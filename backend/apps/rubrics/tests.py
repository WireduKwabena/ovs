from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.authentication.permissions import (
    RECENT_AUTH_REQUIRED_CODE,
    RECENT_AUTH_SESSION_KEY,
)
from apps.billing.models import BillingSubscription
from apps.governance.models import Organization, OrganizationMembership
from apps.rubrics.models import RubricEvaluation, VettingDecisionOverride, VettingDecisionRecommendation, VettingRubric
from apps.rubrics.tasks import auto_assign_rubric, evaluate_case_with_rubric


class RubricsApiTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            code="rubrics-api-org",
            name="Rubrics API Org",
            organization_type="agency",
            is_active=True,
        )
        self.hr = User.objects.create_user(
            email="hr_rubrics_test@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Rubrics",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="app_rubrics_test@example.com",
            password="Pass1234!",
            first_name="Applicant",
            last_name="Rubrics",
            user_type="applicant",
        )
        self.admin = User.objects.create_user(
            email="admin_rubrics_test@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="Rubrics",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
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
            position_applied="Risk Analyst",
            department="Compliance",
            priority="high",
            status="under_review",
            document_authenticity_score=86,
            consistency_score=80,
            fraud_risk_score=18,
            interview_score=74,
        )
        self._authenticate_with_recent_auth(self.hr)

    def _authenticate_with_recent_auth(self, user: User, *, age_seconds: int = 0):
        self.client.force_authenticate(user)
        session = self.client.session
        session[RECENT_AUTH_SESSION_KEY] = int(
            (timezone.now() - timedelta(seconds=max(age_seconds, 0))).timestamp()
        )
        session.save()

    def _authenticate_without_recent_auth(self, user: User):
        self.client.force_authenticate(user)
        session = self.client.session
        session.pop(RECENT_AUTH_SESSION_KEY, None)
        session.save()

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
            reference=f"OVS-RUBRIC-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    def _rubric_payload(self, name: str) -> dict:
        return {
            "name": name,
            "description": "Baseline rubric for tests",
            "rubric_type": "general",
            "document_authenticity_weight": 25,
            "consistency_weight": 20,
            "fraud_detection_weight": 20,
            "interview_weight": 25,
            "manual_review_weight": 10,
            "passing_score": 70,
            "auto_approve_threshold": 90,
            "auto_reject_threshold": 40,
            "minimum_document_score": 60,
            "maximum_fraud_score": 50,
            "require_interview": True,
            "critical_flags_auto_fail": True,
            "max_unresolved_flags": 2,
            "is_active": True,
            "is_default": False,
        }

    def _create_rubric(self, name: str, *, active_org_id: str | None = None) -> int:
        request_kwargs = {}
        if active_org_id:
            request_kwargs["HTTP_X_ACTIVE_ORGANIZATION_ID"] = str(active_org_id)
        response = self.client.post(
            "/api/rubrics/vetting-rubrics/",
            self._rubric_payload(name),
            format="json",
            **request_kwargs,
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_create_rubric_with_nested_criteria_is_atomic_success(self):
        payload = self._rubric_payload("Atomic Nested Rubric")
        payload["criteria"] = [
            {
                "name": "Document Confidence",
                "description": "Document integrity confidence signal",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 55,
                "minimum_score": 65,
                "is_mandatory": True,
                "display_order": 0,
            },
            {
                "name": "Interview Coherence",
                "description": "Interview answer consistency and coherence",
                "criteria_type": "interview",
                "scoring_method": "manual_rating",
                "weight": 45,
                "minimum_score": 60,
                "is_mandatory": False,
                "display_order": 1,
            },
        ]

        response = self.client.post("/api/rubrics/vetting-rubrics/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        rubric_id = response.json()["id"]
        self.assertEqual(len(response.json().get("criteria", [])), 2)
        self.assertEqual(
            VettingRubric.objects.get(id=rubric_id).criteria.count(),
            2,
        )

    def test_create_rubric_with_duplicate_nested_criteria_names_rolls_back(self):
        payload = self._rubric_payload("Atomic Duplicate Rubric")
        payload["criteria"] = [
            {
                "name": "Integrity Check",
                "description": "First criterion",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 50,
                "minimum_score": 60,
                "is_mandatory": True,
                "display_order": 0,
            },
            {
                "name": " integrity check ",
                "description": "Duplicate by normalization",
                "criteria_type": "consistency",
                "scoring_method": "ai_score",
                "weight": 50,
                "minimum_score": 60,
                "is_mandatory": False,
                "display_order": 1,
            },
        ]

        response = self.client.post("/api/rubrics/vetting-rubrics/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("criteria", response.json())
        self.assertFalse(VettingRubric.objects.filter(name="Atomic Duplicate Rubric").exists())

    def test_create_rubric_evaluate_case_and_override_criterion(self):
        rubric_id = self._create_rubric("Test Rubric")

        add_criterion = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/criteria/",
            {
                "name": "Document Trust",
                "description": "Validate document authenticity confidence",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 40,
                "minimum_score": 65,
                "is_mandatory": True,
                "display_order": 1,
            },
            format="json",
        )
        self.assertEqual(add_criterion.status_code, 201)
        criterion_id = add_criterion.json()["id"]

        evaluate = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        self.assertEqual(evaluate.status_code, 200)
        evaluation_id = evaluate.json()["id"]
        self.assertIsNotNone(evaluate.json()["total_weighted_score"])

        override = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-criterion/",
            {
                "criterion_id": criterion_id,
                "overridden_score": 50,
                "justification": "Manual correction for known OCR noise.",
            },
            format="json",
        )
        self.assertEqual(override.status_code, 201)

        evaluation = RubricEvaluation.objects.get(id=evaluation_id)
        self.assertTrue(evaluation.requires_manual_review)
        self.assertEqual(evaluation.status, "requires_review")

    def test_evaluate_case_returns_structured_trace_and_explanation(self):
        rubric_id = self._create_rubric("Trace Rubric")
        self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/criteria/",
            {
                "name": "Document Trust",
                "description": "Document authenticity confidence",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 50,
                "minimum_score": 65,
                "is_mandatory": True,
                "display_order": 1,
            },
            format="json",
        )

        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("decision_explanation", payload)
        self.assertIn("evaluation_trace", payload)
        self.assertIn("scoring", payload["evaluation_trace"])
        self.assertIn("components", payload["evaluation_trace"])
        self.assertEqual(payload["evaluation_trace"]["ai_signals"]["advisory_only"], True)
        self.assertIsNotNone(payload.get("decision_recommendation"))
        self.assertTrue(payload["decision_recommendation"]["advisory_only"])
        self.assertIn(
            payload["decision_recommendation"]["recommendation_status"],
            {"recommend_approve", "recommend_reject", "recommend_manual_review"},
        )

    def test_async_evaluation_rejects_ai_signals_payload(self):
        rubric_id = self._create_rubric("Async AI Rubric")
        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {
                "case_id": self.case.id,
                "async": True,
                "ai_signals": {"source": "test-agent", "criteria": {}},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("ai_signals", response.json()["error"])

    @patch("apps.rubrics.views.evaluate_case_with_rubric.delay")
    @override_settings(
        BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_RUBRIC_EVALUATION_PER_MONTH=1,
    )
    def test_evaluate_case_blocks_when_org_rubric_quota_exceeded(self, mock_delay):
        organization = Organization.objects.create(
            code="rubric-quota-org",
            name="Rubric Quota Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=False,
        )
        self._create_org_subscription(organization, plan_id="starter")

        rubric_id = self._create_rubric(
            "Scoped Rubric Quota",
            active_org_id=str(organization.id),
        )
        rubric = VettingRubric.objects.get(id=rubric_id)

        used_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="Analyst",
            department="Compliance",
            priority="medium",
            status="under_review",
        )
        RubricEvaluation.objects.create(
            case=used_case,
            rubric=rubric,
            status="completed",
            evaluated_by=self.hr,
            total_weighted_score=82.0,
            passes_threshold=True,
            final_decision="manual_approved",
        )

        target_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="Investigator",
            department="Compliance",
            priority="medium",
            status="under_review",
        )
        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": target_case.id},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "vetting_operation_quota_exceeded")
        self.assertEqual((payload.get("quota") or {}).get("operation"), "rubric_evaluation")
        mock_delay.assert_not_called()

    def test_ai_signals_are_advisory_only_and_do_not_auto_approve(self):
        rubric_id = self._create_rubric("Advisory AI Rubric")
        low_case = VettingCase.objects.create(
            organization=self.org,
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="Assistant Analyst",
            department="Compliance",
            priority="medium",
            status="under_review",
            document_authenticity_score=25,
            consistency_score=20,
            fraud_risk_score=80,
            interview_score=20,
        )
        self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/criteria/",
            {
                "name": "Behavioral Fit",
                "description": "Behavioral signal",
                "criteria_type": "behavioral",
                "scoring_method": "ai_score",
                "weight": 30,
                "minimum_score": 60,
                "is_mandatory": False,
                "display_order": 1,
            },
            format="json",
        )

        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {
                "case_id": low_case.id,
                "ai_signals": {
                    "source": "ai-assessor-v1",
                    "summary": "High confidence potential despite low baseline.",
                    "criteria": {"behavioral fit": {"score": 98, "confidence": 0.92}},
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(payload["final_decision"], "auto_approved")
        self.assertTrue(payload["evaluation_trace"]["ai_signals"]["advisory_only"])
        self.assertEqual(payload["evaluation_trace"]["ai_signals"]["source"], "ai-assessor-v1")
        self.assertEqual(payload["decision_recommendation"]["advisory_only"], True)

    def test_decision_recommendation_endpoint_returns_latest_recommendation(self):
        rubric_id = self._create_rubric("Decision Endpoint Rubric")
        evaluate = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        self.assertEqual(evaluate.status_code, 200)
        evaluation_id = evaluate.json()["id"]
        recommendation_id = evaluate.json()["decision_recommendation"]["id"]

        detail = self.client.get(f"/api/rubrics/evaluations/{evaluation_id}/decision-recommendation/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], recommendation_id)
        self.assertTrue(detail.json()["is_latest"])

    def test_rerun_creates_new_latest_decision_recommendation(self):
        rubric_id = self._create_rubric("Decision Rerun Rubric")
        evaluate = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        self.assertEqual(evaluate.status_code, 200)
        evaluation_id = evaluate.json()["id"]

        first_recommendation = VettingDecisionRecommendation.objects.filter(
            rubric_evaluation_id=evaluation_id,
            is_latest=True,
        ).first()
        self.assertIsNotNone(first_recommendation)

        rerun = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/rerun/",
            {},
            format="json",
        )
        self.assertEqual(rerun.status_code, 200)

        latest = VettingDecisionRecommendation.objects.filter(
            rubric_evaluation_id=evaluation_id,
            is_latest=True,
        ).first()
        self.assertIsNotNone(latest)
        self.assertNotEqual(latest.id, first_recommendation.id)
        first_recommendation.refresh_from_db()
        self.assertFalse(first_recommendation.is_latest)

    def test_override_decision_endpoint_records_override(self):
        rubric_id = self._create_rubric("Decision Override Rubric")
        evaluate = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        self.assertEqual(evaluate.status_code, 200)
        evaluation_id = evaluate.json()["id"]

        override = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-decision/",
            {
                "recommendation_status": "recommend_manual_review",
                "rationale": "Final governance review requested by committee secretariat.",
            },
            format="json",
        )
        self.assertEqual(override.status_code, 200)
        recommendation = VettingDecisionRecommendation.objects.filter(
            rubric_evaluation_id=evaluation_id,
            is_latest=True,
        ).first()
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.recommendation_status, "recommend_manual_review")
        self.assertEqual(
            VettingDecisionOverride.objects.filter(recommendation=recommendation).count(),
            1,
        )

    def test_override_decision_requires_recent_auth(self):
        rubric_id = self._create_rubric("Decision Override Step Up Rubric")
        evaluate = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        self.assertEqual(evaluate.status_code, 200)
        evaluation_id = evaluate.json()["id"]

        self._authenticate_without_recent_auth(self.hr)
        denied_missing = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-decision/",
            {
                "recommendation_status": "recommend_manual_review",
                "rationale": "Attempt without step-up auth.",
            },
            format="json",
        )
        self.assertEqual(denied_missing.status_code, 403)
        self.assertEqual((denied_missing.json() or {}).get("code"), RECENT_AUTH_REQUIRED_CODE)

        self._authenticate_with_recent_auth(self.hr, age_seconds=3600)
        denied_stale = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-decision/",
            {
                "recommendation_status": "recommend_manual_review",
                "rationale": "Attempt with stale step-up auth.",
            },
            format="json",
        )
        self.assertEqual(denied_stale.status_code, 403)
        self.assertEqual((denied_stale.json() or {}).get("code"), RECENT_AUTH_REQUIRED_CODE)

        self._authenticate_with_recent_auth(self.hr)
        allowed = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-decision/",
            {
                "recommendation_status": "recommend_manual_review",
                "rationale": "Fresh step-up auth accepted.",
            },
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)

    def test_override_records_trace_event(self):
        rubric_id = self._create_rubric("Override Trace Rubric")
        criterion_response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/criteria/",
            {
                "name": "Document Trust",
                "description": "Validate document authenticity confidence",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 40,
                "minimum_score": 65,
                "is_mandatory": True,
                "display_order": 1,
            },
            format="json",
        )
        criterion_id = criterion_response.json()["id"]

        evaluate_response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        evaluation_id = evaluate_response.json()["id"]

        override_response = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-criterion/",
            {
                "criterion_id": criterion_id,
                "overridden_score": 52,
                "justification": "Manual correction for source document artifact.",
            },
            format="json",
        )
        self.assertEqual(override_response.status_code, 201)
        evaluation = RubricEvaluation.objects.get(id=evaluation_id)
        trace = evaluation.criterion_scores.get("__trace__", {})
        events = trace.get("events", [])
        self.assertTrue(any(event.get("event_type") == "override_applied" for event in events))

    def test_override_rejects_out_of_range_score(self):
        rubric_id = self._create_rubric("Negative Test Rubric")
        criterion = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/criteria/",
            {
                "name": "Consistency Criterion",
                "description": "Check consistency",
                "criteria_type": "consistency",
                "scoring_method": "ai_score",
                "weight": 30,
                "minimum_score": 60,
                "is_mandatory": False,
                "display_order": 1,
            },
            format="json",
        )
        criterion_id = criterion.json()["id"]
        evaluation = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id},
            format="json",
        )
        evaluation_id = evaluation.json()["id"]

        bad_override = self.client.post(
            f"/api/rubrics/evaluations/{evaluation_id}/override-criterion/",
            {
                "criterion_id": criterion_id,
                "overridden_score": 101,
                "justification": "Invalid score test.",
            },
            format="json",
        )
        self.assertEqual(bad_override.status_code, 400)

    @patch("apps.rubrics.views.evaluate_case_with_rubric.delay")
    def test_evaluate_case_async_string_true_queues_task(self, mock_delay):
        rubric_id = self._create_rubric("Async Queue Rubric")

        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id, "async": "true"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["message"], "Evaluation queued.")
        mock_delay.assert_called_once_with(self.case.id, UUID(str(rubric_id)), self.hr.id)

    @patch("apps.rubrics.views.evaluate_case_with_rubric.delay")
    def test_evaluate_case_async_string_false_runs_synchronously(self, mock_delay):
        rubric_id = self._create_rubric("Async Sync Rubric")

        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{rubric_id}/evaluate-case/",
            {"case_id": self.case.id, "async": "false"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("id", response.json())
        mock_delay.assert_not_called()

    def test_hr_manager_can_list_rubrics(self):
        self._create_rubric("HR Access Rubric")
        response = self.client.get("/api/rubrics/vetting-rubrics/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        if isinstance(payload, list):
            self.assertGreaterEqual(len(payload), 1)
        else:
            self.assertIn("results", payload)
            self.assertGreaterEqual(len(payload["results"]), 1)

    def test_admin_can_create_rubric(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/rubrics/vetting-rubrics/",
            self._rubric_payload("Admin Access Rubric"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Admin Access Rubric")

    def test_applicant_cannot_access_rubrics_api(self):
        self.client.force_authenticate(self.applicant)

        list_response = self.client.get("/api/rubrics/vetting-rubrics/")
        self.assertEqual(list_response.status_code, 403)

        create_response = self.client.post(
            "/api/rubrics/vetting-rubrics/",
            self._rubric_payload("Applicant Forbidden Rubric"),
            format="json",
        )
        self.assertEqual(create_response.status_code, 403)


class RubricTaskTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            code="rubric-task-org",
            name="Rubric Task Org",
            organization_type="agency",
            is_active=True,
        )
        self.hr = User.objects.create_user(
            email="rubric-task-hr@example.com",
            password="Pass1234!",
            first_name="Task",
            last_name="HR",
            user_type="hr_manager",
            is_staff=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr,
            organization=self.org,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self.applicant = User.objects.create_user(
            email="rubric-task-applicant@example.com",
            password="Pass1234!",
            first_name="Task",
            last_name="Applicant",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
            organization=self.org,
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="Risk Analyst",
            department="Compliance",
            priority="high",
            status="under_review",
            document_authenticity_score=86,
            consistency_score=80,
            fraud_risk_score=18,
            interview_score=74,
        )
        self._create_org_subscription(self.org, plan_id="starter")
        self.default_rubric = VettingRubric.objects.create(
            name="Default Task Rubric",
            is_active=True,
            is_default=True,
            created_by=self.hr,
        )
        VettingRubric.objects.create(
            name="Secondary Task Rubric",
            is_active=True,
            is_default=False,
            created_by=self.hr,
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
            reference=f"OVS-RUBTASK-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    def test_auto_assign_rubric_uses_default_rubric(self):
        result = auto_assign_rubric.run(self.case.id)

        self.assertTrue(result["success"])
        evaluation = RubricEvaluation.objects.get(case=self.case)
        self.assertEqual(evaluation.rubric_id, self.default_rubric.id)
        self.assertIn("decision_recommendation_id", result)
        self.assertIn(
            result.get("decision_recommendation_status"),
            {"recommend_approve", "recommend_reject", "recommend_manual_review"},
        )

    def test_evaluate_case_with_rubric_task_returns_decision_recommendation(self):
        result = evaluate_case_with_rubric.run(self.case.id, self.default_rubric.id, self.hr.id)
        self.assertTrue(result["success"])
        self.assertIn("decision_recommendation_id", result)
        recommendation = VettingDecisionRecommendation.objects.get(id=result["decision_recommendation_id"])
        self.assertEqual(recommendation.case_id, self.case.id)

    def test_auto_assign_rubric_returns_error_for_missing_case(self):
        result = auto_assign_rubric.run(case_id=999999)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_evaluate_case_with_rubric_task_blocks_with_legacy_org_mapping_when_case_has_no_org(self):
        legacy_org = Organization.objects.create(
            code="rubric-task-legacy-org",
            name="Rubric Task Legacy Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.filter(user=self.hr, is_active=True).update(
            is_active=False,
            is_default=False,
        )
        self.hr.organization = legacy_org.name
        self.hr.save(update_fields=["organization", "updated_at"])
        self._create_org_subscription(
            legacy_org,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
        )
        self.case.organization = None
        self.case.save(update_fields=["organization", "updated_at"])

        with self.assertRaises(DRFValidationError) as context:
            evaluate_case_with_rubric.run(self.case.id, self.default_rubric.id, evaluator_id=None)

        detail = context.exception.detail if isinstance(context.exception.detail, dict) else {}
        self.assertEqual(detail.get("code"), "subscription_required")
        self.assertEqual((detail.get("quota") or {}).get("operation"), "rubric_evaluation")
        self.assertIn(str(legacy_org.id), str((detail.get("quota") or {}).get("scope", "")))


class RubricsOrganizationScopeTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="rub-org-a", name="Rubrics Org A")
        self.org_b = Organization.objects.create(code="rub-org-b", name="Rubrics Org B")

        self.hr_a = User.objects.create_user(
            email="rubrics_scope_a@example.com",
            password="Pass1234!",
            first_name="Rubrics",
            last_name="ScopeA",
            user_type="hr_manager",
        )
        self.hr_b = User.objects.create_user(
            email="rubrics_scope_b@example.com",
            password="Pass1234!",
            first_name="Rubrics",
            last_name="ScopeB",
            user_type="hr_manager",
        )
        self.applicant = User.objects.create_user(
            email="rubrics_scope_applicant@example.com",
            password="Pass1234!",
            first_name="Rubrics",
            last_name="Applicant",
            user_type="applicant",
        )
        OrganizationMembership.objects.create(
            user=self.hr_a,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr_b,
            organization=self.org_b,
            is_active=True,
            is_default=True,
        )

        self.rubric_org_a = VettingRubric.objects.create(
            organization=self.org_a,
            name="Scope Rubric A",
            is_active=True,
            created_by=self.hr_a,
        )
        self.rubric_org_b = VettingRubric.objects.create(
            organization=self.org_b,
            name="Scope Rubric B",
            is_active=True,
            created_by=self.hr_b,
        )
        self.rubric_legacy = VettingRubric.objects.create(
            name="Scope Rubric Legacy",
            is_active=True,
            created_by=self.hr_a,
        )
        self.case_org_b = VettingCase.objects.create(
            organization=self.org_b,
            applicant=self.applicant,
            assigned_to=self.hr_b,
            position_applied="Compliance Officer",
            department="Audit",
            priority="medium",
            status="under_review",
            document_authenticity_score=85,
            consistency_score=82,
            fraud_risk_score=20,
            interview_score=80,
        )

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def test_list_is_scoped_to_org_and_excludes_legacy_null_scope(self):
        self.client.force_authenticate(self.hr_a)
        response = self.client.get("/api/rubrics/vetting-rubrics/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._extract_results(response)}
        self.assertIn(str(self.rubric_org_a.id), ids)
        self.assertNotIn(str(self.rubric_legacy.id), ids)
        self.assertNotIn(str(self.rubric_org_b.id), ids)

    def test_cross_org_case_evaluation_is_denied(self):
        self.client.force_authenticate(self.hr_a)
        response = self.client.post(
            f"/api/rubrics/vetting-rubrics/{self.rubric_org_a.id}/evaluate-case/",
            {"case_id": str(self.case_org_b.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
