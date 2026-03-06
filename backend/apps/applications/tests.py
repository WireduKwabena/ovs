from django.conf import settings
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.applications.models import Document, VettingCase
from apps.applications.tasks import verify_document_async
from apps.authentication.models import User
from apps.billing.models import BillingSubscription
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment, CandidateSocialProfile
from apps.interviews.models import InterviewSession


class ApplicationsApiTests(APITestCase):
    def _seed_subscription(self, user, *, plan_id="starter", plan_name="Starter"):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference=f"OVS-{plan_id.upper()}-{user.id.hex[:6]}",
            registration_consumed_by_email=user.email,
        )

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
        self._seed_subscription(self.hr, plan_id="growth", plan_name="Growth")
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

    @patch("apps.applications.views.verify_document_async.delay")
    def test_upload_document_rejects_non_required_campaign_type(self, _mock_verify_delay):
        campaign = VettingCampaign.objects.create(
            name="Strict Docs Campaign",
            initiated_by=self.hr,
            settings_json={"required_document_types": ["id_card", "passport"]},
        )
        candidate = Candidate.objects.create(
            first_name="Doc",
            last_name="Restricted",
            email="doc.restricted@example.com",
            consent_ai_processing=True,
        )
        enrollment = CandidateEnrollment.objects.create(
            campaign=campaign,
            candidate=candidate,
            status="in_progress",
        )
        case = VettingCase.objects.create(
            applicant=self.applicant,
            candidate_enrollment=enrollment,
            assigned_to=self.hr,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_upload",
        )

        forbidden_upload = self.client.post(
            f"/api/applications/cases/{case.id}/upload-document/",
            {
                "document_type": "degree",
                "file": SimpleUploadedFile("degree.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(forbidden_upload.status_code, 400)
        error_payload = forbidden_upload.json()
        self.assertIn("document_type", error_payload)
        self.assertIn("required_document_types", error_payload)
        self.assertEqual(error_payload["required_document_types"], ["id_card", "passport"])

        allowed_upload = self.client.post(
            f"/api/applications/cases/{case.id}/upload-document/",
            {
                "document_type": "id_card",
                "file": SimpleUploadedFile("id-card.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(allowed_upload.status_code, 201)

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

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=0,
        BILLING_PLAN_DEFAULT_CANDIDATES_PER_MONTH=0,
    )
    def test_hr_create_case_requires_active_subscription_when_not_admin(self):
        hr_without_subscription = User.objects.create_user(
            email="hr_no_sub_apps@example.com",
            password="Pass1234!",
            first_name="No",
            last_name="Subscription",
            user_type="hr_manager",
        )
        self.client.force_authenticate(hr_without_subscription)

        response = self.client.post(
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

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "subscription_required")
        self.assertIn("quota", payload)
        self.assertIn("period_start", payload["quota"])
        self.assertIn("period_end", payload["quota"])
        self.assertTrue(str(payload["quota"].get("period_start")))
        self.assertTrue(str(payload["quota"].get("period_end")))

    def test_hr_cannot_create_case_for_enrollment_outside_owned_campaign(self):
        other_hr = User.objects.create_user(
            email="hr_other_apps@example.com",
            password="Pass1234!",
            first_name="Other",
            last_name="Manager",
            user_type="hr_manager",
        )
        campaign = VettingCampaign.objects.create(
            name="Other HR Campaign",
            description="Owned by other HR",
            status="active",
            initiated_by=other_hr,
        )
        candidate = Candidate.objects.create(
            first_name="Owned",
            last_name="Elsewhere",
            email="candidate_elsewhere@example.com",
            consent_ai_processing=True,
        )
        enrollment = CandidateEnrollment.objects.create(
            campaign=campaign,
            candidate=candidate,
            status="in_progress",
            metadata={},
        )

        self.client.force_authenticate(self.hr)
        response = self.client.post(
            "/api/applications/cases/",
            {
                "applicant": self.applicant.id,
                "candidate_enrollment": str(enrollment.id),
                "position_applied": "Analyst",
                "department": "Operations",
                "job_description": "Data validation and reporting",
                "priority": "medium",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

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

    def test_verify_document_task_auto_schedules_interview_session_when_documents_verified(self):
        campaign = VettingCampaign.objects.create(
            name="Auto Interview Campaign",
            description="Auto schedule candidate interview",
            status="active",
            initiated_by=self.hr,
        )
        candidate = Candidate.objects.create(
            first_name="John",
            last_name="Doe",
            email="candidate_auto_interview@example.com",
            consent_ai_processing=True,
        )
        enrollment = CandidateEnrollment.objects.create(
            campaign=campaign,
            candidate=candidate,
            status="in_progress",
            metadata={},
        )
        case = VettingCase.objects.create(
            applicant=self.applicant,
            candidate_enrollment=enrollment,
            assigned_to=self.hr,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        file_obj = SimpleUploadedFile("id_card.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        document = Document.objects.create(
            case=case,
            document_type="id_card",
            file=file_obj,
            original_filename="id_card.pdf",
            file_size=file_obj.size,
            mime_type="application/pdf",
            status="uploaded",
        )

        result = verify_document_async.run(document.id)

        self.assertTrue(result["success"])
        case.refresh_from_db()
        self.assertEqual(case.status, "interview_scheduled")
        self.assertTrue(InterviewSession.objects.filter(case=case).exists())

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
