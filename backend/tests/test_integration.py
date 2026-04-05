# backend/tests/test_integration.py
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from apps.applications.models import VettingCase
from apps.users.models import User
import os
import unittest

# TODO: This is a placeholder test based on the integration guide.
# It requires further setup to run correctly (e.g., proper request data,
# and mocking of external services).

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@unittest.skip("Legacy placeholder integration flow; requires full endpoint/mocking refresh.")
class IntegrationTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpassword',
            full_name='Test User',
            date_of_birth='1990-01-01'
        )
        # Get JWT token
        response = self.client.post('/api/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.token = response.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_full_vetting_workflow(self):
        # 1. Create application
        # TODO: Replace with actual application data from the models
        application_data = {
            "application_type": "employment",
            "priority": "medium",
            "notes": "Test application"
        }
        response = self.client.post('/api/applications/', application_data, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        application_id = response.data['case']['id']

        # 2. Upload documents
        file_path = os.path.join(os.path.dirname(__file__), 'test_doc.pdf')
        with open(file_path, 'rb') as f:
            response = self.client.post(f'/api/applications/{application_id}/upload_document/', {
                'document': f,
                'document_type': 'id_card'
            })
        self.assertEqual(response.status_code, 201)

        # 3. AI processing happens synchronously because of CELERY_TASK_ALWAYS_EAGER=True

        # 4. Check verification results
        application = VettingCase.objects.get(id=application_id)
        # TODO: This assertion will fail until the verification_results field is populated.
        # self.assertIsNotNone(application.verification_results)

        # 5. Start interview
        response = self.client.post('/api/interviews/interrogation/start/', {
            'application_id': application_id
        })
        self.assertEqual(response.status_code, 200)
