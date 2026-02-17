# backend/apps/applications/views.py
# From: Development Guide PDF

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import VettingCase, Document
from .serializers import VettingCaseSerializer, DocumentSerializer
from ai_verification.tasks import verify_document_async
from documents.services import DocumentService

class VettingCaseViewSet(viewsets.ModelViewSet):
    """
    API endpoints for vetting cases
    From: Development Guide PDF
    """
    serializer_class = VettingCaseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Retrieve vetting cases for the authenticated user"""
        if getattr(self, "swagger_fake_view", False):
            return VettingCase.objects.none()
        user = self.request.user
        if hasattr(user, 'role'):  # Admin user
            return VettingCase.objects.all()
        return VettingCase.objects.filter(applicant=user)
    
    def create(self, request):
        """Create new vetting application"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = serializer.save(applicant=request.user)
        
        return Response({
            'success': True,
            'case': VettingCaseSerializer(case).data,
            'message': 'Application created successfully'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """
        Upload document to case
        Triggers AI verification pipeline
        """
        case = self.get_object()
        file = request.FILES.get('document')
        document_type = request.data.get('document_type')
        
        if not file or not document_type:
            return Response(
                {'error': 'document and document_type required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Upload to S3
        doc_service = DocumentService()
        file_path = doc_service.upload_document(file, case.case_id)
        
        # Create document record
        document = Document.objects.create(
            case=case,
            document_type=document_type,
            file_path=file_path,
            file_size=file.size,
            file_name=file.name,
            verification_status='pending'
        )
        
        # Trigger async AI verification
        verify_document_async.delay(document.id)
        
        return Response({
            'success': True,
            'document': DocumentSerializer(document).data,
            'message': 'Document uploaded and queued for verification'
        })
    
    @action(detail=True, methods=['get'])
    def verification_status(self, request, pk=None):
        """
        Get complete verification status including:
        - Document verification results
        - Consistency check
        - Fraud detection
        - Rubric evaluation
        """
        case = self.get_object()
        
        documents_status = []
        for doc in case.documents.all():
            verification = doc.verification_results.first()
            documents_status.append({
                'document_type': doc.document_type,
                'verification_status': doc.verification_status,
                'ai_confidence': doc.ai_confidence_score,
                'ocr_confidence': verification.ocr_confidence if verification else None,
                'authenticity_score': verification.authenticity_score if verification else None
            })
        
        # Consistency check
        consistency = getattr(case, 'consistency_result', None)
        consistency_data = None
        if consistency:
            consistency_data = {
                'overall_score': consistency.overall_score,
                'overall_consistent': consistency.overall_consistent,
                'recommendation': consistency.recommendation
            }
        
        # Fraud detection
        fraud = getattr(case, 'fraud_result', None)
        fraud_data = None
        if fraud:
            fraud_data = {
                'is_fraud': fraud.is_fraud,
                'fraud_probability': fraud.fraud_probability,
                'risk_level': fraud.risk_level,
                'recommendation': fraud.recommendation
            }
        
        # Rubric evaluation
        rubric_eval = case.rubric_evaluations.first()
        rubric_data = None
        if rubric_eval:
            rubric_data = {
                'overall_score': rubric_eval.overall_score,
                'passed': rubric_eval.passed,
                'recommendation': rubric_eval.ai_recommendation,
                'criteria_scores': rubric_eval.criteria_scores
            }
        
        return Response({
            'case_id': case.case_id,
            'status': case.status,
            'documents': documents_status,
            'consistency_check': consistency_data,
            'fraud_detection': fraud_data,
            'rubric_evaluation': rubric_data,
            'overall_scores': {
                'consistency': case.consistency_score,
                'fraud_risk': case.fraud_risk_score
            }
        })