from django.conf import settings
from django.test import TestCase
import unittest

APP_ENABLED = "apps.fraud" in settings.INSTALLED_APPS

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.fraud.models import ConsistencyCheckResult, FraudDetectionResult


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
