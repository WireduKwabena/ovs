# Django: apps/applications/tasks.py
from celery import shared_task
import httpx
from django.conf import settings

from apps.applications.models import VerificationResult, Document


@shared_task(max_retries=3)
def verify_document_async(document_id):
    """Call FastAPI AI service for document verification"""

    document = Document.objects.get(id=document_id)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.FASTAPI_SERVICE_URL}/api/verify-document",
            files={'document': open(document.file_path, 'rb')},
            data={
                'document_type': document.document_type,
                'case_id': document.case.case_id
            },
            timeout=120.0
        )

    if response.status_code == 200:
        results = response.json()['results']

        # Save to Django database
        VerificationResult.objects.create(
            document=document,
            ocr_text=results['ocr']['text'],
            ocr_confidence=results['ocr']['confidence'],
            authenticity_score=results['authenticity']['overall_score'],
            details=results
        )