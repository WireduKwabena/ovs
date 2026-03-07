from unittest.mock import patch
from uuid import UUID

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.rubrics.models import RubricEvaluation, VettingDecisionOverride, VettingDecisionRecommendation, VettingRubric
from apps.rubrics.tasks import auto_assign_rubric, evaluate_case_with_rubric


class RubricsApiTests(APITestCase):
    def setUp(self):
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
        self.case = VettingCase.objects.create(
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
        self.client.force_authenticate(self.hr)

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

    def _create_rubric(self, name: str) -> int:
        response = self.client.post(
            "/api/rubrics/vetting-rubrics/",
            self._rubric_payload(name),
            format="json",
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

    def test_ai_signals_are_advisory_only_and_do_not_auto_approve(self):
        rubric_id = self._create_rubric("Advisory AI Rubric")
        low_case = VettingCase.objects.create(
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
        self.hr = User.objects.create_user(
            email="rubric-task-hr@example.com",
            password="Pass1234!",
            first_name="Task",
            last_name="HR",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="rubric-task-applicant@example.com",
            password="Pass1234!",
            first_name="Task",
            last_name="Applicant",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
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
