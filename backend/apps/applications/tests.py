from django.conf import settings
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.applications.models import (
    Document,
    VerificationRequest,
    VerificationResult,
    VerificationSource,
    VettingCase,
)
from apps.applications.tasks import verify_document_async
from apps.applications.verification_gateway import (
    build_case_external_verification_snapshot,
    create_verification_request,
    record_verification_result,
)
from apps.users.models import User
from apps.billing.models import BillingSubscription
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment, CandidateSocialProfile
from apps.tenants.models import Organization
from apps.governance.models import OrganizationMembership
from apps.interviews.models import InterviewSession
from apps.rubrics.decision_engine import VettingDecisionEngine
from apps.rubrics.engine import RubricEvaluationEngine
from apps.rubrics.models import VettingRubric


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

    def _create_org_subscription(self, organization, *, status="complete", payment_status="paid", plan_id="starter"):
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=organization,
            status=status,
            payment_status=payment_status,
            plan_id=plan_id,
            plan_name=plan_id.title(),
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference=f"OVS-ORG-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    def setUp(self):
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.hr = User.objects.create_user(
            email="internal_apps_test@example.com",
            password="Pass1234!",
            first_name="Internal",
            last_name="Tester",
            user_type="internal",
            is_staff=True,
        )
        self.hr.groups.add(vetting_officer_group)
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
        org = Organization.objects.create(
            code="apps-basic-flow-org",
            name="Applications Basic Flow Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=org,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        active_org_headers = {"HTTP_X_ACTIVE_ORGANIZATION_ID": str(org.id)}

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
            **active_org_headers,
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
                **active_org_headers,
            )
        self.assertEqual(upload_response.status_code, 201)
        self.assertIn(upload_response.json()["status"], {"queued", "processing", "verified", "flagged", "failed"})

        case = VettingCase.objects.get(id=case_id)
        self.assertTrue(case.documents_uploaded)
        self.assertEqual(case.organization_id, org.id)

        status_response = self.client.get(
            f"/api/applications/cases/{case_id}/verification-status/",
            **active_org_headers,
        )
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

    def test_internal_create_case_without_applicant_returns_400(self):
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
    def test_internal_create_case_requires_active_subscription_when_not_admin(self):
        internal_without_subscription = User.objects.create_user(
            email="internal_no_sub_apps@example.com",
            password="Pass1234!",
            first_name="No",
            last_name="Subscription",
            user_type="internal",
        )
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        internal_without_subscription.groups.add(vetting_officer_group)
        organization = Organization.objects.create(
            code="apps-no-subscription-org",
            name="Applications No Subscription Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=internal_without_subscription,
            organization=organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self._create_org_subscription(
            organization,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
        )
        self.client.force_authenticate(internal_without_subscription)

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
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "subscription_required")
        self.assertIn("quota", payload)
        self.assertIn("period_start", payload["quota"])
        self.assertIn("period_end", payload["quota"])
        self.assertTrue(str(payload["quota"].get("period_start")))
        self.assertTrue(str(payload["quota"].get("period_end")))

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=1,
    )
    def test_internal_create_case_uses_org_scoped_quota_context(self):
        organization = Organization.objects.create(
            code="apps-quota-org",
            name="Applications Quota Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )

        BillingSubscription.objects.create(
            provider="sandbox",
            organization=organization,
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-APPS-ORG-QUOTA-STARTER",
        )

        scoped_campaign = VettingCampaign.objects.create(
            organization=organization,
            name="Apps Scoped Campaign",
            initiated_by=self.hr,
        )
        scoped_candidate = Candidate.objects.create(
            first_name="Quota",
            last_name="Used",
            email="apps_quota_used@example.com",
        )
        CandidateEnrollment.objects.create(
            campaign=scoped_campaign,
            candidate=scoped_candidate,
            status="invited",
        )

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
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "quota_exceeded")
        quota_payload = payload.get("quota") or {}
        self.assertEqual(int(quota_payload.get("limit")), 1)
        self.assertEqual(int(quota_payload.get("used")), 1)
        self.assertIn("organization:", str(quota_payload.get("scope", "")))

    def test_internal_cannot_create_case_for_enrollment_outside_owned_campaign(self):
        other_hr = User.objects.create_user(
            email="internal_other_apps@example.com",
            password="Pass1234!",
            first_name="Other",
            last_name="Manager",
            user_type="internal",
        )
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        other_hr.groups.add(vetting_officer_group)
        campaign = VettingCampaign.objects.create(
            name="Other Internal Campaign",
            description="Owned by other internal reviewer",
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

    @override_settings(
        BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_DOCUMENT_VERIFICATION_PER_MONTH=1,
    )
    @patch("apps.applications.views.verify_document_async.delay")
    def test_upload_document_blocks_when_org_document_verification_quota_exceeded(self, mock_verify_delay):
        organization = Organization.objects.create(
            code="apps-doc-quota-org",
            name="Apps Doc Quota Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self._create_org_subscription(organization, plan_id="starter")

        exhausted_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        exhausted_file = SimpleUploadedFile("used.pdf", b"%PDF-1.4 used", content_type="application/pdf")
        exhausted_doc = Document.objects.create(
            case=exhausted_case,
            document_type="degree",
            file=exhausted_file,
            original_filename="used.pdf",
            file_size=exhausted_file.size,
            mime_type="application/pdf",
            status="verified",
        )
        VerificationResult.objects.create(
            document=exhausted_doc,
            ocr_text="used",
            ocr_confidence=95.0,
            ocr_language="en",
            authenticity_score=95.0,
            authenticity_confidence=95.0,
            is_authentic=True,
            metadata_check_passed=True,
            visual_check_passed=True,
            tampering_detected=False,
            fraud_risk_score=5.0,
            fraud_prediction="legitimate",
            fraud_indicators=[],
            detailed_results={},
            ocr_model_version="baseline",
            authenticity_model_version="baseline",
            fraud_model_version="baseline",
            processing_time_seconds=0.5,
        )

        target_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_upload",
        )

        response = self.client.post(
            f"/api/applications/cases/{target_case.id}/upload-document/",
            {
                "document_type": "id_card",
                "file": SimpleUploadedFile("id-card.pdf", b"%PDF-1.4 blocked", content_type="application/pdf"),
            },
            format="multipart",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "vetting_operation_quota_exceeded")
        self.assertEqual((payload.get("quota") or {}).get("operation"), "document_verification")
        mock_verify_delay.assert_not_called()

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    @patch("apps.applications.views.verify_document_async.delay")
    def test_upload_document_uses_legacy_user_org_mapping_for_quota_scope(self, mock_verify_delay):
        legacy_org = Organization.objects.create(
            code="legacy-user-org-map",
            name="Legacy User Organization Map",
            organization_type="agency",
            is_active=True,
        )
        legacy_internal_user = User.objects.create_user(
            email="legacy_org_internal_apps@example.com",
            password="Pass1234!",
            first_name="Legacy",
            last_name="Org",
            user_type="internal",
            organization=legacy_org.name,
        )
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        legacy_internal_user.groups.add(vetting_officer_group)
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=legacy_org,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-LEGACY-ORG-MAP-INACTIVE",
        )
        case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=legacy_internal_user,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_upload",
        )

        self.client.force_authenticate(legacy_internal_user)
        response = self.client.post(
            f"/api/applications/cases/{case.id}/upload-document/",
            {
                "document_type": "id_card",
                "file": SimpleUploadedFile("legacy-map.pdf", b"%PDF-1.4 legacy", content_type="application/pdf"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "subscription_required")
        self.assertEqual((payload.get("quota") or {}).get("operation"), "document_verification")
        self.assertIn(str(legacy_org.id), str((payload.get("quota") or {}).get("scope", "")))
        mock_verify_delay.assert_not_called()

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_verify_document_task_blocks_when_org_subscription_is_inactive(self):
        organization = Organization.objects.create(
            code="apps-doc-sub-inactive",
            name="Apps Doc Subscription Inactive Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self._create_org_subscription(
            organization,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
        )

        case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        file_obj = SimpleUploadedFile("inactive.pdf", b"%PDF-1.4 blocked", content_type="application/pdf")
        document = Document.objects.create(
            case=case,
            document_type="degree",
            file=file_obj,
            original_filename="inactive.pdf",
            file_size=file_obj.size,
            mime_type="application/pdf",
            status="uploaded",
        )

        result = verify_document_async.run(document.id)

        document.refresh_from_db()
        self.assertFalse(result["success"])
        self.assertEqual(result.get("code"), "subscription_required")
        self.assertEqual(document.status, "failed")

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_verify_document_task_blocks_with_legacy_org_mapping_when_case_has_no_org(self):
        legacy_org = Organization.objects.create(
            code="apps-doc-legacy-task-org",
            name="Apps Document Legacy Task Org",
            organization_type="agency",
            is_active=True,
        )
        legacy_internal_user = User.objects.create_user(
            email="legacy_task_internal_apps@example.com",
            password="Pass1234!",
            first_name="Legacy",
            last_name="TaskHR",
            user_type="internal",
            organization=legacy_org.name,
        )
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        legacy_internal_user.groups.add(vetting_officer_group)
        self._create_org_subscription(
            legacy_org,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
        )

        case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=legacy_internal_user,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        file_obj = SimpleUploadedFile("legacy-task.pdf", b"%PDF-1.4 blocked", content_type="application/pdf")
        document = Document.objects.create(
            case=case,
            document_type="degree",
            file=file_obj,
            original_filename="legacy-task.pdf",
            file_size=file_obj.size,
            mime_type="application/pdf",
            status="uploaded",
        )

        result = verify_document_async.run(document.id)

        document.refresh_from_db()
        self.assertFalse(result["success"])
        self.assertEqual(result.get("code"), "subscription_required")
        self.assertEqual((result.get("quota") or {}).get("operation"), "document_verification")
        self.assertIn(str(legacy_org.id), str((result.get("quota") or {}).get("scope", "")))
        self.assertEqual(document.status, "failed")

    @override_settings(
        BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_VETTING_REQUIRE_SCOPE_RESOLUTION=True,
    )
    def test_verify_document_task_blocks_when_org_context_cannot_be_resolved(self):
        unscoped_hr = User.objects.create_user(
            email="unscoped_internal_apps@example.com",
            password="Pass1234!",
            first_name="Unscoped",
            last_name="Reviewer",
            user_type="internal",
        )
        unscoped_applicant = User.objects.create_user(
            email="unscoped_app_apps@example.com",
            password="Pass1234!",
            first_name="Unscoped",
            last_name="Applicant",
            user_type="applicant",
        )
        case = VettingCase.objects.create(
            applicant=unscoped_applicant,
            assigned_to=unscoped_hr,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="document_analysis",
        )
        file_obj = SimpleUploadedFile("unscoped.pdf", b"%PDF-1.4 blocked", content_type="application/pdf")
        document = Document.objects.create(
            case=case,
            document_type="degree",
            file=file_obj,
            original_filename="unscoped.pdf",
            file_size=file_obj.size,
            mime_type="application/pdf",
            status="uploaded",
        )

        result = verify_document_async.run(document.id)

        document.refresh_from_db()
        self.assertFalse(result["success"])
        self.assertEqual(result.get("code"), "organization_context_required")
        self.assertEqual((result.get("quota") or {}).get("operation"), "document_verification")
        self.assertEqual(document.status, "failed")

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
            assigned_to=self.hr,
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
            assigned_to=self.hr,
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
            assigned_to=self.hr,
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
        mock_run_check.assert_called_once_with(case, actor=self.hr)

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_returns_skipped_when_no_profiles(self, mock_run_check):
        case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
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
        mock_run_check.assert_called_once_with(case, actor=self.hr)

    def test_recheck_social_profiles_forbidden_for_non_internal_user(self):
        case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
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

    def test_plain_internal_without_operational_role_cannot_list_cases(self):
        plain_internal = User.objects.create_user(
            email="plain_internal_apps_cases@example.com",
            password="Pass1234!",
            first_name="Plain",
            last_name="Reviewer",
            user_type="internal",
        )
        self.client.force_authenticate(plain_internal)
        response = self.client.get("/api/applications/cases/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("results", []), [])

    @patch("apps.applications.views.run_case_social_profile_check")
    def test_recheck_social_profiles_writes_audit_log(self, mock_run_check):
        if "apps.audit" not in settings.INSTALLED_APPS:
            self.skipTest("Audit app disabled in INSTALLED_APPS")

        case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
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
            assigned_to=self.hr,
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
            assigned_to=self.hr,
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


class ApplicationsOrganizationScopeTests(APITestCase):
    def setUp(self):
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.org_a = Organization.objects.create(code="apps-org-a", name="Applications Org A")
        self.org_b = Organization.objects.create(code="apps-org-b", name="Applications Org B")

        self.internal_a = User.objects.create_user(
            email="apps_scope_a@example.com",
            password="Pass1234!",
            first_name="Apps",
            last_name="ScopeA",
            user_type="internal",
        )
        self.internal_a.groups.add(vetting_officer_group)
        self.internal_b = User.objects.create_user(
            email="apps_scope_b@example.com",
            password="Pass1234!",
            first_name="Apps",
            last_name="ScopeB",
            user_type="internal",
        )
        self.internal_b.groups.add(vetting_officer_group)
        self.applicant = User.objects.create_user(
            email="apps_scope_applicant@example.com",
            password="Pass1234!",
            first_name="Apps",
            last_name="Applicant",
            user_type="applicant",
        )
        OrganizationMembership.objects.create(
            user=self.internal_a,
            organization=self.org_a,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.internal_b,
            organization=self.org_b,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )

        self.campaign_org_a = VettingCampaign.objects.create(
            name="Applications Campaign A",
            organization=self.org_a,
            initiated_by=self.internal_b,
            status="active",
        )
        self.campaign_org_b = VettingCampaign.objects.create(
            name="Applications Campaign B",
            organization=self.org_b,
            initiated_by=self.internal_b,
            status="active",
        )
        self.candidate_a = Candidate.objects.create(
            first_name="Org",
            last_name="CandidateA",
            email="apps_scope_candidate_a@example.com",
        )
        self.candidate_b = Candidate.objects.create(
            first_name="Org",
            last_name="CandidateB",
            email="apps_scope_candidate_b@example.com",
        )
        self.enrollment_org_a = CandidateEnrollment.objects.create(
            campaign=self.campaign_org_a,
            candidate=self.candidate_a,
            status="in_progress",
        )
        self.enrollment_org_b = CandidateEnrollment.objects.create(
            campaign=self.campaign_org_b,
            candidate=self.candidate_b,
            status="in_progress",
        )
        self.case_org_a = VettingCase.objects.create(
            organization=self.org_a,
            applicant=self.applicant,
            candidate_enrollment=self.enrollment_org_a,
            assigned_to=self.internal_a,
            position_applied="Policy Analyst",
            department="Secretariat",
            priority="medium",
            status="under_review",
        )
        self.case_org_b = VettingCase.objects.create(
            organization=self.org_b,
            applicant=self.applicant,
            candidate_enrollment=self.enrollment_org_b,
            assigned_to=self.internal_b,
            position_applied="Policy Analyst",
            department="Secretariat",
            priority="medium",
            status="under_review",
        )

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def test_internal_list_is_scoped_to_org_memberships(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.get("/api/applications/cases/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._extract_results(response)}
        self.assertIn(str(self.case_org_a.id), ids)
        self.assertNotIn(str(self.case_org_b.id), ids)

    def test_internal_can_create_case_for_same_org_foreign_campaign(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.post(
            "/api/applications/cases/",
            {
                "applicant": str(self.applicant.id),
                "candidate_enrollment": str(self.enrollment_org_a.id),
                "position_applied": "Analyst",
                "department": "Operations",
                "job_description": "Cross-team vetting support",
                "priority": "medium",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        created = VettingCase.objects.get(id=response.json()["id"])
        self.assertEqual(created.organization_id, self.org_a.id)

    def test_internal_cannot_create_case_for_other_org(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.post(
            "/api/applications/cases/",
            {
                "applicant": str(self.applicant.id),
                "candidate_enrollment": str(self.enrollment_org_b.id),
                "position_applied": "Analyst",
                "department": "Operations",
                "job_description": "Cross-org forbidden path",
                "priority": "medium",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_membershipless_internal_list_only_shows_assigned_legacy_cases(self):
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        membershipless_internal = User.objects.create_user(
            email="apps_scope_legacy_only@example.com",
            password="Pass1234!",
            first_name="Apps",
            last_name="LegacyOnly",
            user_type="internal",
        )
        membershipless_internal.groups.add(vetting_officer_group)
        legacy_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=membershipless_internal,
            position_applied="Legacy Analyst",
            department="Secretariat",
            priority="medium",
            status="under_review",
        )
        org_case = VettingCase.objects.create(
            organization=self.org_a,
            applicant=self.applicant,
            assigned_to=membershipless_internal,
            position_applied="Scoped Analyst",
            department="Secretariat",
            priority="medium",
            status="under_review",
        )

        self.client.force_authenticate(membershipless_internal)
        response = self.client.get("/api/applications/cases/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._extract_results(response)}
        self.assertIn(str(legacy_case.id), ids)
        self.assertNotIn(str(org_case.id), ids)
        self.assertNotIn(str(self.case_org_a.id), ids)
        self.assertNotIn(str(self.case_org_b.id), ids)

    def test_membershipless_internal_cannot_create_case_without_org_context(self):
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        membershipless_internal = User.objects.create_user(
            email="apps_scope_create_denied@example.com",
            password="Pass1234!",
            first_name="Apps",
            last_name="CreateDenied",
            user_type="internal",
        )
        membershipless_internal.groups.add(vetting_officer_group)
        self.client.force_authenticate(membershipless_internal)
        response = self.client.post(
            "/api/applications/cases/",
            {
                "applicant": str(self.applicant.id),
                "position_applied": "Membershipless Case",
                "department": "Operations",
                "job_description": "Should require org context",
                "priority": "medium",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class VerificationGatewayFoundationTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            code="verif-gateway-org",
            name="Verification Gateway Org",
            organization_type="agency",
            is_active=True,
        )
        self.hr = User.objects.create_user(
            email="gateway.hr@example.com",
            password="Pass1234!",
            first_name="Gateway",
            last_name="Reviewer",
            user_type="internal",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="gateway.applicant@example.com",
            password="Pass1234!",
            first_name="Gateway",
            last_name="Applicant",
            user_type="applicant",
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=self.org,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )
        self.case = VettingCase.objects.create(
            organization=self.org,
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="Policy Officer",
            department="Governance",
            priority="high",
            status="under_review",
            document_authenticity_score=88.0,
            consistency_score=82.0,
            fraud_risk_score=14.0,
            interview_score=79.0,
            documents_uploaded=True,
            documents_verified=True,
            interview_completed=True,
        )
        self.identity_source = VerificationSource.objects.create(
            organization=self.org,
            key="national-id-registry",
            name="National Identity Registry",
            source_category="national_identity",
            integration_mode="mock",
            advisory_only=True,
            is_active=True,
            created_by=self.hr,
        )
        self.client.force_authenticate(self.hr)

    def test_create_verification_request_is_idempotent_per_case_source_key(self):
        request_a, created_a = create_verification_request(
            case=self.case,
            source=self.identity_source,
            requested_by=self.hr,
            idempotency_key="case-source-1",
            subject_identifiers={"national_id": "NIN-001"},
            request_payload={"subject": {"full_name": "Gateway Applicant"}},
        )
        request_b, created_b = create_verification_request(
            case=self.case,
            source=self.identity_source,
            requested_by=self.hr,
            idempotency_key="case-source-1",
            subject_identifiers={"national_id": "NIN-001"},
        )

        self.assertTrue(created_a)
        self.assertFalse(created_b)
        self.assertEqual(request_a.id, request_b.id)
        self.assertEqual(str(request_a.organization_id), str(self.org.id))
        self.assertEqual(VerificationRequest.objects.filter(case=self.case, source=self.identity_source).count(), 1)

    def test_record_verification_result_normalizes_and_updates_request_status(self):
        verification_request, _ = create_verification_request(
            case=self.case,
            source=self.identity_source,
            requested_by=self.hr,
            idempotency_key="result-case-1",
            subject_identifiers={"national_id": "NIN-001"},
        )
        result = record_verification_result(
            verification_request=verification_request,
            result_status="verified",
            recommendation="review",
            confidence_score=96.5,
            advisory_flags=[{"code": "name_variation", "severity": "warning"}],
            evidence_summary={"matched_fields": 4, "mismatched_fields": 1},
            normalized_evidence={"identity_match": True, "name_match": False},
            raw_payload={"raw_provider_blob": {"sensitive": "redacted"}},
            raw_payload_redacted=True,
            provider_reference="NID-REF-123",
            actor=self.hr,
        )

        verification_request.refresh_from_db()
        self.assertEqual(verification_request.status, "completed")
        self.assertEqual(result.result_status, "verified")
        self.assertEqual(result.recommendation, "review")
        self.assertEqual(result.provider_reference, "NID-REF-123")
        self.assertEqual(len(result.advisory_flags), 1)
        self.assertTrue(result.raw_payload_redacted)

        snapshot = build_case_external_verification_snapshot(self.case)
        self.assertEqual(snapshot["total_requests"], 1)
        self.assertEqual(snapshot["completed"], 1)
        self.assertEqual(snapshot["sources_with_advisory_flags"], 1)
        self.assertEqual(snapshot["advisory_flags_total"], 1)
        self.assertEqual(snapshot["latest_by_source"][0]["source_key"], "national-id-registry")
        self.assertEqual(snapshot["latest_by_source"][0]["advisory_flags_count"], 1)

        if "apps.audit" in settings.INSTALLED_APPS:
            from apps.audit.models import AuditLog

            audit_row = (
                AuditLog.objects.filter(entity_type="ExternalVerificationResult", entity_id=str(result.id))
                .order_by("-created_at")
                .first()
            )
            self.assertIsNotNone(audit_row)
            changes = audit_row.changes or {}
            self.assertEqual(changes.get("event"), "verification_gateway_result_recorded")
            self.assertNotIn("raw_payload", changes)

    def test_verification_status_includes_external_verification_summary(self):
        verification_request, _ = create_verification_request(
            case=self.case,
            source=self.identity_source,
            requested_by=self.hr,
            idempotency_key="status-case-1",
            subject_identifiers={"national_id": "NIN-009"},
        )
        record_verification_result(
            verification_request=verification_request,
            result_status="inconclusive",
            recommendation="escalate",
            confidence_score=61.0,
            advisory_flags=[{"code": "record_gap", "severity": "warning"}],
            evidence_summary={"record_found": False},
            normalized_evidence={"record_status": "partial"},
            raw_payload={"status": "partial_record"},
            raw_payload_redacted=True,
            actor=self.hr,
        )

        response = self.client.get(
            f"/api/applications/cases/{self.case.id}/verification-status/",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("external_verification", payload)
        external = payload["external_verification"]
        self.assertEqual(external["total_requests"], 1)
        self.assertEqual(external["completed"], 1)
        self.assertEqual(external["sources_with_advisory_flags"], 1)
        self.assertEqual(external["latest_by_source"][0]["result_status"], "inconclusive")
        self.assertNotIn("raw_payload", external["latest_by_source"][0])

    def test_decision_engine_evidence_snapshot_includes_external_verification_context(self):
        verification_request, _ = create_verification_request(
            case=self.case,
            source=self.identity_source,
            requested_by=self.hr,
            idempotency_key="decision-case-1",
            subject_identifiers={"national_id": "NIN-777"},
        )
        record_verification_result(
            verification_request=verification_request,
            result_status="mismatch",
            recommendation="review",
            confidence_score=82.0,
            advisory_flags=[{"code": "name_mismatch", "severity": "warning"}],
            evidence_summary={"name_match": False},
            normalized_evidence={"name_match": False, "dob_match": True},
            raw_payload={"provider_status": "mismatch"},
            raw_payload_redacted=True,
            actor=self.hr,
        )

        rubric = VettingRubric.objects.create(
            organization=self.org,
            name="Gateway Decision Rubric",
            description="Rubric for gateway decision snapshot test",
            rubric_type="general",
            document_authenticity_weight=25,
            consistency_weight=20,
            fraud_detection_weight=20,
            interview_weight=25,
            manual_review_weight=10,
            passing_score=70,
            auto_approve_threshold=90,
            auto_reject_threshold=40,
            minimum_document_score=60,
            maximum_fraud_score=50,
            require_interview=True,
            critical_flags_auto_fail=True,
            max_unresolved_flags=2,
            is_active=True,
            created_by=self.hr,
        )
        evaluation = RubricEvaluationEngine(case=self.case, rubric=rubric).evaluate(evaluated_by=self.hr)
        recommendation = VettingDecisionEngine.generate_recommendation(evaluation=evaluation, actor=self.hr)

        external_snapshot = (recommendation.evidence_snapshot or {}).get("external_verifications") or {}
        self.assertEqual(external_snapshot.get("total_requests"), 1)
        self.assertEqual(external_snapshot.get("sources_with_advisory_flags"), 1)
        warning_codes = {item.get("code") for item in recommendation.warnings or []}
        self.assertIn("external_verification_flags", warning_codes)


class ApplicationsAliasContractTests(APITestCase):
    def setUp(self):
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.internal_user = User.objects.create_user(
            email="applications_alias_internal@example.com",
            password="Pass1234!",
            first_name="Applications",
            last_name="Alias",
            user_type="internal",
        )
        self.internal_user.groups.add(vetting_officer_group)
        self.applicant = User.objects.create_user(
            email="applications_alias_applicant@example.com",
            password="Pass1234!",
            first_name="Alias",
            last_name="Applicant",
            user_type="applicant",
        )
        self.campaign = VettingCampaign.objects.create(
            name="Executive Office Exercise",
            status="active",
            initiated_by=self.internal_user,
        )
        self.candidate = Candidate.objects.create(
            first_name="Alias",
            last_name="Candidate",
            email="applications_alias_candidate@example.com",
        )
        self.enrollment = CandidateEnrollment.objects.create(
            campaign=self.campaign,
            candidate=self.candidate,
            status="in_progress",
        )
        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            candidate_enrollment=self.enrollment,
            assigned_to=self.internal_user,
            position_applied="Director of Operations",
            department="Executive Office",
            status="under_review",
            priority="medium",
        )
        self.client.force_authenticate(self.internal_user)

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_government_vetting_dossiers_alias_endpoint_exposes_additive_fields(self):
        response = self.client.get("/api/government/vetting-dossiers/")
        self.assertEqual(response.status_code, 200)
        items = self._items(response.json())
        target = next((item for item in items if item["id"] == str(self.case.id)), None)
        self.assertIsNotNone(target)
        self.assertEqual(target["vetting_dossier_id"], self.case.case_id)
        self.assertEqual(target["vetting_dossier_status"], self.case.status)
        self.assertEqual(target["appointment_exercise_id"], str(self.campaign.id))
        self.assertEqual(target["appointment_exercise_name"], self.campaign.name)
        self.assertEqual(target["office_title"], self.case.position_applied)



