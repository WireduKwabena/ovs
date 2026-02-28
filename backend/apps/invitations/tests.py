from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase, APIRequestFactory

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.interviews.models import InterviewQuestion, InterviewSession
from apps.invitations.models import CandidateAccessPass, Invitation
from apps.invitations.permissions import IsAuthenticatedOrCandidateAccessSession
from apps.invitations.services import CandidateAccessError, issue_candidate_access_pass, send_invitation


class InvitationAuthorizationAndNegativeTests(APITestCase):
    def setUp(self):
        self.hr_one = User.objects.create_user(
            email="hr_invites_one@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="One",
            user_type="hr_manager",
        )
        self.hr_two = User.objects.create_user(
            email="hr_invites_two@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Two",
            user_type="hr_manager",
        )

        campaign = VettingCampaign.objects.create(name="Invite Campaign", initiated_by=self.hr_one)
        candidate = Candidate.objects.create(
            first_name="Invite",
            last_name="Candidate",
            email="invite_candidate@example.com",
        )
        self.enrollment = CandidateEnrollment.objects.create(campaign=campaign, candidate=candidate, status="invited")
        self.invitation = Invitation.objects.create(
            enrollment=self.enrollment,
            channel="email",
            send_to=candidate.email,
            expires_at=timezone.now() + timedelta(hours=24),
            created_by=self.hr_one,
        )

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_hr_manager_cannot_create_invitation_for_other_campaign(self):
        self.client.force_authenticate(self.hr_two)
        response = self.client.post(
            "/api/invitations/",
            {
                "enrollment": self.enrollment.id,
                "channel": "email",
                "expires_in_hours": 24,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_hr_manager_lists_only_own_invitations(self):
        self.client.force_authenticate(self.hr_two)
        response = self.client.get("/api/invitations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self._items(response.json())), 0)

    def test_accept_invalid_token_returns_404(self):
        response = self.client.post(
            "/api/invitations/accept/",
            {"token": "9f846a53-0b12-4e4b-b6b5-57d57d7ea9c0"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_accept_expired_invitation_returns_400_and_marks_expired(self):
        expired = Invitation.objects.create(
            enrollment=self.enrollment,
            channel="email",
            send_to=self.enrollment.candidate.email,
            expires_at=timezone.now() - timedelta(hours=1),
            created_by=self.hr_one,
        )
        response = self.client.post(
            "/api/invitations/accept/",
            {"token": str(expired.token)},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        expired.refresh_from_db()
        self.assertEqual(expired.status, "expired")


class CandidateAccessPassFlowTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_candidate_access@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Owner",
            user_type="hr_manager",
        )
        self.campaign = VettingCampaign.objects.create(name="Candidate Access Campaign", initiated_by=self.hr)
        self.candidate = Candidate.objects.create(
            first_name="Portal",
            last_name="Candidate",
            email="portal_candidate@example.com",
        )
        self.enrollment = CandidateEnrollment.objects.create(
            campaign=self.campaign,
            candidate=self.candidate,
            status="invited",
        )
        self.invitation = Invitation.objects.create(
            enrollment=self.enrollment,
            channel="email",
            send_to=self.candidate.email,
            expires_at=timezone.now() + timedelta(hours=24),
            status="sent",
            created_by=self.hr,
        )

    def test_candidate_access_consume_me_results_and_logout_flow(self):
        access_pass, raw_token = issue_candidate_access_pass(
            enrollment=self.enrollment,
            invitation=self.invitation,
            issued_by=self.hr,
            pass_type="portal",
            max_uses=5,
        )
        self.assertEqual(access_pass.status, "issued")

        consume = self.client.post(
            "/api/invitations/access/consume/",
            {"token": raw_token, "begin_vetting": True},
            format="json",
        )
        self.assertEqual(consume.status_code, 200)
        self.assertEqual(consume.json()["enrollment_status"], "in_progress")

        self.enrollment.refresh_from_db()
        self.invitation.refresh_from_db()
        self.assertEqual(self.enrollment.status, "in_progress")
        self.assertIsNotNone(self.enrollment.registered_at)
        self.assertEqual(self.invitation.status, "accepted")
        self.assertIsNotNone(self.invitation.accepted_at)

        access_pass.refresh_from_db()
        self.assertEqual(access_pass.use_count, 1)

        me = self.client.get("/api/invitations/access/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["candidate"]["email"], self.candidate.email)

        results_pending = self.client.get("/api/invitations/access/results/")
        self.assertEqual(results_pending.status_code, 200)
        self.assertFalse(results_pending.json()["available"])

        self.enrollment.status = "approved"
        self.enrollment.review_notes = "Approved after full review."
        self.enrollment.metadata = {"results": {"overall_score": 92.5, "decision": "approved"}}
        self.enrollment.save(update_fields=["status", "review_notes", "metadata", "updated_at"])

        results_ready = self.client.get("/api/invitations/access/results/")
        self.assertEqual(results_ready.status_code, 200)
        self.assertTrue(results_ready.json()["available"])
        self.assertEqual(results_ready.json()["results"]["overall_score"], 92.5)

        logout = self.client.post("/api/invitations/access/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)

        me_after_logout = self.client.get("/api/invitations/access/me/")
        self.assertIn(me_after_logout.status_code, {401, 403})

    def test_candidate_access_invalid_token_returns_404(self):
        response = self.client.post(
            "/api/invitations/access/consume/",
            {"token": "invalid-token-value"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_candidate_access_exhausted_token_returns_400(self):
        _, raw_token = issue_candidate_access_pass(
            enrollment=self.enrollment,
            invitation=self.invitation,
            issued_by=self.hr,
            pass_type="portal",
            max_uses=1,
        )
        first = self.client.post(
            "/api/invitations/access/consume/",
            {"token": raw_token},
            format="json",
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/invitations/access/consume/",
            {"token": raw_token},
            format="json",
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["code"], "exhausted")


class CandidateAccessVettingEndpointsTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_candidate_endpoints@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Owner",
            user_type="hr_manager",
        )
        self.applicant = User.objects.create_user(
            email="portal_candidate_user@example.com",
            password="Pass1234!",
            first_name="Portal",
            last_name="Candidate",
            user_type="applicant",
        )
        campaign = VettingCampaign.objects.create(name="Portal Campaign", initiated_by=self.hr)
        self.candidate = Candidate.objects.create(
            first_name="Portal",
            last_name="Candidate",
            email=self.applicant.email,
        )
        self.enrollment = CandidateEnrollment.objects.create(
            campaign=campaign,
            candidate=self.candidate,
            status="registered",
            registered_at=timezone.now(),
        )
        self.invitation = Invitation.objects.create(
            enrollment=self.enrollment,
            channel="email",
            send_to=self.candidate.email,
            expires_at=timezone.now() + timedelta(hours=24),
            status="sent",
            created_by=self.hr,
        )
        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            candidate_enrollment=self.enrollment,
            assigned_to=self.hr,
            position_applied="Risk Analyst",
            department="Compliance",
            priority="medium",
            status="document_upload",
        )
        self.interview_session = InterviewSession.objects.create(
            case=self.case,
            use_dynamic_questions=True,
            max_questions=5,
            status="created",
        )
        self.question = InterviewQuestion.objects.create(
            question_text="Describe your document verification process.",
            question_type="verification",
            difficulty="medium",
            evaluation_rubric="Assess structured and evidence-based explanation.",
            expected_keywords=["verify", "document"],
            is_active=True,
            created_by=self.hr,
        )

        _, raw_token = issue_candidate_access_pass(
            enrollment=self.enrollment,
            invitation=self.invitation,
            issued_by=self.hr,
            pass_type="portal",
            max_uses=5,
        )
        consume = self.client.post(
            "/api/invitations/access/consume/",
            {"token": raw_token, "begin_vetting": True},
            format="json",
        )
        self.assertEqual(consume.status_code, 200)

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    @patch("apps.interviews.views.generate_session_summary_task.delay", return_value=None)
    @patch("apps.interviews.signals.analyze_response_task.delay", return_value=None)
    @patch("apps.applications.views.verify_document_async.delay", return_value=None)
    def test_candidate_session_can_use_application_and_interview_endpoints(self, _mock_verify_delay, _mock_analyze_delay, _mock_summary_delay):
        cases = self.client.get("/api/applications/cases/")
        self.assertEqual(cases.status_code, 200)
        case_rows = self._items(cases.json())
        self.assertEqual(len(case_rows), 1)
        self.assertEqual(case_rows[0]["id"], self.case.id)

        upload = self.client.post(
            f"/api/applications/cases/{self.case.id}/upload-document/",
            {
                "document_type": "degree",
                "file": SimpleUploadedFile("degree.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(upload.status_code, 201)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, "in_progress")

        sessions = self.client.get("/api/interviews/sessions/")
        self.assertEqual(sessions.status_code, 200)
        session_rows = self._items(sessions.json())
        self.assertEqual(len(session_rows), 1)
        self.assertEqual(session_rows[0]["id"], self.interview_session.id)

        start = self.client.post(f"/api/interviews/sessions/{self.interview_session.id}/start/")
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["status"], "in_progress")

        response_create = self.client.post(
            "/api/interviews/responses/",
            {
                "session": self.interview_session.id,
                "question": self.question.id,
                "sequence_number": 1,
                "transcript": "I validate document provenance and reconcile records with trusted systems.",
                "response_duration_seconds": 22,
            },
            format="json",
        )
        self.assertEqual(response_create.status_code, 201)

        complete = self.client.post(f"/api/interviews/sessions/{self.interview_session.id}/complete/")
        self.assertEqual(complete.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, "completed")

    def test_candidate_session_is_scoped_and_cannot_create_cases_or_sessions(self):
        other_applicant = User.objects.create_user(
            email="other_candidate_user@example.com",
            password="Pass1234!",
            first_name="Other",
            last_name="Candidate",
            user_type="applicant",
        )
        other_candidate = Candidate.objects.create(
            first_name="Other",
            last_name="Candidate",
            email=other_applicant.email,
        )
        other_enrollment = CandidateEnrollment.objects.create(
            campaign=self.enrollment.campaign,
            candidate=other_candidate,
            status="registered",
            registered_at=timezone.now(),
        )
        other_case = VettingCase.objects.create(
            applicant=other_applicant,
            candidate_enrollment=other_enrollment,
            assigned_to=self.hr,
            position_applied="Data Analyst",
            department="Compliance",
            priority="medium",
            status="document_upload",
        )
        other_session = InterviewSession.objects.create(
            case=other_case,
            use_dynamic_questions=True,
            max_questions=5,
            status="created",
        )

        hidden_case = self.client.get(f"/api/applications/cases/{other_case.id}/")
        self.assertEqual(hidden_case.status_code, 404)

        hidden_session = self.client.get(f"/api/interviews/sessions/{other_session.id}/")
        self.assertEqual(hidden_session.status_code, 404)

        create_case = self.client.post(
            "/api/applications/cases/",
            {
                "position_applied": "New Role",
                "department": "Ops",
                "job_description": "Candidate initiated request",
                "priority": "medium",
            },
            format="json",
        )
        self.assertEqual(create_case.status_code, 403)

        create_session = self.client.post(
            "/api/interviews/sessions/",
            {
                "case": self.case.id,
                "use_dynamic_questions": True,
                "max_questions": 5,
            },
            format="json",
        )
        self.assertEqual(create_session.status_code, 403)

        wrong_response = self.client.post(
            "/api/interviews/responses/",
            {
                "session": other_session.id,
                "question": self.question.id,
                "sequence_number": 1,
                "transcript": "This should fail.",
                "response_duration_seconds": 5,
            },
            format="json",
        )
        self.assertEqual(wrong_response.status_code, 403)


class ServiceTokenPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsAuthenticatedOrCandidateAccessSession()

    @override_settings(SERVICE_TOKEN="svc-token")
    @patch("apps.invitations.permissions.resolve_candidate_access_session", return_value=None)
    def test_allows_valid_x_service_token(self, _mock_session):
        request = self.factory.get("/api/interviews/sessions/", HTTP_X_SERVICE_TOKEN="svc-token")
        request.session = {}

        allowed = self.permission.has_permission(request, view=None)

        self.assertTrue(allowed)
        self.assertTrue(getattr(request, "service_authenticated", False))

    @override_settings(SERVICE_TOKEN="svc-token")
    @patch("apps.invitations.permissions.resolve_candidate_access_session", return_value=None)
    def test_allows_valid_bearer_service_token(self, _mock_session):
        request = self.factory.get(
            "/api/interviews/sessions/",
            HTTP_AUTHORIZATION="Bearer svc-token",
        )
        request.session = {}

        allowed = self.permission.has_permission(request, view=None)

        self.assertTrue(allowed)
        self.assertTrue(getattr(request, "service_authenticated", False))

    @override_settings(SERVICE_TOKEN="svc-token")
    @patch("apps.invitations.permissions.resolve_candidate_access_session", return_value=None)
    def test_rejects_invalid_service_token_without_candidate_session(self, _mock_session):
        request = self.factory.get("/api/interviews/sessions/", HTTP_X_SERVICE_TOKEN="bad-token")
        request.session = {}

        allowed = self.permission.has_permission(request, view=None)

        self.assertFalse(allowed)


class InvitationServiceHardeningTests(APITestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="hr_inv_service@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Service",
            user_type="hr_manager",
        )
        self.campaign = VettingCampaign.objects.create(name="Invitation Service Campaign", initiated_by=self.hr)
        self.candidate = Candidate.objects.create(
            first_name="Invite",
            last_name="SMS",
            email="invite_sms_candidate@example.com",
            phone_number="+15550001111",
        )
        self.enrollment = CandidateEnrollment.objects.create(
            campaign=self.campaign,
            candidate=self.candidate,
            status="invited",
        )

    def test_issue_candidate_access_pass_sanitizes_metadata(self):
        access_pass, _ = issue_candidate_access_pass(
            enrollment=self.enrollment,
            issued_by=self.hr,
            metadata={
                "created_at": timezone.now(),
                "tags": {"a", "b"},
                99: object(),
            },
        )

        self.assertIn("created_at", access_pass.metadata)
        self.assertTrue(isinstance(access_pass.metadata["created_at"], str))
        self.assertIn("tags", access_pass.metadata)
        self.assertTrue(isinstance(access_pass.metadata["tags"], list))
        self.assertIn("99", access_pass.metadata)
        self.assertTrue(isinstance(access_pass.metadata["99"], str))

    def test_send_invitation_sms_records_delivery_metadata(self):
        invitation = Invitation.objects.create(
            enrollment=self.enrollment,
            channel="sms",
            send_to=self.candidate.phone_number,
            expires_at=timezone.now() + timedelta(hours=24),
            created_by=self.hr,
        )

        send_invitation(invitation)

        access_pass = CandidateAccessPass.objects.get(invitation=invitation)
        self.assertEqual(access_pass.metadata.get("delivery_channel"), "sms")
        self.assertEqual(access_pass.metadata.get("delivery_target"), invitation.send_to)
        self.assertIn("access_url", access_pass.metadata)

    def test_send_invitation_unsupported_channel_does_not_issue_access_pass(self):
        invitation = Invitation.objects.create(
            enrollment=self.enrollment,
            channel="email",
            send_to=self.candidate.email,
            expires_at=timezone.now() + timedelta(hours=24),
            created_by=self.hr,
        )
        Invitation.objects.filter(id=invitation.id).update(channel="fax")
        invitation.refresh_from_db()

        with self.assertRaises(CandidateAccessError) as exc:
            send_invitation(invitation)

        self.assertEqual(exc.exception.code, "unsupported_channel")
        self.assertEqual(CandidateAccessPass.objects.filter(invitation=invitation).count(), 0)

