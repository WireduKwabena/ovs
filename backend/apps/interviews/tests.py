from rest_framework.test import APITestCase
from django.test import override_settings
from unittest.mock import Mock, patch

from apps.applications.models import InterrogationFlag, VettingCase
from apps.authentication.models import User
from apps.billing.models import BillingSubscription
from apps.governance.models import Organization, OrganizationMembership
from apps.interviews.models import (
    InterviewQuestion,
    InterviewResponse,
    InterviewSession,
    VideoAnalysis,
)
from apps.interviews.tasks import analyze_response_task, generate_session_summary_task


class InterviewsApiTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_interviews_test@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Interviews",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="app_interviews_test@example.com",
            password="Pass1234!",
            first_name="Applicant",
            last_name="Interviews",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="QA Engineer",
            department="Quality",
            priority="medium",
            status="interview_scheduled",
            document_authenticity_score=82,
            consistency_score=78,
            fraud_risk_score=22,
        )
        self.client.force_authenticate(self.hr)

        question_response = self.client.post(
            "/api/interviews/questions/",
            {
                "question_text": "Tell us how you validate inconsistent records.",
                "question_type": "verification",
                "difficulty": "medium",
                "evaluation_rubric": "Assess structure, ownership, and verification depth.",
                "expected_keywords": ["validate", "records", "consistency"],
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(question_response.status_code, 201)
        self.question_id = question_response.json()["id"]

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
            reference=f"OVS-INT-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    def test_session_lifecycle_and_response_analysis(self):
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        session_id = create_session.json()["id"]

        start_session = self.client.post(f"/api/interviews/sessions/{session_id}/start/")
        self.assertEqual(start_session.status_code, 200)
        self.assertEqual(start_session.json()["status"], "in_progress")

        create_response = self.client.post(
            "/api/interviews/responses/",
            {
                "session": session_id,
                "question": self.question_id,
                "sequence_number": 1,
                "transcript": "I compare source systems, reconcile fields, and escalate anomalies with evidence.",
                "response_duration_seconds": 20,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        response_id = create_response.json()["id"]
        analyze_response_task.run(response_id)

        complete_session = self.client.post(f"/api/interviews/sessions/{session_id}/complete/")
        self.assertEqual(complete_session.status_code, 200)
        self.assertEqual(complete_session.json()["status"], "completed")
        generate_session_summary_task.run(session_id)

        get_session = self.client.get(f"/api/interviews/sessions/{session_id}/")
        self.assertEqual(get_session.status_code, 200)
        self.assertIsNotNone(get_session.json()["overall_score"])

        self.case.refresh_from_db()
        self.assertTrue(self.case.interview_completed)
        self.assertIsNotNone(self.case.interview_score)

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_analyze_endpoint_blocks_when_org_subscription_is_inactive(self):
        organization = Organization.objects.create(
            code="interview-quota-org",
            name="Interview Quota Org",
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

        scoped_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="QA Engineer",
            department="Quality",
            priority="medium",
            status="interview_in_progress",
        )
        session = InterviewSession.objects.create(
            case=scoped_case,
            status="in_progress",
            max_questions=5,
        )
        interview_response = InterviewResponse.objects.create(
            session=session,
            question=InterviewQuestion.objects.get(id=self.question_id),
            sequence_number=1,
            transcript="I validate data lineage and verify evidence chains.",
            response_duration_seconds=20,
        )

        response = self.client.post(f"/api/interviews/responses/{interview_response.id}/analyze/")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "subscription_required")
        self.assertEqual((payload.get("quota") or {}).get("operation"), "interview_analysis")

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_create_response_blocks_when_org_subscription_is_inactive(self):
        organization = Organization.objects.create(
            code="interview-create-sub-inactive",
            name="Interview Create Inactive Subscription Org",
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

        scoped_case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            organization=organization,
            position_applied="QA Engineer",
            department="Quality",
            priority="medium",
            status="interview_in_progress",
        )
        session = InterviewSession.objects.create(
            case=scoped_case,
            status="in_progress",
            max_questions=5,
        )

        response = self.client.post(
            "/api/interviews/responses/",
            {
                "session": str(session.id),
                "question": str(self.question_id),
                "sequence_number": 1,
                "transcript": "I validate chain-of-custody records against source systems.",
                "response_duration_seconds": 22,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "subscription_required")
        self.assertEqual((payload.get("quota") or {}).get("operation"), "interview_analysis")

    @patch("apps.interviews.signals.NotificationService.send_interview_scheduled")
    def test_session_creation_triggers_candidate_interview_scheduled_notification(
        self, mock_send_interview_scheduled
    ):
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        mock_send_interview_scheduled.assert_called_once()
        created_session = mock_send_interview_scheduled.call_args.args[0]
        self.assertEqual(str(created_session.id), create_session.json()["id"])

    def test_save_and_update_exchange_actions_with_session_id_lookup(self):
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        session_pk = create_session.json()["id"]
        session_code = create_session.json()["session_id"]

        start_session = self.client.post(f"/api/interviews/sessions/{session_pk}/start/")
        self.assertEqual(start_session.status_code, 200)

        flag = InterrogationFlag.objects.create(
            case=self.case,
            flag_type="consistency_mismatch",
            severity="high",
            title="Name mismatch",
            description="Submitted name differs across documents.",
        )

        save_exchange = self.client.post(
            f"/api/interviews/sessions/{session_pk}/save-exchange/",
            {
                "sequence_number": 1,
                "question_text": "Please explain why your submitted names differ.",
                "question_intent": "resolve_flag",
                "target_flag_id": flag.id,
            },
            format="json",
        )
        self.assertEqual(save_exchange.status_code, 200)
        self.assertEqual(save_exchange.json()["question_number"], 1)
        self.assertEqual(save_exchange.json()["current_flag_id"], str(flag.id))

        get_by_session_code = self.client.get(f"/api/interviews/sessions/{session_code}/")
        self.assertEqual(get_by_session_code.status_code, 200)
        self.assertEqual(get_by_session_code.json()["session_id"], session_code)

        update_exchange = self.client.post(
            f"/api/interviews/sessions/{session_code}/update-exchange/",
            {
                "sequence_number": 1,
                "transcript": "The mismatch happened because one document used my abbreviated middle name.",
                "video_url": "https://example.com/interview/video1.mp4",
                "sentiment": "neutral",
                "nonverbal_data": {"confidence_score": 72},
            },
            format="json",
        )
        self.assertEqual(update_exchange.status_code, 200)
        self.assertEqual(update_exchange.json()["question_number"], 1)
        self.assertEqual(update_exchange.json()["current_flag_id"], str(flag.id))

        get_session = self.client.get(f"/api/interviews/sessions/{session_pk}/")
        self.assertEqual(get_session.status_code, 200)
        history = get_session.json()["conversation_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["question_number"], 1)
        self.assertIn("abbreviated middle name", history[0]["transcript"])

        flag.refresh_from_db()
        self.assertEqual(flag.status, "addressed")

    def test_save_exchange_rejects_invalid_sequence_number(self):
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        session_pk = create_session.json()["id"]

        invalid_save = self.client.post(
            f"/api/interviews/sessions/{session_pk}/save-exchange/",
            {
                "sequence_number": "not-an-int",
                "question_text": "Invalid sequence test question",
            },
            format="json",
        )
        self.assertEqual(invalid_save.status_code, 400)

    @override_settings(HEYGEN_FRONTEND_SDK_ENABLED=False)
    def test_avatar_session_returns_disabled_payload_when_sdk_is_off(self):
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        session_pk = create_session.json()["id"]

        response = self.client.post(f"/api/interviews/sessions/{session_pk}/avatar-session/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"enabled": False})

    @override_settings(
        HEYGEN_FRONTEND_SDK_ENABLED=True,
        HEYGEN_API_KEY="test-api-key",
        HEYGEN_AVATAR_ID="avatar_test",
        HEYGEN_VOICE_ID="voice_test",
        HEYGEN_AVATAR_QUALITY="high",
        HEYGEN_AVATAR_ACTIVITY_IDLE_TIMEOUT=240,
        HEYGEN_AVATAR_LANGUAGE="en",
    )
    @patch("apps.interviews.services.heygen_sdk.httpx.post")
    def test_avatar_session_returns_sdk_payload(self, mock_post):
        mocked_response = Mock()
        mocked_response.status_code = 200
        mocked_response.json.return_value = {
            "data": {
                "token": "token-123",
            }
        }
        mock_post.return_value = mocked_response

        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        session_pk = create_session.json()["id"]

        response = self.client.post(f"/api/interviews/sessions/{session_pk}/avatar-session/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["token"], "token-123")
        self.assertEqual(payload["avatar_name"], "avatar_test")
        self.assertEqual(payload["voice_id"], "voice_test")
        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["language"], "en")
        self.assertEqual(payload["activity_idle_timeout"], 240)

    def test_save_exchange_same_sequence_does_not_double_increment_question_usage(self):
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        session_pk = create_session.json()["id"]

        question_text = "Please explain the document inconsistency."

        first_save = self.client.post(
            f"/api/interviews/sessions/{session_pk}/save-exchange/",
            {
                "sequence_number": 1,
                "question_text": question_text,
                "question_intent": "resolve_flag",
            },
            format="json",
        )
        self.assertEqual(first_save.status_code, 200)

        question = InterviewQuestion.objects.get(question_text=question_text)
        self.assertEqual(question.times_used, 1)

        second_save = self.client.post(
            f"/api/interviews/sessions/{session_pk}/save-exchange/",
            {
                "sequence_number": 1,
                "question_text": question_text,
                "question_intent": "resolve_flag",
            },
            format="json",
        )
        self.assertEqual(second_save.status_code, 200)

        question.refresh_from_db()
        self.assertEqual(question.times_used, 1)

    @patch("apps.interviews.signals.analyze_response_task.delay")
    def test_response_signal_skips_empty_created_response(self, mock_delay):
        session = InterviewSession.objects.create(
            case=self.case,
            status="in_progress",
        )
        InterviewResponse.objects.create(
            session=session,
            question_id=self.question_id,
            sequence_number=1,
            transcript="",
        )
        mock_delay.assert_not_called()

    @patch("apps.interviews.signals.analyze_response_task.delay")
    def test_response_signal_queues_created_response_with_inputs(self, mock_delay):
        session = InterviewSession.objects.create(
            case=self.case,
            status="in_progress",
        )
        created = InterviewResponse.objects.create(
            session=session,
            question_id=self.question_id,
            sequence_number=1,
            transcript="I verified the details against official records.",
        )
        mock_delay.assert_called_once_with(created.id)

    def test_admin_service_actions_require_hr_or_service(self):
        self.client.force_authenticate(self.applicant)

        analytics_response = self.client.get("/api/interviews/sessions/analytics-dashboard/?days=30")
        self.assertEqual(analytics_response.status_code, 403)

        compare_response = self.client.post(
            "/api/interviews/sessions/compare/",
            {"session_ids": ["INT-UNKNOWN"]},
            format="json",
        )
        self.assertEqual(compare_response.status_code, 403)

        generate_flags_response = self.client.post(
            "/api/interviews/sessions/generate-flags/",
            {"case": self.case.id, "persist": False},
            format="json",
        )
        self.assertEqual(generate_flags_response.status_code, 403)

    def test_services_actions_playback_analytics_compare_and_flag_generation(self):
        session_one = InterviewSession.objects.create(
            case=self.case,
            status="completed",
            total_questions_asked=1,
            duration_seconds=180,
            overall_score=81,
            communication_score=76,
            consistency_score=73,
            confidence_score=79,
        )
        response_one = InterviewResponse.objects.create(
            session=session_one,
            question_id=self.question_id,
            sequence_number=1,
            transcript="I verified the inconsistency with source records and attached evidence.",
            response_duration_seconds=40,
            response_quality_score=82,
            relevance_score=80,
            completeness_score=78,
            coherence_score=81,
        )
        VideoAnalysis.objects.update_or_create(
            response=response_one,
            defaults={
                "face_detected": True,
                "face_detection_confidence": 88,
                "eye_contact_percentage": 72,
                "confidence_level": 75,
                "stress_level": 28,
                "behavioral_indicators": [],
                "raw_analysis_data": {
                    "identity_match": {"enabled": True, "success": True, "is_match": True}
                },
                "frames_analyzed": 50,
                "analysis_duration_seconds": 1.5,
            },
        )

        applicant_two = User.objects.create_user(
            email="app_interviews_compare@example.com",
            password="Pass1234!",
            first_name="Applicant",
            last_name="Compare",
            user_type="applicant",
        )
        case_two = VettingCase.objects.create(
            applicant=applicant_two,
            assigned_to=self.hr,
            position_applied="QA Engineer",
            department="Quality",
            priority="medium",
            status="under_review",
        )
        session_two = InterviewSession.objects.create(
            case=case_two,
            status="completed",
            total_questions_asked=1,
            duration_seconds=200,
            overall_score=64,
            communication_score=60,
            consistency_score=62,
            confidence_score=58,
        )
        response_two = InterviewResponse.objects.create(
            session=session_two,
            question_id=self.question_id,
            sequence_number=1,
            transcript="I am not fully sure why the records differ.",
            response_duration_seconds=30,
            response_quality_score=45,
            relevance_score=48,
            completeness_score=42,
            coherence_score=46,
        )
        VideoAnalysis.objects.update_or_create(
            response=response_two,
            defaults={
                "face_detected": True,
                "face_detection_confidence": 70,
                "eye_contact_percentage": 45,
                "confidence_level": 35,
                "stress_level": 74,
                "behavioral_indicators": ["poor_eye_contact"],
                "raw_analysis_data": {
                    "identity_match": {"enabled": True, "success": True, "is_match": False}
                },
                "frames_analyzed": 45,
                "analysis_duration_seconds": 1.4,
            },
        )

        playback_response = self.client.get(f"/api/interviews/sessions/{session_one.id}/playback/")
        self.assertEqual(playback_response.status_code, 200)
        self.assertEqual(playback_response.json()["session"]["session_id"], session_one.session_id)

        analytics_response = self.client.get("/api/interviews/sessions/analytics-dashboard/?days=30")
        self.assertEqual(analytics_response.status_code, 200)
        self.assertIn("metrics", analytics_response.json())

        compare_response = self.client.post(
            "/api/interviews/sessions/compare/",
            {"session_ids": [session_one.session_id, session_two.session_id]},
            format="json",
        )
        self.assertEqual(compare_response.status_code, 200)
        self.assertIn("recommendation", compare_response.json())
        self.assertEqual(len(compare_response.json()["sessions"]), 2)

        generate_flags_response = self.client.post(
            "/api/interviews/sessions/generate-flags/",
            {"case": self.case.id, "persist": False},
            format="json",
        )
        self.assertEqual(generate_flags_response.status_code, 200)
        self.assertGreaterEqual(generate_flags_response.json()["generated_count"], 1)


@override_settings(SERVICE_TOKEN="svc-token")
class InterviewServiceTokenApiTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_interviews_service@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Service",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="app_interviews_service@example.com",
            password="Pass1234!",
            first_name="Applicant",
            last_name="Service",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="Security Analyst",
            department="Trust & Safety",
            priority="medium",
            status="interview_scheduled",
        )
        self.client.force_authenticate(self.hr)
        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 201)
        self.session_id = create_session.json()["id"]
        self.client.force_authenticate(user=None)

    def test_service_token_can_access_session_routes(self):
        list_response = self.client.get(
            "/api/interviews/sessions/",
            HTTP_X_SERVICE_TOKEN="svc-token",
        )
        self.assertEqual(list_response.status_code, 200)
        rows = list_response.json()
        if isinstance(rows, dict):
            rows = rows.get("results", [])
        self.assertGreaterEqual(len(rows), 1)

        save_exchange = self.client.post(
            f"/api/interviews/sessions/{self.session_id}/save-exchange/",
            {
                "sequence_number": 1,
                "question_text": "Please explain the discrepancy in your timeline.",
                "question_intent": "resolve_flag",
            },
            format="json",
            HTTP_X_SERVICE_TOKEN="svc-token",
        )
        self.assertEqual(save_exchange.status_code, 200)

        update_exchange = self.client.post(
            f"/api/interviews/sessions/{self.session_id}/update-exchange/",
            {
                "sequence_number": 1,
                "transcript": "The timeline difference was due to a contractor overlap.",
                "sentiment": "neutral",
                "nonverbal_data": {"confidence_score": 68},
            },
            format="json",
            HTTP_X_SERVICE_TOKEN="svc-token",
        )
        self.assertEqual(update_exchange.status_code, 200)

    def test_invalid_service_token_is_rejected(self):
        response = self.client.get(
            "/api/interviews/sessions/",
            HTTP_X_SERVICE_TOKEN="invalid-token",
        )
        self.assertIn(response.status_code, {401, 403})

    def test_service_token_can_access_admin_service_actions(self):
        analytics_response = self.client.get(
            "/api/interviews/sessions/analytics-dashboard/?days=30",
            HTTP_X_SERVICE_TOKEN="svc-token",
        )
        self.assertEqual(analytics_response.status_code, 200)


class InterviewTaskIdentityMatchTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_interviews_task@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Task",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="app_interviews_task@example.com",
            password="Pass1234!",
            first_name="Applicant",
            last_name="Task",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="Risk Analyst",
            department="Compliance",
            priority="medium",
            status="interview_in_progress",
        )
        self.session = InterviewSession.objects.create(
            case=self.case,
            status="in_progress",
            max_questions=5,
        )
        self.question = InterviewQuestion.objects.create(
            question_text="Describe your verification process.",
            question_type="verification",
            difficulty="medium",
            evaluation_rubric="Assess clarity and evidence-based reasoning.",
            created_by=self.hr,
            is_active=True,
        )
        self.response = InterviewResponse.objects.create(
            session=self.session,
            question=self.question,
            sequence_number=1,
            transcript="I validate records against source systems and document evidence.",
            response_duration_seconds=30,
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
            reference=f"OVS-INTTASK-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    @patch("apps.interviews.tasks._run_identity_match")
    def test_task_persists_identity_match_payload(self, mock_identity):
        mock_identity.return_value = {
            "enabled": True,
            "success": True,
            "is_match": False,
            "similarity_score": 0.42,
            "threshold": 0.72,
        }

        result = analyze_response_task.run(self.response.id)
        self.assertTrue(result["success"])

        self.response.refresh_from_db()
        self.assertIn(
            "Identity mismatch detected between document face and interview face.",
            self.response.concerns_detected,
        )

        video_analysis = self.response.video_analysis
        self.assertIn("identity_match", video_analysis.raw_analysis_data)
        self.assertEqual(
            video_analysis.raw_analysis_data["identity_match"]["similarity_score"],
            0.42,
        )

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_analyze_response_task_blocks_when_org_subscription_is_inactive(self):
        organization = Organization.objects.create(
            code="interview-task-sub-inactive",
            name="Interview Task Subscription Inactive Org",
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
        self.case.organization = organization
        self.case.save(update_fields=["organization", "updated_at"])
        self.response.processed_at = None
        self.response.save(update_fields=["processed_at"])

        result = analyze_response_task.run(self.response.id)

        self.assertFalse(result["success"])
        self.assertEqual(result.get("code"), "subscription_required")
        self.assertEqual((result.get("quota") or {}).get("operation"), "interview_analysis")

    @override_settings(BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_analyze_response_task_blocks_with_legacy_org_mapping_when_case_has_no_org(self):
        legacy_org = Organization.objects.create(
            code="interview-task-legacy-org",
            name="Interview Task Legacy Org",
            organization_type="agency",
            is_active=True,
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
        self.response.processed_at = None
        self.response.save(update_fields=["processed_at"])

        result = analyze_response_task.run(self.response.id)

        self.assertFalse(result["success"])
        self.assertEqual(result.get("code"), "subscription_required")
        self.assertEqual((result.get("quota") or {}).get("operation"), "interview_analysis")
        self.assertIn(str(legacy_org.id), str((result.get("quota") or {}).get("scope", "")))
