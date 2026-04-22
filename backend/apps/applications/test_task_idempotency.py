"""Tests for verify_document_async idempotency and placeholder pipeline warning."""

from io import BytesIO
from unittest.mock import MagicMock, PropertyMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.applications.models import Document, VerificationResult, VettingCase
from apps.applications.tasks import (
    _build_placeholder_analysis,
    _run_document_analysis,
    verify_document_async,
)
from apps.users.models import User
from apps.billing.models import BillingSubscription
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.tenants.models import Organization
from apps.governance.models import OrganizationMembership


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_officer(email="officer@idempotency.example.com"):
    return User.objects.create_user(
        email=email,
        password="Pass1234!",
        user_type="internal",
        first_name="Test",
        last_name="Officer",
    )


def _make_org():
    return Organization.objects.create(
        name="Idempotency Test Agency",
        code="idem-test-agency",
        organization_type="agency",
        is_active=True,
    )


def _make_subscription(org):
    return BillingSubscription.objects.create(
        provider="sandbox",
        status="complete",
        payment_status="paid",
        plan_id="starter",
        plan_name="Starter",
        billing_cycle="monthly",
        payment_method="card",
        amount_usd="149.00",
        reference=f"OVS-IDEM-STARTER-{str(org.id)[:8]}",
    )


def _make_case(officer, org):
    candidate = Candidate.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe.idem@example.com",
        consent_ai_processing=True,
    )
    campaign = VettingCampaign.objects.create(
        name="Idempotency Test Campaign",
        initiated_by=officer,
    )
    enrollment = CandidateEnrollment.objects.create(
        campaign=campaign,
        candidate=candidate,
        status="in_progress",
    )
    return VettingCase.objects.create(
        applicant=officer,
        candidate_enrollment=enrollment,
        assigned_to=officer,
        position_applied="Test Position",
        priority="medium",
        status="document_upload",
    )


def _make_document(case, status="pending", filename="passport.pdf"):
    return Document.objects.create(
        case=case,
        document_type="passport",
        original_filename=filename,
        file=SimpleUploadedFile(filename, b"%PDF-1.4 test content", content_type="application/pdf"),
        file_size=21,
        mime_type="application/pdf",
        status=status,
    )


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class VerifyDocumentIdempotencyTests(TestCase):
    def setUp(self):
        self.officer = _make_officer()
        self.org = _make_org()
        _make_subscription(self.org)
        OrganizationMembership.objects.create(
            user=self.officer,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )
        self.case = _make_case(self.officer, self.org)

    def test_skips_already_verified_document(self):
        doc = _make_document(self.case, status="verified")
        result = verify_document_async(doc.id)
        self.assertTrue(result["success"])
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result["status"], "verified")

    def test_skips_already_flagged_document(self):
        doc = _make_document(self.case, status="flagged")
        result = verify_document_async(doc.id)
        self.assertTrue(result["success"])
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result["status"], "flagged")

    def test_skip_does_not_create_duplicate_verification_result(self):
        doc = _make_document(self.case, status="verified")
        VerificationResult.objects.create(
            document=doc,
            authenticity_score=92.0,
            authenticity_confidence=80.0,
            fraud_risk_score=18.0,
            fraud_prediction="legitimate",
            is_authentic=True,
        )
        initial_count = VerificationResult.objects.filter(document=doc).count()

        # Run twice — both should skip
        verify_document_async(doc.id)
        verify_document_async(doc.id)

        self.assertEqual(VerificationResult.objects.filter(document=doc).count(), initial_count)

    def test_processes_pending_document(self):
        doc = _make_document(self.case, status="pending")
        result = verify_document_async(doc.id)
        self.assertTrue(result["success"])
        self.assertFalse(result.get("skipped", False))
        doc.refresh_from_db()
        self.assertIn(doc.status, {"verified", "flagged"})

    def test_returns_error_for_nonexistent_document(self):
        result = verify_document_async(999_999_999)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_processing_status_is_not_skipped(self):
        doc = _make_document(self.case, status="processing")
        result = verify_document_async(doc.id)
        # "processing" is not in the skip set — should process normally
        self.assertFalse(result.get("skipped", False))


# ---------------------------------------------------------------------------
# Placeholder analysis tests
# ---------------------------------------------------------------------------

class PlaceholderAnalysisTests(TestCase):
    def setUp(self):
        self.officer = _make_officer("officer2@idem.example.com")
        self.org = _make_org()
        _make_subscription(self.org)
        OrganizationMembership.objects.create(
            user=self.officer,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )
        self.case = _make_case(self.officer, self.org)

    def test_emits_warning_log(self):
        doc = _make_document(self.case, filename="clean_passport.pdf")
        with self.assertLogs("apps.applications.tasks", level="WARNING") as log_ctx:
            _build_placeholder_analysis(doc)
        self.assertTrue(
            any("PLACEHOLDER" in msg for msg in log_ctx.output),
            f"Expected PLACEHOLDER warning. Got: {log_ctx.output}",
        )

    def test_includes_document_id_in_warning(self):
        doc = _make_document(self.case, filename="doc.pdf")
        with self.assertLogs("apps.applications.tasks", level="WARNING") as log_ctx:
            _build_placeholder_analysis(doc)
        self.assertTrue(any(str(doc.id) in msg for msg in log_ctx.output))

    def test_clean_filename_returns_high_authenticity(self):
        doc = _make_document(self.case, filename="clean_passport.pdf")
        result = _build_placeholder_analysis(doc)
        self.assertEqual(result["authenticity_score"], 92.0)
        self.assertEqual(result["fraud_risk_score"], 18.0)
        self.assertTrue(result["is_authentic"])

    def test_scan_filename_returns_reduced_scores(self):
        doc = _make_document(self.case, filename="document_scan.pdf")
        result = _build_placeholder_analysis(doc)
        self.assertEqual(result["authenticity_score"], 75.0)
        self.assertEqual(result["fraud_risk_score"], 35.0)

    def test_edited_filename_returns_low_authenticity(self):
        doc = _make_document(self.case, filename="passport_edited.pdf")
        result = _build_placeholder_analysis(doc)
        self.assertEqual(result["authenticity_score"], 48.0)
        self.assertEqual(result["fraud_risk_score"], 82.0)
        self.assertFalse(result["is_authentic"])

    def test_result_contains_pipeline_marker(self):
        doc = _make_document(self.case, filename="doc.pdf")
        result = _build_placeholder_analysis(doc)
        self.assertEqual(result["detailed_results"]["pipeline"], "placeholder")

    def test_result_structure_has_required_keys(self):
        doc = _make_document(self.case, filename="doc.pdf")
        result = _build_placeholder_analysis(doc)
        required_keys = {
            "ocr_text", "ocr_confidence", "authenticity_score",
            "is_authentic", "fraud_risk_score", "fraud_prediction",
            "fraud_indicators", "detailed_results",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")


# ---------------------------------------------------------------------------
# _run_document_analysis — AI/ML pipeline wiring tests
# ---------------------------------------------------------------------------

_AI_ML_SUCCESS_RESULT = {
    "success": True,
    "case_id": "test-case-id",
    "document_type": "passport",
    "results": {
        "ocr": {"text": "John Doe DOB 1990-01-01", "confidence": 0.97, "language": "en"},
        "authenticity": {
            "overall_score": 91.5,
            "deep_learning": {"confidence": 0.93},
            "computer_vision": {},
        },
        "signature": {},
        "document_classification": {},
        "document_type_alignment": {},
        "overall_score": 89.0,
        "recommendation": "APPROVE",
        "automated_decision_allowed": True,
        "decision_constraints": [],
    },
    "processing_time": 1.23,
}


@override_settings(PLACEHOLDER_ML_ENABLED=False)
class RunDocumentAnalysisTests(TestCase):
    def setUp(self):
        self.officer = _make_officer("officer3@ai.example.com")
        self.org = _make_org()
        _make_subscription(self.org)
        from apps.governance.models import OrganizationMembership
        OrganizationMembership.objects.create(
            user=self.officer,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )
        self.case = _make_case(self.officer, self.org)
        self.doc = _make_document(self.case, filename="passport.pdf")

    @patch("apps.applications.tasks.ImproperlyConfigured", ImproperlyConfigured)
    @patch("ai_ml_services.service.verify_document", return_value=_AI_ML_SUCCESS_RESULT)
    def test_returns_structured_analysis_on_success(self, mock_verify):
        with patch.object(type(self.doc.file), "path", new_callable=PropertyMock, return_value="/tmp/passport.pdf"):
            result = _run_document_analysis(self.doc)
        self.assertIn("authenticity_score", result)
        self.assertAlmostEqual(result["authenticity_score"], 91.5)
        self.assertEqual(result["fraud_prediction"], "legitimate")
        self.assertTrue(result["is_authentic"])
        self.assertEqual(result["detailed_results"]["pipeline"], "ai_ml_services")
        self.assertEqual(result["detailed_results"]["recommendation"], "APPROVE")

    @patch("apps.applications.tasks.ImproperlyConfigured", ImproperlyConfigured)
    @patch("ai_ml_services.service.verify_document", return_value=_AI_ML_SUCCESS_RESULT)
    def test_maps_approve_to_legitimate_fraud_prediction(self, mock_verify):
        with patch.object(type(self.doc.file), "path", new_callable=PropertyMock, return_value="/tmp/passport.pdf"):
            result = _run_document_analysis(self.doc)
        self.assertEqual(result["fraud_prediction"], "legitimate")

    @patch("apps.applications.tasks.ImproperlyConfigured", ImproperlyConfigured)
    @patch("ai_ml_services.service.verify_document", return_value={
        **_AI_ML_SUCCESS_RESULT,
        "results": {**_AI_ML_SUCCESS_RESULT["results"], "recommendation": "REJECT"},
    })
    def test_maps_reject_to_fraudulent_fraud_prediction(self, mock_verify):
        with patch.object(type(self.doc.file), "path", new_callable=PropertyMock, return_value="/tmp/passport.pdf"):
            result = _run_document_analysis(self.doc)
        self.assertEqual(result["fraud_prediction"], "fraudulent")
        self.assertFalse(result["is_authentic"])

    @patch("apps.applications.tasks.ImproperlyConfigured", ImproperlyConfigured)
    @patch("ai_ml_services.service.verify_document", return_value={
        **_AI_ML_SUCCESS_RESULT,
        "results": {**_AI_ML_SUCCESS_RESULT["results"], "recommendation": "MANUAL_REVIEW"},
    })
    def test_maps_manual_review_to_suspicious_fraud_prediction(self, mock_verify):
        with patch.object(type(self.doc.file), "path", new_callable=PropertyMock, return_value="/tmp/passport.pdf"):
            result = _run_document_analysis(self.doc)
        self.assertEqual(result["fraud_prediction"], "suspicious")

    @override_settings(PLACEHOLDER_ML_ENABLED=False)
    def test_raises_improperly_configured_when_ml_fails_and_placeholder_disabled(self):
        with patch("ai_ml_services.service.verify_document", side_effect=RuntimeError("model not loaded")):
            with patch.object(type(self.doc.file), "path", new_callable=PropertyMock, return_value="/tmp/passport.pdf"):
                with self.assertRaises(ImproperlyConfigured):
                    _run_document_analysis(self.doc)

    @override_settings(PLACEHOLDER_ML_ENABLED=True)
    def test_falls_back_to_placeholder_when_ml_fails_and_placeholder_enabled(self):
        with patch("ai_ml_services.service.verify_document", side_effect=RuntimeError("model not loaded")):
            with patch.object(type(self.doc.file), "path", new_callable=PropertyMock, return_value="/tmp/passport.pdf"):
                with self.assertLogs("apps.applications.tasks", level="WARNING"):
                    result = _run_document_analysis(self.doc)
        self.assertEqual(result["detailed_results"]["pipeline"], "placeholder")

    @override_settings(PLACEHOLDER_ML_ENABLED=False)
    def test_raises_runtime_error_for_cloud_storage_documents(self):
        """Documents stored in S3 have no local .path — should raise RuntimeError."""
        with patch.object(type(self.doc.file), "path", property(lambda self: (_ for _ in ()).throw(ValueError("no local path")))):
            with self.assertRaises((RuntimeError, ImproperlyConfigured)):
                _run_document_analysis(self.doc)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, PLACEHOLDER_ML_ENABLED=False)
class VerifyDocumentAsyncAiMlIntegrationTests(TestCase):
    """
    Integration-style tests for verify_document_async with the real AI/ML pipeline mocked.
    These run in CELERY_TASK_ALWAYS_EAGER mode so the task executes synchronously.
    For true broker integration tests, run against a live Redis instance in CI.
    """

    def setUp(self):
        self.officer = _make_officer("officer4@integration.example.com")
        self.org = _make_org()
        _make_subscription(self.org)
        from apps.governance.models import OrganizationMembership
        OrganizationMembership.objects.create(
            user=self.officer,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )
        self.case = _make_case(self.officer, self.org)

    @patch("ai_ml_services.service.verify_document", return_value=_AI_ML_SUCCESS_RESULT)
    def test_task_creates_verification_result_via_ai_ml(self, mock_verify):
        doc = _make_document(self.case, filename="id_card.pdf")
        with patch.object(type(doc.file), "path", new_callable=PropertyMock, return_value="/tmp/id_card.pdf"):
            result = verify_document_async(doc.id)
        self.assertTrue(result["success"])
        vr = VerificationResult.objects.get(document=doc)
        self.assertAlmostEqual(vr.authenticity_score, 91.5)
        self.assertEqual(vr.fraud_prediction, "legitimate")
        self.assertEqual(vr.detailed_results["pipeline"], "ai_ml_services")

    @patch("ai_ml_services.service.verify_document", side_effect=RuntimeError("no model"))
    def test_task_fails_when_ai_ml_errors_and_placeholder_disabled(self, mock_verify):
        doc = _make_document(self.case, filename="bad_doc.pdf")
        with patch.object(type(doc.file), "path", new_callable=PropertyMock, return_value="/tmp/bad_doc.pdf"):
            with self.assertRaises(ImproperlyConfigured):
                verify_document_async(doc.id)
