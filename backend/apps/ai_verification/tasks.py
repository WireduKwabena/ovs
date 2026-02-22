# backend/apps/ai_verification/tasks.py
# From: Development Guide & AI/ML PDFs

from celery import shared_task
import requests
from apps.applications import VettingCase, Document, VerificationResult
from fraud.models import FraudDetectionResult, ConsistencyCheckResult
from apps.rubrics.logic import generate_flags
from apps.rubrics.engine import RubricEvaluationEngine
import logging

logger = logging.getLogger(__name__)

AI_SERVICE_URL = "http://localhost:5000"  # FastAPI service

@shared_task(bind=True, max_retries=3)
def verify_document_async(self, document_id):
    """
    Async document verification task
    From: Development Guide PDF
    
    This task:
    1. Gets document from Django DB
    2. Sends to FastAPI for AI processing
    3. Saves results back to Django DB
    """
    try:
        document = Document.objects.get(id=document_id)
        document.verification_status = 'processing'
        document.save()
        
        # Get file from S3
        from documents.services import DocumentService
        doc_service = DocumentService()
        file_url = doc_service.get_presigned_url(document.file_path)
        
        # Download file temporarily
        import tempfile
        import requests as req
        response = req.get(file_url)
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        # Send to FastAPI for AI verification
        with open(tmp_path, 'rb') as f:
            ai_response = requests.post(
                f"{AI_SERVICE_URL}/api/verify-document",
                files={'file': f},
                data={
                    'document_type': document.document_type,
                    'case_id': document.case.case_id
                },
                timeout=120
            )
        
        if ai_response.status_code == 200:
            results = ai_response.json()
            
            # Save verification results to Django DB
            VerificationResult.objects.create(
                document=document,
                ocr_text=results['results']['ocr']['text'],
                ocr_confidence=results['results']['ocr']['confidence'],
                ocr_method=results['results']['ocr'].get('method', 'hybrid'),
                authenticity_score=results['results']['authenticity']['overall_score'],
                is_authentic=results['results']['authenticity']['overall_score'] > 70,
                extracted_data=results['results']['ocr'].get('extracted_data', {}),
                cv_checks=results['results']['authenticity']['computer_vision'],
                details=results['results']
            )
            
            # Update document status
            document.verification_status = 'verified'
            document.ai_confidence_score = results['results']['overall_score']
            document.save()
            
            # Check if all documents are verified
            case = document.case
            all_docs = case.documents.all()
            if all(doc.verification_status == 'verified' for doc in all_docs):
                # Trigger consistency and fraud checks
                check_application_consistency.delay(case.id)
                detect_application_fraud.delay(case.id)
            
            return {
                'success': True,
                'document_id': document_id,
                'overall_score': results['results']['overall_score']
            }
        else:
            raise Exception(f"AI Service error: {ai_response.status_code}")
            
    except Exception as e:
        logger.error(f"Document verification failed: {str(e)}")
        document.verification_status = 'failed'
        document.save()
        
        # Retry on failure
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def check_application_consistency(self, case_id):
    """
    Check consistency across all documents in application
    From: AI/ML PDF - Consistency section
    """
    try:
        case = VettingCase.objects.get(id=case_id)
        documents = case.documents.all()
        
        # Prepare data for consistency check
        documents_data = []
        for doc in documents:
            verification = doc.verification_results.first()
            if verification:
                documents_data.append({
                    'text': verification.ocr_text,
                    'document_type': doc.document_type,
                    'extracted_data': verification.extracted_data
                })
        
        # Call FastAPI consistency checker
        response = requests.post(
            f"{AI_SERVICE_URL}/api/check-consistency",
            json={'documents': documents_data},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()['consistency_result']
            
            # Save to Django DB
            ConsistencyCheckResult.objects.update_or_create(
                application=case,
                defaults={
                    'overall_consistent': result['overall_consistent'],
                    'overall_score': result['overall_score'],
                    'name_consistency': result['name_consistency'],
                    'date_consistency': result['date_consistency'],
                    'entity_consistency': result.get('entity_consistency', {}),
                    'recommendation': result['recommendation']
                }
            )
            
            # Update case consistency score
            case.consistency_score = result['overall_score']
            case.save()
            
            return {'success': True, 'case_id': case.case_id}
            
    except Exception as e:
        logger.error(f"Consistency check failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def detect_application_fraud(self, case_id):
    """
    Run fraud detection on complete application
    From: AI/ML PDF - Fraud Detection section
    """
    try:
        case = VettingCase.objects.get(id=case_id)
        documents = case.documents.all()
        
        # Extract features for fraud detection
        application_data = {
            'case_id': case.case_id,
            'applicant_name': case.applicant.full_name,
            'email': case.applicant.email,
            'phone': case.applicant.phone_number,
            'submission_time': {
                'hour': case.created_at.hour,
                'day': case.created_at.weekday()
            },
            'documents': []
        }
        
        for doc in documents:
            verification = doc.verification_results.first()
            if verification:
                application_data['documents'].append({
                    'document_type': doc.document_type,
                    'ocr_confidence': verification.ocr_confidence,
                    'authenticity_score': verification.authenticity_score,
                    'text': verification.ocr_text,
                    'has_metadata': verification.cv_checks.get('metadata', {}).get('has_metadata', False)
                })
        
        # Add consistency score if available
        consistency = getattr(case, 'consistency_result', None)
        if consistency:
            application_data['consistency_check'] = {
                'overall_score': consistency.overall_score
            }
        
        # Call FastAPI fraud detector
        response = requests.post(
            f"{AI_SERVICE_URL}/api/detect-fraud",
            json={'application_data': application_data},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Save to Django DB
            FraudDetectionResult.objects.update_or_create(
                application=case,
                defaults={
                    'is_fraud': result['is_fraud'],
                    'fraud_probability': result['fraud_probability'],
                    'anomaly_score': result['anomaly_score'],
                    'risk_level': result['risk_level'],
                    'recommendation': result['recommendation'],
                    'feature_scores': result.get('feature_scores', {})
                }
            )
            
            # Update case fraud score
            case.fraud_risk_score = result['fraud_probability']
            
            # Update case status based on risk
            if result['risk_level'] == 'HIGH':
                case.status = 'under_review'
                case.priority = 'high'
            elif result['risk_level'] == 'MEDIUM':
                case.status = 'under_review'
            
            case.save()
            
            # Trigger rubric evaluation if configured
            evaluate_with_rubric.delay(case.id)
            
            return {'success': True, 'case_id': case.case_id}
            
    except Exception as e:
        logger.error(f"Fraud detection failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task
def evaluate_with_rubric(case_id):
    """
    Evaluate application against HR-defined rubric
    From: Dynamic Vetting Rubrics PDF
    """
    try:
        from apps.rubrics import VettingRubric
        
        case = VettingCase.objects.get(id=case_id)
        
        # Find appropriate rubric
        rubrics = VettingRubric.objects.filter(
            status='active',
            rubric_type=case.application_type
        )
        
        if case.applicant.email:  # Can add more sophisticated matching
            # Match by department/position if available
            rubric = rubrics.first()
        else:
            rubric = rubrics.first()
        
        if rubric:
            # Run rubric evaluation engine
            engine = RubricEvaluationEngine(case, rubric)
            evaluation = engine.evaluate()
            
            # Update case status based on rubric evaluation
            if evaluation.ai_recommendation == 'AUTO_APPROVE':
                case.status = 'approved'
            elif evaluation.ai_recommendation == 'AUTO_REJECT':
                case.status = 'rejected'
            else:
                case.status = 'under_review'
            
            case.save()
            
            # Send notification
            from apps.notifications.services import NotificationService
            NotificationService.send_evaluation_complete(case, evaluation)
            
            return {
                'success': True,
                'case_id': case.case_id,
                'evaluation_score': evaluation.overall_score,
                'recommendation': evaluation.ai_recommendation
            }
        else:
            logger.warning(f"No active rubric found for case {case.case_id}")
            return {'success': False, 'reason': 'No rubric configured'}
            
    except Exception as e:
        logger.error(f"Rubric evaluation failed: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def batch_process_applications(case_ids):
    """
    Process multiple applications in batch
    Useful for bulk uploads
    """
    results = []
    for case_id in case_ids:
        try:
            case = VettingCase.objects.get(id=case_id)
            documents = case.documents.all()
            
            # Queue verification for all documents
            for doc in documents:
                verify_document_async.delay(doc.id)
            
            results.append({
                'case_id': case.case_id,
                'status': 'queued',
                'documents_count': documents.count()
            })
        except Exception as e:
            results.append({
                'case_id': case_id,
                'status': 'error',
                'error': str(e)
            })
    
    return results

@shared_task
def aggregate_flags(vetting_case_id):
    case = VettingCase.objects.get(id=vetting_case_id)
    case.interrogation_flags = generate_flags(case.ai_vetting_results)
    case.save()
    
@shared_task
def trigger_interrogation(vetting_case_id):
    case = VettingCase.objects.get(id=vetting_case_id)
    flags = generate_flags(case)  # From rubrics
    response = requests.post('/api/interviews/interrogation/start/', json={'application_id': case.id})
    session_id = response.json()['session_id']
    # Email link: f"ws://yourserver.com/ws/interview/{session_id}"