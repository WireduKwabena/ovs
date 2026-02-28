from django.conf import settings
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.applications.models import Document, VettingCase
from apps.applications.tasks import verify_document_async
from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment, CandidateSocialProfile


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

        with patch("apps.applications.views.verify_document_async.delay"):
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

    def test_verify_document_task_persists_social_profile_result_when_candidate_data_present(self):
        if "apps.fraud" not in settings.INSTALLED_APPS:
            self.skipTest("Fraud app disabled in INSTALLED_APPS")

        campaign = VettingCampaign.objects.create(
            name="Ops Vetting",
            description="Operations screening",
            status="active",
            initiated_by=self.hr,
        )
        candidate = Candidate.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="candidate_social_test@example.com",
            consent_ai_processing=True,
        )
        enrollment = CandidateEnrollment.objects.create(
            campaign=campaign,
            candidate=candidate,
            status="in_progress",
            metadata={},
        )
        CandidateSocialProfile.objects.create(
            candidate=candidate,
            platform="linkedin",
            url="https://linkedin.com/in/jane-doe",
            username="jane-doe",
            is_primary=True,
        )
        CandidateSocialProfile.objects.create(
            candidate=candidate,
            platform="github",
            url="https://github.com/jane-doe",
            username="jane-doe",
            is_primary=False,
        )

        case = VettingCase.objects.create(
            applicant=self.applicant,
            candidate_enrollment=enrollment,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        file_obj = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        document = Document.objects.create(
            case=case,
            document_type="degree",
            file=file_obj,
            original_filename="resume.pdf",
            file_size=file_obj.size,
            mime_type="application/pdf",
            status="uploaded",
        )

        result = verify_document_async.run(document.id)

        from apps.fraud.models import SocialProfileCheckResult

        self.assertTrue(result["success"])
        social_result = SocialProfileCheckResult.objects.get(application=case)
        self.assertTrue(social_result.consent_provided)
        self.assertGreaterEqual(social_result.profiles_checked, 2)
        self.assertEqual(social_result.recommendation, "MANUAL_REVIEW")

        detail_response = self.client.get(f"/api/applications/cases/{case.id}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIsNotNone(detail_response.json().get("social_profile_result"))

        status_response = self.client.get(f"/api/applications/cases/{case.id}/verification-status/")
        self.assertEqual(status_response.status_code, 200)
        self.assertIsNotNone(status_response.json().get("social_profile_result"))

    def test_verify_document_task_skips_social_profile_result_when_no_profiles(self):
        if "apps.fraud" not in settings.INSTALLED_APPS:
            self.skipTest("Fraud app disabled in INSTALLED_APPS")

        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        file_obj = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        document = Document.objects.create(
            case=case,
            document_type="degree",
            file=file_obj,
            original_filename="resume.pdf",
            file_size=file_obj.size,
            mime_type="application/pdf",
            status="uploaded",
        )

        result = verify_document_async.run(document.id)

        from apps.fraud.models import SocialProfileCheckResult

        self.assertTrue(result["success"])
        self.assertFalse(SocialProfileCheckResult.objects.filter(application=case).exists())

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_returns_ok_when_check_succeeds(self, mock_run_check):
        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        mock_run_check.return_value = {
            "success": True,
            "case_id": case.case_id,
            "result": {
                "profiles_checked": 1,
                "overall_score": 82.0,
                "risk_level": "low",
                "recommendation": "MANUAL_REVIEW",
            },
        }

        response = self.client.post(
            f"/api/applications/cases/{case.id}/recheck-social-profiles/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        mock_run_check.assert_called_once_with(case)

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_returns_skipped_when_no_profiles(self, mock_run_check):
        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        mock_run_check.return_value = {
            "success": False,
            "case_id": case.case_id,
            "reason": "no_profiles",
            "message": "No social profiles available for this case.",
        }

        response = self.client.post(
            f"/api/applications/cases/{case.id}/recheck-social-profiles/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "skipped")
        mock_run_check.assert_called_once_with(case)

    def test_recheck_social_profiles_forbidden_for_non_hr_user(self):
        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        self.client.force_authenticate(self.applicant)

        response = self.client.post(
            f"/api/applications/cases/{case.id}/recheck-social-profiles/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        if "apps.audit" in settings.INSTALLED_APPS:
            from apps.audit.models import AuditLog

            self.assertFalse(
                AuditLog.objects.filter(entity_type="VettingCase", entity_id=str(case.id)).exists()
            )

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_writes_audit_log(self, mock_run_check):
        if "apps.audit" not in settings.INSTALLED_APPS:
            self.skipTest("Audit app disabled in INSTALLED_APPS")

        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        mock_run_check.return_value = {
            "success": True,
            "case_id": case.case_id,
            "record_id": "social-result-1",
            "result": {
                "profiles_checked": 1,
                "overall_score": 90.0,
                "risk_level": "low",
                "recommendation": "MANUAL_REVIEW",
            },
        }

        response = self.client.post(
            f"/api/applications/cases/{case.id}/recheck-social-profiles/",
            {},
            format="json",
            HTTP_USER_AGENT="apps-tests",
            HTTP_X_FORWARDED_FOR="10.0.0.1",
        )

        self.assertEqual(response.status_code, 200)

        from apps.audit.models import AuditLog

        log = AuditLog.objects.filter(entity_type="VettingCase", entity_id=str(case.id)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.admin_user, self.hr)
        self.assertEqual(log.user, self.hr)
        self.assertEqual(log.action, "other")
        self.assertEqual(log.changes.get("event"), "social_profile_recheck")
        self.assertEqual(log.changes.get("status"), "ok")
        self.assertEqual(log.changes.get("case_code"), case.case_id)
        self.assertEqual(log.changes.get("record_id"), "social-result-1")
        self.assertIsNone(log.changes.get("reason"))
        summary = log.changes.get("result_summary") or {}
        self.assertEqual(summary.get("profiles_checked"), 1)
        self.assertEqual(summary.get("overall_score"), 90.0)
        self.assertEqual(summary.get("risk_level"), "low")
        self.assertEqual(summary.get("recommendation"), "MANUAL_REVIEW")
        self.assertEqual(log.ip_address, "10.0.0.1")
        self.assertEqual(log.user_agent, "apps-tests")

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_logs_skipped_status(self, mock_run_check):
        if "apps.audit" not in settings.INSTALLED_APPS:
            self.skipTest("Audit app disabled in INSTALLED_APPS")

        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        mock_run_check.return_value = {
            "success": False,
            "case_id": case.case_id,
            "reason": "no_profiles",
            "message": "No social profiles available for this case.",
        }

        response = self.client.post(
            f"/api/applications/cases/{case.id}/recheck-social-profiles/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "skipped")

        from apps.audit.models import AuditLog

        log = AuditLog.objects.filter(entity_type="VettingCase", entity_id=str(case.id)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, "other")
        self.assertEqual(log.changes.get("event"), "social_profile_recheck")
        self.assertEqual(log.changes.get("status"), "skipped")
        self.assertEqual(log.changes.get("case_code"), case.case_id)
        self.assertEqual(log.changes.get("reason"), "no_profiles")
        self.assertIsNone(log.changes.get("record_id"))
        summary = log.changes.get("result_summary") or {}
        self.assertEqual(summary.get("profiles_checked"), 0)
        self.assertEqual(summary.get("overall_score"), 0.0)
        self.assertEqual(summary.get("risk_level"), "")
        self.assertEqual(summary.get("recommendation"), "")

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_logs_error_status(self, mock_run_check):
        if "apps.audit" not in settings.INSTALLED_APPS:
            self.skipTest("Audit app disabled in INSTALLED_APPS")

        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        mock_run_check.return_value = {
            "success": False,
            "case_id": case.case_id,
            "reason": "check_failed",
            "error": "mock failure",
        }

        response = self.client.post(
            f"/api/applications/cases/{case.id}/recheck-social-profiles/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

        from apps.audit.models import AuditLog

        log = AuditLog.objects.filter(entity_type="VettingCase", entity_id=str(case.id)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, "other")
        self.assertEqual(log.changes.get("event"), "social_profile_recheck")
        self.assertEqual(log.changes.get("status"), "error")
        self.assertEqual(log.changes.get("case_code"), case.case_id)
        self.assertEqual(log.changes.get("reason"), "check_failed")
        self.assertIsNone(log.changes.get("record_id"))
        summary = log.changes.get("result_summary") or {}
        self.assertEqual(summary.get("profiles_checked"), 0)
        self.assertEqual(summary.get("overall_score"), 0.0)
        self.assertEqual(summary.get("risk_level"), "")
        self.assertEqual(summary.get("recommendation"), "")
