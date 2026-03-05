from unittest.mock import patch
from uuid import UUID

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.rubrics.models import RubricEvaluation, VettingRubric
from apps.rubrics.tasks import auto_assign_rubric


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

    def test_auto_assign_rubric_returns_error_for_missing_case(self):
        result = auto_assign_rubric.run(case_id=999999)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())
