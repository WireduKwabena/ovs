from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.rubrics.models import RubricEvaluation


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

    def test_create_rubric_evaluate_case_and_override_criterion(self):
        create_rubric = self.client.post(
            "/api/rubrics/vetting-rubrics/",
            {
                "name": "Test Rubric",
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
            },
            format="json",
        )
        self.assertEqual(create_rubric.status_code, 201)
        rubric_id = create_rubric.json()["id"]

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
        rubric = self.client.post(
            "/api/rubrics/vetting-rubrics/",
            {
                "name": "Negative Test Rubric",
                "description": "Negative path test",
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
            },
            format="json",
        )
        rubric_id = rubric.json()["id"]
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
