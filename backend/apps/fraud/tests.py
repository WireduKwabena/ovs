# backend/apps/fraud/tests.py
from rest_framework.test import APITestCase
from apps.auth_actions import User
from apps.applications import VettingCase
from .models import FraudDetectionResult, ConsistencyCheckResult
import datetime

class FraudAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            full_name='Test User',
            date_of_birth=datetime.date(1990, 1, 1)
        )
        self.case = VettingCase.objects.create(
            applicant=self.user,
            application_type='employment'
        )
        self.fraud_result = FraudDetectionResult.objects.create(
            application=self.case,
            is_fraud=True,
            fraud_probability=0.9,
            anomaly_score=0.8,
            risk_level='HIGH',
            recommendation='REJECT'
        )
        self.consistency_result = ConsistencyCheckResult.objects.create(
            application=self.case,
            overall_consistent=False,
            overall_score=45.5,
            recommendation='MANUAL_REVIEW'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_fraud_results(self):
        response = self.client.get('/api/fraud/results/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_get_fraud_statistics(self):
        response = self.client.get('/api/fraud/results/statistics/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_scans'], 1)
        self.assertEqual(response.data['fraud_detected'], 1)

    def test_list_consistency_results(self):
        response = self.client.get('/api/fraud/consistency/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_get_consistency_statistics(self):
        response = self.client.get('/api/fraud/consistency/statistics/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_checks'], 1)
        self.assertEqual(response.data['consistent_count'], 0)
