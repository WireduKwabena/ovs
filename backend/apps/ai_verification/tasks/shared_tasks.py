### Django Celery Integration

# backend/apps/ai_verification/tasks.py
from celery import shared_task
import requests
from django.conf import settings
from apps.applications.models import Document
from apps.applications.models import VerificationResult


@shared_task(bind=True, max_retries=3)
def verify_document_async(self, document_id):
    """
    Async task to verify document with AI service
    """
    try:
        document = Document.objects.get(id=document_id)

        # Prepare file for AI service
        file_path = document.file_path

        # Call AI service
        with open(file_path, 'rb') as f:
            response = requests.post(
                f'{settings.AI_SERVICE_URL}/api/verify-document',
                files={'file': f},
                data={
                    'document_type': document.document_type,
                    'case_id': document.case.case_id
                },
                timeout=120
            )

        if response.status_code == 200:
            result_data = response.json()

            # Save verification result
            VerificationResult.objects.create(
                document=document,
                ocr_text=result_data['results']['ocr'].get('text', ''),
                ocr_confidence=result_data['results']['ocr'].get('confidence', 0),
                authenticity_score=result_data['results']['authenticity']['overall_score'],
                overall_score=result_data['results']['overall_score'],
                recommendation=result_data['results']['recommendation'],
                raw_result=result_data
            )

            # Update document status
            document.verification_status = 'completed'
            document.ai_confidence_score = result_data['results']['overall_score']
            document.save()

            return {
                'success': True,
                'document_id': document_id,
                'score': result_data['results']['overall_score']
            }
        else:
            raise Exception(f"AI service returned {response.status_code}")

    except Exception as e:
        # Retry on failure
        raise self.retry(exc=e, countdown=60)


@shared_task
def check_consistency_async(case_id):
    """
    Check consistency across all documents in a case
    """
    from apps.applications.models import VettingCase

    try:
        case = VettingCase.objects.get(case_id=case_id)
        documents = case.documents.all()

        # Prepare documents data
        documents_data = []
        for doc in documents:
            verification = doc.verification_results.first()
            if verification:
                documents_data.append({
                    'text': verification.ocr_text,
                    'document_type': doc.document_type,
                    'confidence': verification.ocr_confidence
                })

        # Call AI service
        response = requests.post(
            f'{settings.AI_SERVICE_URL}/api/check-consistency',
            json=documents_data,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()

            # Save consistency result to case
            case.consistency_score = result['consistency_result']['overall_score']
            case.consistency_report = result['consistency_result']
            case.save()

            return {
                'success': True,
                'case_id': case_id,
                'consistency_score': result['consistency_result']['overall_score']
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def detect_fraud_async(case_id):
    """
    Run fraud detection on application
    """
    from apps.applications.models import VettingCase

    try:
        case = VettingCase.objects.get(case_id=case_id)

        # Prepare application data
        application_data = {
            'case_id': case.case_id,
            'applicant_id': case.applicant.id,
            'documents': [
                {
                    'document_type': doc.document_type,
                    'file_size': doc.file_size,
                    'uploaded_at': doc.upload_date.isoformat(),
                    'ocr_confidence': doc.verification_results.first().ocr_confidence if doc.verification_results.exists() else 0,
                    'authenticity_score': doc.ai_confidence_score or 0,
                    'has_metadata': True
                }
                for doc in case.documents.all()
            ],
            'full_name': case.applicant.full_name,
            'email': case.applicant.email,
            'phone': case.applicant.phone_number,
            'consistency_check': {
                'overall_score': case.consistency_score or 0
            },
            'submission_time': {
                'hour': case.created_at.hour
            },
            'user_history': []  # Would fetch from database
        }

        # Call AI service
        response = requests.post(
            f'{settings.AI_SERVICE_URL}/api/detect-fraud',
            json=application_data,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()

            # Save fraud detection result
            case.fraud_risk_score = result['combined_risk_score']
            case.fraud_detection_report = result
            case.save()

            # If high risk, flag for review
            if result['combined_risk_score'] > 0.7:
                case.status = 'flagged'
                case.notes = 'Flagged by AI fraud detection system'
                case.save()

            return {
                'success': True,
                'case_id': case_id,
                'risk_score': result['combined_risk_score']
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
        
        
        # In your Django task

@shared_task
def verify_document_complete(document_id: int):
    """
    Complete authenticity verification
    """
    from apps.applications.models import Document
    from apps.ai_ml_services.authenticity import DocumentAuthenticityService
    
    document = Document.objects.get(id=document_id)
    service = DocumentAuthenticityService()
    
    # Load image
    image = cv2.imread(document.file.path)
    
    # Analyze
    result = service.analyze_single_document(
        image_path=document.file.path,
        image=image
    )
    
    # Save results
    document.authenticity_score = result['final_authenticity_score']
    document.is_authentic = result['is_authentic']
    document.authenticity_details = result
    document.save()
    
    # If multiple documents in case
    if document.case.documents.count() >= 2:
        consistency_result = service.analyze_multiple_documents([
            {
                'text': doc.extracted_text,
                'document_type': doc.document_type,
                'extracted_data': doc.extracted_data,
                'image_path': doc.file.path,
                'image': cv2.imread(doc.file.path)
            }
            for doc in document.case.documents.all()
        ])
        
        document.case.consistency_score = consistency_result['overall_score']
        document.case.save()
