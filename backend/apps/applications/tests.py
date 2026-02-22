from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.applications.models import VettingCase


class ApplicationsApiTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_apps_test@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Tester",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="app_apps_test@example.com",
            password="Pass1234!",
            first_name="App",
            last_name="Tester",
            user_type="applicant",
        )
        self.client.force_authenticate(self.hr)

    def test_create_case_upload_document_and_get_verification_status(self):
        create_response = self.client.post(
            "/api/applications/cases/",
            {
                "applicant": self.applicant.id,
                "position_applied": "Analyst",
                "department": "Operations",
                "job_description": "Data validation and reporting",
                "priority": "medium",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        case_id = create_response.json()["id"]

        upload_response = self.client.post(
            f"/api/applications/cases/{case_id}/upload-document/",
            {
                "document_type": "degree",
                "file": SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201)
        self.assertIn(upload_response.json()["status"], {"queued", "processing", "verified", "flagged", "failed"})

        case = VettingCase.objects.get(id=case_id)
        self.assertTrue(case.documents_uploaded)

        status_response = self.client.get(f"/api/applications/cases/{case_id}/verification-status/")
        self.assertEqual(status_response.status_code, 200)
        payload = status_response.json()
        self.assertEqual(payload["case_id"], case.case_id)
        self.assertGreaterEqual(payload["documents_total"], 1)

    def test_hr_create_case_without_applicant_returns_400(self):
        response = self.client.post(
            "/api/applications/cases/",
            {
                "position_applied": "Analyst",
                "department": "Operations",
                "job_description": "Data validation and reporting",
                "priority": "medium",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("applicant", response.json())
