from django.conf import settings
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
import unittest

APP_ENABLED = "apps.fraud" in settings.INSTALLED_APPS

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.fraud.models import ConsistencyCheckResult, FraudDetectionResult, SocialProfileCheckResult


@unittest.skipUnless(APP_ENABLED, "Fraud app is not enabled in INSTALLED_APPS.")
class FraudModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="fraud_test_user@example.com",
            password="Pass1234!",
            first_name="Fraud",
            last_name="Tester",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
            applicant=self.user,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="under_review",
        )

    def test_can_create_fraud_detection_result(self):
        result = FraudDetectionResult.objects.create(
            application=self.case,
            is_fraud=True,
            fraud_probability=0.91,
            anomaly_score=0.83,
            risk_level="HIGH",
            recommendation="REJECT",
            feature_scores={"signal_strength": 0.88},
        )
        self.assertTrue(result.is_fraud)
        self.assertEqual(result.application_id, self.case.id)

    def test_can_create_consistency_check_result(self):
        result = ConsistencyCheckResult.objects.create(
            application=self.case,
            overall_consistent=False,
            overall_score=45.5,
            name_consistency={"match": False},
            date_consistency={"match": True},
            entity_consistency={"match": False},
            recommendation="MANUAL_REVIEW",
        )
        self.assertFalse(result.overall_consistent)
        self.assertEqual(result.application_id, self.case.id)

    def test_can_create_social_profile_check_result(self):
        result = SocialProfileCheckResult.objects.create(
            application=self.case,
            consent_provided=True,
            profiles_checked=1,
            overall_score=82.5,
            risk_level="LOW",
            recommendation="MANUAL_REVIEW",
            automated_decision_allowed=False,
            decision_constraints=[{"code": "social_check_advisory_only"}],
            profiles=[{"platform": "linkedin", "url": "https://linkedin.com/in/sample"}],
        )
        self.assertEqual(result.application_id, self.case.id)
        self.assertEqual(result.risk_level, "LOW")


@unittest.skipUnless(APP_ENABLED, "Fraud app is not enabled in INSTALLED_APPS.")
class FraudApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="fraud-admin@example.com",
            password="Pass1234!",
            first_name="Fraud",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )
        self.user = User.objects.create_user(
            email="fraud-api-user@example.com",
            password="Pass1234!",
            first_name="Fraud",
            last_name="User",
            user_type="applicant",
        )
        self.other_user = User.objects.create_user(
            email="fraud-api-other@example.com",
            password="Pass1234!",
            first_name="Fraud",
            last_name="Other",
            user_type="applicant",
        )

        self.case = VettingCase.objects.create(
            applicant=self.user,
            position_applied="Risk Analyst",
            department="Compliance",
            priority="medium",
            status="under_review",
        )
        self.other_case = VettingCase.objects.create(
            applicant=self.other_user,
            position_applied="Security Analyst",
            department="Operations",
            priority="high",
            status="under_review",
        )

        self.user_fraud_result = FraudDetectionResult.objects.create(
            application=self.case,
            is_fraud=True,
            fraud_probability=0.91,
            anomaly_score=0.83,
            risk_level="HIGH",
            recommendation="REJECT",
            feature_scores={"signal_strength": 0.88},
        )
        self.other_fraud_result = FraudDetectionResult.objects.create(
            application=self.other_case,
            is_fraud=False,
            fraud_probability=0.11,
            anomaly_score=0.12,
            risk_level="LOW",
            recommendation="PROCEED",
            feature_scores={"signal_strength": 0.14},
        )

        self.user_consistency_result = ConsistencyCheckResult.objects.create(
            application=self.case,
            overall_consistent=False,
            overall_score=48.0,
            name_consistency={"match": False},
            date_consistency={"match": True},
            entity_consistency={"match": False},
            recommendation="MANUAL_REVIEW",
        )
        self.other_consistency_result = ConsistencyCheckResult.objects.create(
            application=self.other_case,
            overall_consistent=True,
            overall_score=91.0,
            name_consistency={"match": True},
            date_consistency={"match": True},
            entity_consistency={"match": True},
            recommendation="PROCEED",
        )

        self.user_social_result = SocialProfileCheckResult.objects.create(
            application=self.case,
            consent_provided=True,
            profiles_checked=1,
            overall_score=82.0,
            risk_level="LOW",
            recommendation="MANUAL_REVIEW",
            automated_decision_allowed=False,
            decision_constraints=[{"code": "social_check_advisory_only"}],
            profiles=[{"platform": "linkedin", "url": "https://linkedin.com/in/user"}],
        )
        self.other_social_result = SocialProfileCheckResult.objects.create(
            application=self.other_case,
            consent_provided=False,
            profiles_checked=0,
            overall_score=0.0,
            risk_level="HIGH",
            recommendation="MANUAL_REVIEW",
            automated_decision_allowed=False,
            decision_constraints=[{"code": "social_consent_missing"}],
            profiles=[],
        )

    def test_regular_user_sees_only_own_fraud_results(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/fraud/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.user_fraud_result.id))

    def test_admin_sees_all_fraud_results(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/fraud/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_risk_level_filter_is_case_insensitive(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/fraud/results/", {"risk_level": "high"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.user_fraud_result.id))

    def test_case_id_filter_returns_expected_row(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/fraud/results/", {"case_id": self.case.case_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["application_case_id"], self.case.case_id)

    def test_fraud_statistics_for_regular_user_uses_scoped_queryset(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/fraud/results/statistics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_scans"], 1)
        self.assertEqual(response.data["fraud_detected"], 1)
        self.assertEqual(response.data["risk_distribution"]["HIGH"], 1)

    def test_consistency_invalid_boolean_filter_returns_empty_list(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/fraud/consistency/", {"consistent": "maybe"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_consistency_history_rejects_invalid_limit(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/fraud/consistency/history/", {"limit": "abc"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_consistency_history_clamps_limit(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/fraud/consistency/history/", {"limit": "500"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["limit"], 200)
        self.assertEqual(len(response.data["history"]), 2)

    def test_consistency_statistics_for_regular_user_uses_scoped_queryset(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/fraud/consistency/statistics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_checks"], 1)
        self.assertEqual(response.data["consistent_count"], 0)
        self.assertEqual(response.data["average_score"], 48.0)

    def test_regular_user_sees_only_own_social_profile_results(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/fraud/social-profiles/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.user_social_result.id))

    def test_social_profile_statistics_for_regular_user_uses_scoped_queryset(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/fraud/social-profiles/statistics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_checks"], 1)
        self.assertEqual(response.data["manual_review_count"], 1)
        self.assertEqual(response.data["risk_distribution"]["LOW"], 1)
