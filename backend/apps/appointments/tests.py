from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.audit.contracts import (
    APPOINTMENT_FINAL_DECISION_RECORDED_EVENT,
    APPOINTMENT_NOMINATION_CREATED_EVENT,
    APPOINTMENT_PUBLICATION_PUBLISHED_EVENT,
    APPOINTMENT_PUBLICATION_REVOKED_EVENT,
    APPOINTMENT_RECORD_CREATED_EVENT,
    APPOINTMENT_RECORD_DELETED_EVENT,
    APPOINTMENT_RECORD_UPDATED_EVENT,
    APPOINTMENT_STAGE_ACTION_TAKEN_EVENT,
    APPOINTMENT_STAGE_TRANSITION_EVENT,
    APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
)
from apps.authentication.models import User
from apps.authentication.permissions import (
    RECENT_AUTH_REQUIRED_CODE,
    RECENT_AUTH_SESSION_KEY,
)
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.applications.models import VettingCase
from apps.invitations.models import Invitation
from apps.governance.models import Committee, CommitteeMembership, Organization, OrganizationMembership
from apps.notifications.models import Notification
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition
from apps.rubrics.decision_engine import VettingDecisionEngine
from apps.rubrics.engine import RubricEvaluationEngine
from apps.rubrics.models import VettingRubric

from .models import AppointmentPublication, AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from .services import (
    InvalidTransitionError,
    LinkageValidationError,
    StageAuthorizationError,
    advance_stage,
    ensure_vetting_linkage_for_appointment,
)


class AppointmentTransitionServiceTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="appointments_admin@example.com",
            password="Pass1234!",
            first_name="Appoint",
            last_name="Admin",
            user_type="admin",
        )
        self.candidate = Candidate.objects.create(
            first_name="Nominee",
            last_name="One",
            email="nominee_one@example.com",
        )
        self.nominee = PersonnelRecord.objects.create(
            full_name="Nominee One",
            linked_candidate=self.candidate,
            is_public=True,
        )
        self.position = GovernmentPosition.objects.create(
            title="Minister of Finance",
            branch="executive",
            institution="Ministry of Finance",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        self.exercise = VettingCampaign.objects.create(
            name="Ministerial Appointments 2026",
            initiated_by=self.admin_user,
            status="active",
        )
        self.appointment = AppointmentRecord.objects.create(
            position=self.position,
            nominee=self.nominee,
            appointment_exercise=self.exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="H.E. President",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )
        self.hr_user = User.objects.create_user(
            email="appointments_hr@example.com",
            password="Pass1234!",
            first_name="Vetting",
            last_name="Officer",
            user_type="hr_manager",
        )
        self.committee_user = User.objects.create_user(
            email="appointments_committee@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Member",
            user_type="hr_manager",
        )
        self.vetting_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.committee_group, _ = Group.objects.get_or_create(name="committee_member")
        self.authority_group, _ = Group.objects.get_or_create(name="appointing_authority")
        self.hr_user.groups.add(self.vetting_group)
        self.committee_user.groups.add(self.committee_group)

    def _attach_case_with_vetting_decision(
        self,
        *,
        recommendation_status: str = "recommend_manual_review",
        blocking_issues: list | None = None,
    ):
        applicant = User.objects.create_user(
            email=f"decision.case.{uuid4().hex[:8]}@example.com",
            password="Pass1234!",
            first_name="Decision",
            last_name="Applicant",
            user_type="applicant",
        )
        case = VettingCase.objects.create(
            applicant=applicant,
            assigned_to=self.hr_user,
            position_applied=self.position.title,
            department=self.position.institution[:100],
            priority="medium",
            status="under_review",
            documents_uploaded=True,
            documents_verified=True,
            interview_completed=True,
            document_authenticity_score=88,
            consistency_score=84,
            fraud_risk_score=15,
            interview_score=82,
        )
        self.appointment.vetting_case = case
        self.appointment.save(update_fields=["vetting_case", "updated_at"])

        rubric = VettingRubric.objects.create(
            name=f"Decision Gate Rubric {uuid4().hex[:8]}",
            is_active=True,
            created_by=self.admin_user,
        )
        evaluation = RubricEvaluationEngine(case=case, rubric=rubric).evaluate(evaluated_by=self.admin_user)
        recommendation = VettingDecisionEngine.generate_recommendation(
            evaluation=evaluation,
            actor=self.admin_user,
        )
        changed_fields = []
        if recommendation_status:
            recommendation.recommendation_status = recommendation_status
            changed_fields.append("recommendation_status")
        if blocking_issues is not None:
            recommendation.blocking_issues = blocking_issues
            changed_fields.append("blocking_issues")
        if changed_fields:
            recommendation.save(update_fields=[*changed_fields, "updated_at"])
        return case, evaluation, recommendation

    def test_valid_transition_creates_stage_action(self):
        updated = advance_stage(
            appointment=self.appointment,
            new_status="under_vetting",
            actor=self.admin_user,
        )
        self.assertEqual(updated.status, "under_vetting")
        self.assertEqual(updated.stage_actions.count(), 1)
        action = updated.stage_actions.first()
        self.assertEqual(action.previous_status, "nominated")
        self.assertEqual(action.new_status, "under_vetting")

    def test_invalid_transition_raises_error(self):
        with self.assertRaises(InvalidTransitionError):
            advance_stage(
                appointment=self.appointment,
                new_status="appointed",
                actor=self.admin_user,
            )

    def test_stage_role_enforced(self):
        template = ApprovalStageTemplate.objects.create(
            name="Ministerial Standard",
            exercise_type="ministerial",
            created_by=self.admin_user,
        )
        stage = ApprovalStage.objects.create(
            template=template,
            order=1,
            name="Committee Review",
            required_role="committee_member",
            maps_to_status="committee_review",
        )

        self.appointment.status = "under_vetting"
        self.appointment.save(update_fields=["status", "updated_at"])

        with self.assertRaises(StageAuthorizationError):
            advance_stage(
                appointment=self.appointment,
                new_status="committee_review",
                actor=self.hr_user,
                stage=stage,
            )

        updated = advance_stage(
            appointment=self.appointment,
            new_status="committee_review",
            actor=self.committee_user,
            stage=stage,
        )
        self.assertEqual(updated.status, "committee_review")

    def test_finalize_decision_requires_authority_or_admin(self):
        self.appointment.status = "committee_review"
        self.appointment.save(update_fields=["status", "updated_at"])

        with self.assertRaises(StageAuthorizationError):
            advance_stage(
                appointment=self.appointment,
                new_status="appointed",
                actor=self.hr_user,
            )

        self.hr_user.groups.add(self.authority_group)
        updated = advance_stage(
            appointment=self.appointment,
            new_status="appointed",
            actor=self.hr_user,
        )
        self.assertEqual(updated.status, "appointed")

    def test_transition_with_linked_case_requires_rubric_evaluation(self):
        applicant = User.objects.create_user(
            email=f"missing.eval.{uuid4().hex[:8]}@example.com",
            password="Pass1234!",
            first_name="Missing",
            last_name="Eval",
            user_type="applicant",
        )
        case = VettingCase.objects.create(
            applicant=applicant,
            assigned_to=self.hr_user,
            position_applied=self.position.title,
            department=self.position.institution[:100],
            priority="medium",
            status="under_review",
            documents_uploaded=True,
            documents_verified=True,
        )
        self.appointment.vetting_case = case
        self.appointment.status = "under_vetting"
        self.appointment.save(update_fields=["vetting_case", "status", "updated_at"])

        with self.assertRaises(InvalidTransitionError):
            advance_stage(
                appointment=self.appointment,
                new_status="committee_review",
                actor=self.admin_user,
            )

    def test_confirmation_pending_with_blocking_issues_requires_reason_or_override(self):
        self._attach_case_with_vetting_decision(
            recommendation_status="recommend_manual_review",
            blocking_issues=[
                {
                    "code": "documents_unverified",
                    "severity": "blocking",
                    "source": "policy_rule",
                    "message": "Documents are not fully verified.",
                }
            ],
        )
        self.appointment.status = "committee_review"
        self.appointment.save(update_fields=["status", "updated_at"])

        with self.assertRaises(InvalidTransitionError):
            advance_stage(
                appointment=self.appointment,
                new_status="confirmation_pending",
                actor=self.admin_user,
            )

        updated = advance_stage(
            appointment=self.appointment,
            new_status="confirmation_pending",
            actor=self.admin_user,
            reason_note="Committee accepted temporary blocker with explicit mitigation plan.",
        )
        self.assertEqual(updated.status, "confirmation_pending")

    def test_appointed_transition_with_reject_recommendation_requires_override(self):
        _case, _evaluation, recommendation = self._attach_case_with_vetting_decision(
            recommendation_status="recommend_reject",
            blocking_issues=[],
        )
        self.appointment.status = "confirmation_pending"
        self.appointment.save(update_fields=["status", "updated_at"])

        with self.assertRaises(InvalidTransitionError):
            advance_stage(
                appointment=self.appointment,
                new_status="appointed",
                actor=self.admin_user,
                reason_note="Attempting to proceed without formal override.",
            )

        VettingDecisionEngine.record_human_override(
            recommendation=recommendation,
            actor=self.admin_user,
            overridden_recommendation_status="recommend_approve",
            rationale="Statutory appointing authority exercised after full human review.",
        )

        updated = advance_stage(
            appointment=self.appointment,
            new_status="appointed",
            actor=self.admin_user,
            reason_note="Override recorded and acknowledged.",
        )
        self.assertEqual(updated.status, "appointed")

    def test_ensure_vetting_linkage_creates_enrollment_and_case(self):
        linked = ensure_vetting_linkage_for_appointment(appointment=self.appointment, actor=self.admin_user)
        self.assertIsNotNone(linked.vetting_case_id)
        enrollment = CandidateEnrollment.objects.filter(
            campaign=self.exercise,
            candidate=self.candidate,
        ).first()
        self.assertIsNotNone(enrollment)
        case = VettingCase.objects.filter(candidate_enrollment=enrollment).first()
        self.assertIsNotNone(case)
        self.assertEqual(case.id, linked.vetting_case_id)
        self.assertTrue(Invitation.objects.filter(enrollment=enrollment).exists())

    def test_ensure_vetting_linkage_is_idempotent_for_invitation(self):
        ensure_vetting_linkage_for_appointment(appointment=self.appointment, actor=self.admin_user)
        first_count = Invitation.objects.filter(enrollment__campaign=self.exercise, enrollment__candidate=self.candidate).count()

        ensure_vetting_linkage_for_appointment(appointment=self.appointment, actor=self.admin_user)
        second_count = Invitation.objects.filter(enrollment__campaign=self.exercise, enrollment__candidate=self.candidate).count()

        self.assertEqual(first_count, second_count)

    @patch("apps.invitations.tasks.send_invitation_task.delay", side_effect=RuntimeError("broker down"))
    def test_ensure_vetting_linkage_tolerates_invitation_dispatch_failures(self, _mock_invite_delay):
        linked = ensure_vetting_linkage_for_appointment(appointment=self.appointment, actor=self.admin_user)
        self.assertIsNotNone(linked.vetting_case_id)
        self.assertTrue(
            Invitation.objects.filter(
                enrollment__campaign=self.exercise,
                enrollment__candidate=self.candidate,
            ).exists()
        )

    def test_serving_transition_updates_position_holder(self):
        self.appointment.status = "appointed"
        self.appointment.save(update_fields=["status", "updated_at"])

        updated = advance_stage(
            appointment=self.appointment,
            new_status="serving",
            actor=self.admin_user,
        )

        self.position.refresh_from_db()
        self.nominee.refresh_from_db()
        self.assertEqual(updated.status, "serving")
        self.assertIsNotNone(updated.appointment_date)
        self.assertEqual(self.position.current_holder_id, self.nominee.id)
        self.assertFalse(self.position.is_vacant)
        self.assertTrue(self.nominee.is_active_officeholder)

    def test_exited_transition_clears_position_holder(self):
        self.appointment.status = "appointed"
        self.appointment.save(update_fields=["status", "updated_at"])
        advance_stage(
            appointment=self.appointment,
            new_status="serving",
            actor=self.admin_user,
        )

        updated = advance_stage(
            appointment=self.appointment,
            new_status="exited",
            actor=self.admin_user,
        )

        self.position.refresh_from_db()
        self.nominee.refresh_from_db()
        self.assertEqual(updated.status, "exited")
        self.assertIsNotNone(updated.exit_date)
        self.assertIsNone(self.position.current_holder_id)
        self.assertTrue(self.position.is_vacant)
        self.assertFalse(self.nominee.is_active_officeholder)

    def test_exited_transition_preserves_reassigned_current_holder(self):
        replacement = PersonnelRecord.objects.create(
            full_name="Replacement Officeholder",
            is_public=True,
            is_active_officeholder=True,
        )
        self.appointment.status = "appointed"
        self.appointment.save(update_fields=["status", "updated_at"])
        advance_stage(
            appointment=self.appointment,
            new_status="serving",
            actor=self.admin_user,
        )

        # Simulate registry correction/reassignment before this appointment exits.
        self.position.current_holder = replacement
        self.position.is_vacant = False
        self.position.save(update_fields=["current_holder", "is_vacant", "updated_at"])

        updated = advance_stage(
            appointment=self.appointment,
            new_status="exited",
            actor=self.admin_user,
        )

        self.position.refresh_from_db()
        self.nominee.refresh_from_db()
        self.assertEqual(updated.status, "exited")
        self.assertIsNotNone(updated.exit_date)
        self.assertEqual(self.position.current_holder_id, replacement.id)
        self.assertFalse(self.position.is_vacant)
        self.assertFalse(self.nominee.is_active_officeholder)

    def test_required_stage_context_enforced_when_campaign_template_exists(self):
        template = ApprovalStageTemplate.objects.create(
            name="Ministerial Required Chain",
            exercise_type="ministerial",
            created_by=self.admin_user,
        )
        stage = ApprovalStage.objects.create(
            template=template,
            order=1,
            name="Vetting Desk Review",
            required_role="vetting_officer",
            is_required=True,
            maps_to_status="under_vetting",
        )
        self.exercise.approval_template = template
        self.exercise.save(update_fields=["approval_template", "updated_at"])

        with self.assertRaises(InvalidTransitionError):
            advance_stage(
                appointment=self.appointment,
                new_status="under_vetting",
                actor=self.admin_user,
            )

        updated = advance_stage(
            appointment=self.appointment,
            new_status="under_vetting",
            actor=self.hr_user,
            stage=stage,
        )
        self.assertEqual(updated.status, "under_vetting")

    def test_ensure_vetting_linkage_rejects_campaign_position_mismatch(self):
        self.exercise.positions.add(self.position)
        other_position = GovernmentPosition.objects.create(
            title="Minister of Transport",
            branch="executive",
            institution="Ministry of Transport",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        mismatched = AppointmentRecord.objects.create(
            position=other_position,
            nominee=self.nominee,
            appointment_exercise=self.exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="H.E. President",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )

        with self.assertRaises(LinkageValidationError):
            ensure_vetting_linkage_for_appointment(appointment=mismatched, actor=self.admin_user)


class AppointmentIntegrityConstraintTests(TestCase):
    def setUp(self):
        self.position = GovernmentPosition.objects.create(
            title="Auditor-General",
            branch="executive",
            institution="Audit Service",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        self.nominee_one = PersonnelRecord.objects.create(full_name="Nominee One")
        self.nominee_two = PersonnelRecord.objects.create(full_name="Nominee Two")

    def _create_record(self, *, nominee, status, appointment_date=None, exit_date=None):
        return AppointmentRecord.objects.create(
            position=self.position,
            nominee=nominee,
            nominated_by_display="Constitutional Authority",
            nomination_date=date.today(),
            status=status,
            appointment_date=appointment_date,
            exit_date=exit_date,
            is_public=False,
        )

    def test_prevents_multiple_serving_records_for_same_position(self):
        self._create_record(
            nominee=self.nominee_one,
            status="serving",
            appointment_date=date.today(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create_record(
                    nominee=self.nominee_two,
                    status="serving",
                    appointment_date=date.today(),
                )

    def test_prevents_multiple_active_records_for_same_position_nominee(self):
        self._create_record(
            nominee=self.nominee_one,
            status="nominated",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create_record(
                    nominee=self.nominee_one,
                    status="under_vetting",
                )

    def test_allows_new_active_record_after_terminal_status(self):
        self._create_record(
            nominee=self.nominee_one,
            status="withdrawn",
        )
        created = self._create_record(
            nominee=self.nominee_one,
            status="nominated",
        )
        self.assertEqual(created.status, "nominated")

    def test_prevents_exit_date_when_status_is_not_exited(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create_record(
                    nominee=self.nominee_one,
                    status="appointed",
                    appointment_date=date.today(),
                    exit_date=date.today(),
                )

    def test_prevents_exited_without_exit_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create_record(
                    nominee=self.nominee_one,
                    status="exited",
                    appointment_date=date.today(),
                )

    def test_prevents_serving_without_appointment_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create_record(
                    nominee=self.nominee_one,
                    status="serving",
                )

    def test_prevents_exited_without_appointment_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create_record(
                    nominee=self.nominee_one,
                    status="exited",
                    exit_date=date.today(),
                )


class AppointmentPublicApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="appointments_admin2@example.com",
            password="Pass1234!",
            first_name="Appoint",
            last_name="Admin",
            user_type="admin",
        )
        self.client.force_authenticate(self.admin_user)
        candidate = Candidate.objects.create(
            first_name="Nominee",
            last_name="Two",
            email="nominee_two@example.com",
        )
        nominee = PersonnelRecord.objects.create(full_name="Nominee Two", linked_candidate=candidate, is_public=True)
        position = GovernmentPosition.objects.create(
            title="Minister of Education",
            branch="executive",
            institution="Ministry of Education",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        campaign = VettingCampaign.objects.create(
            name="Ministerial Appointments 2027",
            initiated_by=self.admin_user,
            status="active",
        )
        self.record = AppointmentRecord.objects.create(
            position=position,
            nominee=nominee,
            appointment_exercise=campaign,
            nominated_by_user=self.admin_user,
            nominated_by_display="H.E. President",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )
        self.vetting_user = User.objects.create_user(
            email="vetting.user@example.com",
            password="Pass1234!",
            first_name="Vetting",
            last_name="Officer",
            user_type="hr_manager",
        )
        self.ordinary_hr_user = User.objects.create_user(
            email="ordinary.hr@example.com",
            password="Pass1234!",
            first_name="Ordinary",
            last_name="HR",
            user_type="hr_manager",
        )
        self.committee_user = User.objects.create_user(
            email="committee.user@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="User",
            user_type="hr_manager",
        )
        self.committee_chair_user = User.objects.create_user(
            email="committee.chair@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Chair",
            user_type="hr_manager",
        )
        self.authority_user = User.objects.create_user(
            email="authority.user@example.com",
            password="Pass1234!",
            first_name="Authority",
            last_name="User",
            user_type="hr_manager",
        )
        self.publication_user = User.objects.create_user(
            email="publication.user@example.com",
            password="Pass1234!",
            first_name="Publication",
            last_name="Officer",
            user_type="hr_manager",
        )
        self.applicant_user = User.objects.create_user(
            email="appointments_applicant@example.com",
            password="Pass1234!",
            first_name="Appointment",
            last_name="Applicant",
            user_type="applicant",
        )
        self.vetting_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.committee_group, _ = Group.objects.get_or_create(name="committee_member")
        self.committee_chair_group, _ = Group.objects.get_or_create(name="committee_chair")
        self.authority_group, _ = Group.objects.get_or_create(name="appointing_authority")
        self.publication_group, _ = Group.objects.get_or_create(name="publication_officer")
        self.vetting_user.groups.add(self.vetting_group)
        self.committee_user.groups.add(self.committee_group)
        self.committee_chair_user.groups.add(self.committee_chair_group)
        self.authority_user.groups.add(self.authority_group)
        self.publication_user.groups.add(self.publication_group)
        self._nominee_seq = 0

    def _build_nominee(self):
        self._nominee_seq += 1
        suffix = self._nominee_seq
        candidate = Candidate.objects.create(
            first_name="Extra",
            last_name=f"Nominee{suffix}",
            email=f"extra.nominee.{suffix}@example.com",
        )
        return PersonnelRecord.objects.create(
            full_name=f"Extra Nominee {suffix}",
            linked_candidate=candidate,
            is_public=True,
        )

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

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def _assert_audit_row_exists(self, *, action: str, entity_id: str, expected_event: str | None = None):
        if "apps.audit" not in settings.INSTALLED_APPS:
            return
        from apps.audit.models import AuditLog

        queryset = AuditLog.objects.filter(
            action=action,
            entity_type="AppointmentRecord",
            entity_id=str(entity_id),
        )
        if expected_event:
            queryset = queryset.filter(changes__event=expected_event)
        row = queryset.order_by("-created_at").first()
        self.assertIsNotNone(row)
        if expected_event:
            self.assertEqual((row.changes or {}).get("event"), expected_event)

    def _assert_audit_event_exists(self, *, event: str, entity_id: str, action: str = "update"):
        if "apps.audit" not in settings.INSTALLED_APPS:
            return
        from apps.audit.models import AuditLog

        self.assertTrue(
            AuditLog.objects.filter(
                action=action,
                entity_type="AppointmentRecord",
                entity_id=str(entity_id),
                changes__event=event,
            ).exists()
        )

    def _notification_count_for_event(self, *, event_type: str, record: AppointmentRecord | None = None) -> int:
        target = record or self.record
        return Notification.objects.filter(
            metadata__event_type=event_type,
            metadata__appointment_id=str(target.id),
        ).count()

    def _publish_record(self, *, record: AppointmentRecord | None = None, actor: User | None = None):
        target = record or self.record
        publisher = actor or self.authority_user
        self._authenticate_with_recent_auth(publisher)
        return self.client.post(
            f"/api/appointments/records/{target.id}/publish/",
            {
                "publication_reference": f"GOV-GAZ-{str(target.id)[:8]}",
                "publication_document_hash": "a" * 64,
                "publication_notes": "Published in official gazette.",
                "gazette_number": f"GZT-{str(target.id)[:8]}",
                "gazette_date": str(date.today()),
            },
            format="json",
        )

    def test_create_record_auto_links_vetting_case(self):
        nominee = self._build_nominee()
        response = self.client.post(
            "/api/appointments/records/",
            {
                "position": str(self.record.position_id),
                "nominee": str(nominee.id),
                "appointment_exercise": str(self.record.appointment_exercise_id),
                "nominated_by_display": "H.E. President",
                "nominated_by_org": "Office of the President",
                "nomination_date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        created_id = response.json()["id"]
        created = AppointmentRecord.objects.get(id=created_id)
        self.assertIsNotNone(created.vetting_case_id)
        self.assertTrue(Invitation.objects.filter(enrollment__campaign=created.appointment_exercise).exists())
        self._assert_audit_row_exists(
            action="create",
            entity_id=created_id,
            expected_event=APPOINTMENT_RECORD_CREATED_EVENT,
        )

    @patch("apps.invitations.tasks.send_invitation_task.delay", return_value=None)
    def test_create_record_emits_nomination_lifecycle_audit_and_notification(self, _mock_invite_delay):
        nominee = self._build_nominee()
        response = self.client.post(
            "/api/appointments/records/",
            {
                "position": str(self.record.position_id),
                "nominee": str(nominee.id),
                "appointment_exercise": str(self.record.appointment_exercise_id),
                "nominated_by_display": "H.E. President",
                "nominated_by_org": "Office of the President",
                "nomination_date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        created_id = response.json()["id"]
        self._assert_audit_event_exists(
            event=APPOINTMENT_NOMINATION_CREATED_EVENT,
            action="create",
            entity_id=created_id,
        )
        self.assertGreater(
            Notification.objects.filter(
                metadata__event_type="appointment_nomination_created",
                metadata__appointment_id=created_id,
            ).count(),
            0,
        )

    def test_list_records_allows_hr_and_admin_but_blocks_applicant(self):
        self.client.force_authenticate(user=None)
        unauthenticated = self.client.get("/api/appointments/records/")
        self.assertIn(unauthenticated.status_code, {401, 403})

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.get("/api/appointments/records/")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.ordinary_hr_user)
        hr_allowed = self.client.get("/api/appointments/records/")
        self.assertEqual(hr_allowed.status_code, 200)
        self.assertGreaterEqual(len(self._extract_results(hr_allowed)), 1)

        self.client.force_authenticate(self.admin_user)
        admin_allowed = self.client.get("/api/appointments/records/")
        self.assertEqual(admin_allowed.status_code, 200)
        self.assertGreaterEqual(len(self._extract_results(admin_allowed)), 1)

    def test_create_record_allows_hr_and_admin_but_blocks_applicant(self):
        first_nominee = self._build_nominee()
        second_nominee = self._build_nominee()
        hr_org = Organization.objects.create(
            code=f"appt-public-create-{uuid4().hex[:8]}",
            name=f"Appointments Public Create Org {uuid4().hex[:6]}",
        )
        OrganizationMembership.objects.create(
            user=self.ordinary_hr_user,
            organization=hr_org,
            is_active=True,
            is_default=True,
        )
        payload = {
            "position": str(self.record.position_id),
            "nominee": str(first_nominee.id),
            "nominated_by_display": "H.E. President",
            "nominated_by_org": "Office of the President",
            "nomination_date": str(date.today()),
            "organization": str(hr_org.id),
        }

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.post("/api/appointments/records/", payload, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.ordinary_hr_user)
        hr_allowed = self.client.post("/api/appointments/records/", payload, format="json")
        self.assertEqual(hr_allowed.status_code, 201)
        self._assert_audit_row_exists(
            action="create",
            entity_id=hr_allowed.json()["id"],
            expected_event=APPOINTMENT_RECORD_CREATED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_allowed = self.client.post(
            "/api/appointments/records/",
            {
                **payload,
                "nominee": str(second_nominee.id),
            },
            format="json",
        )
        self.assertEqual(admin_allowed.status_code, 201)
        self._assert_audit_row_exists(
            action="create",
            entity_id=admin_allowed.json()["id"],
            expected_event=APPOINTMENT_RECORD_CREATED_EVENT,
        )

    def test_update_record_allows_hr_and_admin_but_blocks_applicant(self):
        detail_url = f"/api/appointments/records/{self.record.id}/"

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.patch(detail_url, {"committee_recommendation": "Blocked update"}, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.ordinary_hr_user)
        hr_allowed = self.client.patch(
            detail_url,
            {"committee_recommendation": "Update by HR"},
            format="json",
        )
        self.assertEqual(hr_allowed.status_code, 200)

        self.client.force_authenticate(self.admin_user)
        admin_allowed = self.client.patch(
            detail_url,
            {"committee_recommendation": "Update by Admin"},
            format="json",
        )
        self.assertEqual(admin_allowed.status_code, 200)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=APPOINTMENT_RECORD_UPDATED_EVENT,
        )

    def test_delete_record_allows_hr_and_admin_but_blocks_applicant(self):
        blocked_nominee = self._build_nominee()
        hr_nominee = self._build_nominee()
        admin_nominee = self._build_nominee()
        blocked_record = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=blocked_nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="Blocked Delete",
            nomination_date=date.today(),
            status="nominated",
            is_public=False,
        )
        hr_record = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=hr_nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="HR Delete",
            nomination_date=date.today(),
            status="nominated",
            is_public=False,
        )
        admin_record = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=admin_nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="Admin Delete",
            nomination_date=date.today(),
            status="nominated",
            is_public=False,
        )

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.delete(f"/api/appointments/records/{blocked_record.id}/")
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(AppointmentRecord.objects.filter(id=blocked_record.id).exists())

        self.client.force_authenticate(self.ordinary_hr_user)
        hr_allowed = self.client.delete(f"/api/appointments/records/{hr_record.id}/")
        self.assertEqual(hr_allowed.status_code, 204)
        self.assertFalse(AppointmentRecord.objects.filter(id=hr_record.id).exists())
        self._assert_audit_row_exists(
            action="delete",
            entity_id=str(hr_record.id),
            expected_event=APPOINTMENT_RECORD_DELETED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_allowed = self.client.delete(f"/api/appointments/records/{admin_record.id}/")
        self.assertEqual(admin_allowed.status_code, 204)
        self.assertFalse(AppointmentRecord.objects.filter(id=admin_record.id).exists())
        self._assert_audit_row_exists(
            action="delete",
            entity_id=str(admin_record.id),
            expected_event=APPOINTMENT_RECORD_DELETED_EVENT,
        )

    def test_appoint_endpoint_requires_appointing_authority_or_admin(self):
        self.record.status = "committee_review"
        self.record.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.ordinary_hr_user)
        denied = self.client.post(f"/api/appointments/records/{self.record.id}/appoint/", {}, format="json")
        self.assertEqual(denied.status_code, 403)

        self._authenticate_with_recent_auth(self.authority_user)
        allowed = self.client.post(f"/api/appointments/records/{self.record.id}/appoint/", {}, format="json")
        self.assertEqual(allowed.status_code, 200)

    def test_appoint_endpoint_rejects_staff_without_admin_or_authority_role(self):
        self.record.status = "committee_review"
        self.record.save(update_fields=["status", "updated_at"])

        staff_operator = User.objects.create_user(
            email="staff.operator.appoint@example.com",
            password="Pass1234!",
            first_name="Staff",
            last_name="Operator",
            user_type="hr_manager",
            is_staff=True,
        )
        self._authenticate_with_recent_auth(staff_operator)

        denied = self.client.post(f"/api/appointments/records/{self.record.id}/appoint/", {}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_appoint_emits_final_decision_audit_and_notifications(self):
        self.record.status = "committee_review"
        self.record.save(update_fields=["status", "updated_at"])

        self._authenticate_with_recent_auth(self.authority_user)
        response = self.client.post(f"/api/appointments/records/{self.record.id}/appoint/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self._assert_audit_event_exists(
            event=APPOINTMENT_FINAL_DECISION_RECORDED_EVENT,
            entity_id=str(self.record.id),
        )
        self.assertGreater(self._notification_count_for_event(event_type="appointment_approved"), 0)
        self.assertGreater(self._notification_count_for_event(event_type="appointment_appointed"), 0)

    def test_appoint_requires_recent_auth_for_authorized_actor(self):
        self.record.status = "committee_review"
        self.record.save(update_fields=["status", "updated_at"])

        self._authenticate_without_recent_auth(self.authority_user)
        denied = self.client.post(f"/api/appointments/records/{self.record.id}/appoint/", {}, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual((denied.json() or {}).get("code"), RECENT_AUTH_REQUIRED_CODE)

        self._authenticate_with_recent_auth(self.authority_user)
        allowed = self.client.post(f"/api/appointments/records/{self.record.id}/appoint/", {}, format="json")
        self.assertEqual(allowed.status_code, 200)

    def test_advance_stage_requires_stage_actor_group(self):
        self.record.status = "under_vetting"
        self.record.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.ordinary_hr_user)
        denied = self.client.post(
            f"/api/appointments/records/{self.record.id}/advance-stage/",
            {"status": "committee_review"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.committee_user)
        allowed = self.client.post(
            f"/api/appointments/records/{self.record.id}/advance-stage/",
            {"status": "committee_review"},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=APPOINTMENT_STAGE_TRANSITION_EVENT,
        )

    def test_advance_stage_emits_stage_action_audit_and_committee_notification(self):
        self.record.status = "under_vetting"
        self.record.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.committee_user)
        response = self.client.post(
            f"/api/appointments/records/{self.record.id}/advance-stage/",
            {"status": "committee_review"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self._assert_audit_event_exists(
            event=APPOINTMENT_STAGE_ACTION_TAKEN_EVENT,
            entity_id=str(self.record.id),
        )
        self.assertGreater(
            self._notification_count_for_event(
                event_type="appointment_moved_to_committee_review",
            ),
            0,
        )

    def test_committee_chair_can_advance_committee_stage(self):
        self.record.status = "under_vetting"
        self.record.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.committee_chair_user)
        response = self.client.post(
            f"/api/appointments/records/{self.record.id}/advance-stage/",
            {"status": "committee_review"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_advance_stage_requires_stage_id_when_template_requires_status(self):
        template = ApprovalStageTemplate.objects.create(
            name="Committee Chain",
            exercise_type="ministerial",
            created_by=self.admin_user,
        )
        stage = ApprovalStage.objects.create(
            template=template,
            order=1,
            name="Committee Review",
            required_role="committee_member",
            is_required=True,
            maps_to_status="committee_review",
        )
        campaign = self.record.appointment_exercise
        campaign.approval_template = template
        campaign.save(update_fields=["approval_template", "updated_at"])
        self.record.status = "under_vetting"
        self.record.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.committee_user)
        denied = self.client.post(
            f"/api/appointments/records/{self.record.id}/advance-stage/",
            {"status": "committee_review"},
            format="json",
        )
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(denied.json().get("code"), "invalid_transition")

        allowed = self.client.post(
            f"/api/appointments/records/{self.record.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(stage.id)},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)

    def test_create_record_rejects_position_not_linked_to_campaign(self):
        linked_position = self.record.position
        unlinked_position = GovernmentPosition.objects.create(
            title="Minister of Health",
            branch="executive",
            institution="Ministry of Health",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        campaign = self.record.appointment_exercise
        campaign.positions.clear()
        campaign.positions.add(linked_position)

        response = self.client.post(
            "/api/appointments/records/",
            {
                "position": str(unlinked_position.id),
                "nominee": str(self.record.nominee_id),
                "appointment_exercise": str(campaign.id),
                "nominated_by_display": "H.E. President",
                "nominated_by_org": "Office of the President",
                "nomination_date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("position", response.json())

    def test_appoint_requires_stage_id_when_template_requires_final_stage(self):
        template = ApprovalStageTemplate.objects.create(
            name="Final Decision Chain",
            exercise_type="ministerial",
            created_by=self.admin_user,
        )
        final_stage = ApprovalStage.objects.create(
            template=template,
            order=1,
            name="Appointing Authority Decision",
            required_role="appointing_authority",
            is_required=True,
            maps_to_status="appointed",
        )
        campaign = self.record.appointment_exercise
        campaign.approval_template = template
        campaign.save(update_fields=["approval_template", "updated_at"])

        self.record.status = "committee_review"
        self.record.save(update_fields=["status", "updated_at"])

        self._authenticate_with_recent_auth(self.authority_user)
        denied = self.client.post(
            f"/api/appointments/records/{self.record.id}/appoint/",
            {},
            format="json",
        )
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(denied.json().get("code"), "invalid_transition")

        allowed = self.client.post(
            f"/api/appointments/records/{self.record.id}/appoint/",
            {"stage_id": str(final_stage.id)},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)

    def test_ensure_vetting_linkage_action_logs_event(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            f"/api/appointments/records/{self.record.id}/ensure-vetting-linkage/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
        )

    def test_publish_flow_creates_publication_provenance_and_audit(self):
        self.record.is_public = False
        self.record.save(update_fields=["is_public", "updated_at"])

        response = self._publish_record()
        self.assertEqual(response.status_code, 200)

        self.record.refresh_from_db()
        publication = AppointmentPublication.objects.get(appointment=self.record)
        self.assertEqual(publication.status, "published")
        self.assertIsNotNone(publication.published_at)
        self.assertEqual(publication.published_by_id, self.authority_user.id)
        self.assertEqual(publication.publication_document_hash, "a" * 64)
        self.assertTrue(self.record.is_public)
        self.assertTrue(self.record.gazette_number.startswith("GZT-"))
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=APPOINTMENT_PUBLICATION_PUBLISHED_EVENT,
        )

    def test_publish_and_revoke_allow_publication_officer(self):
        self.client.force_authenticate(self.ordinary_hr_user)
        denied_publish = self.client.post(
            f"/api/appointments/records/{self.record.id}/publish/",
            {"publication_reference": "GOV-GAZ-DENIED", "publication_document_hash": "a" * 64},
            format="json",
        )
        self.assertEqual(denied_publish.status_code, 403)

        self._authenticate_with_recent_auth(self.publication_user)
        publish = self.client.post(
            f"/api/appointments/records/{self.record.id}/publish/",
            {
                "publication_reference": "GOV-GAZ-PUBROLE",
                "publication_document_hash": "a" * 64,
            },
            format="json",
        )
        self.assertEqual(publish.status_code, 200)

        revoke = self.client.post(
            f"/api/appointments/records/{self.record.id}/revoke-publication/",
            {"revocation_reason": "Publication correction", "make_private": True},
            format="json",
        )
        self.assertEqual(revoke.status_code, 200)

    def test_publish_requires_recent_auth_for_authorized_actor(self):
        self._authenticate_without_recent_auth(self.publication_user)
        denied = self.client.post(
            f"/api/appointments/records/{self.record.id}/publish/",
            {
                "publication_reference": "GOV-GAZ-STEPUP",
                "publication_document_hash": "a" * 64,
            },
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual((denied.json() or {}).get("code"), RECENT_AUTH_REQUIRED_CODE)

        self._authenticate_with_recent_auth(self.publication_user)
        allowed = self.client.post(
            f"/api/appointments/records/{self.record.id}/publish/",
            {
                "publication_reference": "GOV-GAZ-STEPUP-OK",
                "publication_document_hash": "a" * 64,
            },
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)

    def test_repeated_publish_does_not_duplicate_publication_notifications(self):
        first = self._publish_record()
        self.assertEqual(first.status_code, 200)
        first_count = self._notification_count_for_event(event_type="appointment_published")
        self.assertGreater(first_count, 0)

        second = self._publish_record()
        self.assertEqual(second.status_code, 200)
        second_count = self._notification_count_for_event(event_type="appointment_published")
        self.assertEqual(first_count, second_count)

    def test_revoke_flow_hides_record_from_public_feed_and_audit(self):
        publish_response = self._publish_record()
        self.assertEqual(publish_response.status_code, 200)

        self.client.force_authenticate(user=None)
        feed_before = self.client.get("/api/appointments/records/gazette-feed/")
        self.assertEqual(feed_before.status_code, 200)
        before_ids = {str(item["id"]) for item in feed_before.json()}
        self.assertIn(str(self.record.id), before_ids)

        self._authenticate_with_recent_auth(self.authority_user)
        revoke_response = self.client.post(
            f"/api/appointments/records/{self.record.id}/revoke-publication/",
            {"revocation_reason": "Court injunction pending review.", "make_private": True},
            format="json",
        )
        self.assertEqual(revoke_response.status_code, 200)

        self.record.refresh_from_db()
        publication = AppointmentPublication.objects.get(appointment=self.record)
        self.assertEqual(publication.status, "revoked")
        self.assertIsNotNone(publication.revoked_at)
        self.assertEqual(publication.revoked_by_id, self.authority_user.id)
        self.assertEqual(publication.revocation_reason, "Court injunction pending review.")
        self.assertFalse(self.record.is_public)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=APPOINTMENT_PUBLICATION_REVOKED_EVENT,
        )
        self.assertGreater(self._notification_count_for_event(event_type="appointment_revoked"), 0)

        self.client.force_authenticate(user=None)
        feed_after = self.client.get("/api/appointments/records/gazette-feed/")
        self.assertEqual(feed_after.status_code, 200)
        after_ids = {str(item["id"]) for item in feed_after.json()}
        self.assertNotIn(str(self.record.id), after_ids)

    def test_revoke_publication_requires_recent_auth_for_authorized_actor(self):
        publish_response = self._publish_record(actor=self.authority_user)
        self.assertEqual(publish_response.status_code, 200)

        self._authenticate_with_recent_auth(self.authority_user, age_seconds=3600)
        denied_stale = self.client.post(
            f"/api/appointments/records/{self.record.id}/revoke-publication/",
            {"revocation_reason": "Stale auth should be rejected.", "make_private": True},
            format="json",
        )
        self.assertEqual(denied_stale.status_code, 403)
        self.assertEqual((denied_stale.json() or {}).get("code"), RECENT_AUTH_REQUIRED_CODE)

        self._authenticate_with_recent_auth(self.authority_user)
        allowed = self.client.post(
            f"/api/appointments/records/{self.record.id}/revoke-publication/",
            {"revocation_reason": "Fresh auth accepted.", "make_private": True},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)

    def test_public_endpoints_exclude_unpublished_records_even_if_marked_public(self):
        nominee = self._build_nominee()
        unpublished = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="Unpublished Public Marker",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )
        self.assertFalse(AppointmentPublication.objects.filter(appointment=unpublished).exists())

        self.client.force_authenticate(user=None)
        gazette_feed = self.client.get("/api/appointments/records/gazette-feed/")
        self.assertEqual(gazette_feed.status_code, 200)
        gazette_ids = {str(item["id"]) for item in gazette_feed.json()}
        self.assertNotIn(str(unpublished.id), gazette_ids)

        open_feed = self.client.get("/api/appointments/records/open/")
        self.assertEqual(open_feed.status_code, 200)
        open_ids = {str(item["id"]) for item in open_feed.json()}
        self.assertNotIn(str(unpublished.id), open_ids)

    def test_publication_detail_endpoint_returns_provenance(self):
        publish_response = self._publish_record()
        self.assertEqual(publish_response.status_code, 200)

        self.client.force_authenticate(self.admin_user)
        detail_response = self.client.get(f"/api/appointments/records/{self.record.id}/publication/")
        self.assertEqual(detail_response.status_code, 200)
        payload = detail_response.json()
        self.assertEqual(payload["status"], "published")
        self.assertEqual(payload["appointment"], str(self.record.id))
        self.assertIn("published_at", payload)
        self.assertIn("publication_reference", payload)

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.get(f"/api/appointments/records/{self.record.id}/publication/")
        self.assertEqual(denied.status_code, 403)

    def test_public_gazette_feed_redacts_internal_fields(self):
        publish_response = self._publish_record(actor=self.admin_user)
        self.assertEqual(publish_response.status_code, 200)

        self.client.force_authenticate(user=None)
        response = self.client.get("/api/appointments/records/gazette-feed/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)
        item = next((row for row in payload if str(row["id"]) == str(self.record.id)), None)
        self.assertIsNotNone(item)
        self.assertNotIn("vetting_case", item)
        self.assertNotIn("committee_recommendation", item)
        self.assertNotIn("stage_actions", item)
        self.assertNotIn("publication_notes", item)
        self.assertIn("position_title", item)
        self.assertIn("publication_status", item)
        self.assertIn("publication_reference", item)

    def test_legacy_public_endpoints_include_deprecation_headers(self):
        self._authenticate_with_recent_auth(self.authority_user)
        publish_response = self.client.post(
            f"/api/appointments/records/{self.record.id}/publish/",
            {
                "publication_reference": "GOV-GAZ-LEGACY-HDR",
                "publication_document_hash": "b" * 64,
                "gazette_number": "GN-LEGACY-1",
                "gazette_date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(publish_response.status_code, 200)

        self.client.force_authenticate(user=None)

        legacy_gazette = self.client.get("/api/appointments/records/gazette-feed/")
        self.assertEqual(legacy_gazette.status_code, 200)
        self.assertEqual(legacy_gazette["Deprecation"], "true")
        self.assertEqual(legacy_gazette["X-Deprecated-Endpoint"], "true")
        self.assertEqual(legacy_gazette["Sunset"], "Thu, 31 Dec 2026 23:59:59 GMT")
        self.assertIn(
            "</api/public/transparency/appointments/gazette-feed/>; rel=\"successor-version\"",
            legacy_gazette["Link"],
        )

        legacy_open = self.client.get("/api/appointments/records/open/")
        self.assertEqual(legacy_open.status_code, 200)
        self.assertEqual(legacy_open["Deprecation"], "true")
        self.assertEqual(legacy_open["X-Deprecated-Endpoint"], "true")
        self.assertIn(
            "</api/public/transparency/appointments/open/>; rel=\"successor-version\"",
            legacy_open["Link"],
        )

    def test_legacy_gazette_feed_matches_transparency_gazette_feed(self):
        self._authenticate_with_recent_auth(self.authority_user)
        publish_response = self.client.post(
            f"/api/appointments/records/{self.record.id}/publish/",
            {
                "publication_reference": "GOV-GAZ-PARITY-HDR",
                "publication_document_hash": "c" * 64,
                "gazette_number": "GN-PARITY-1",
                "gazette_date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(publish_response.status_code, 200)

        self.client.force_authenticate(user=None)
        legacy_feed = self.client.get("/api/appointments/records/gazette-feed/")
        modern_feed = self.client.get("/api/public/transparency/appointments/gazette-feed/")
        self.assertEqual(legacy_feed.status_code, 200)
        self.assertEqual(modern_feed.status_code, 200)

        legacy_ids = {str(item["id"]) for item in legacy_feed.json()}
        modern_ids = {str(item["id"]) for item in modern_feed.json()}
        self.assertSetEqual(legacy_ids, modern_ids)

    def test_public_transparency_appointments_list_and_detail_require_published_state(self):
        publish_response = self._publish_record(actor=self.admin_user)
        self.assertEqual(publish_response.status_code, 200)

        unpublished_nominee = self._build_nominee()
        unpublished = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=unpublished_nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="Unpublished Transparency Marker",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )

        self.client.force_authenticate(user=None)
        list_response = self.client.get("/api/public/transparency/appointments/")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertIsInstance(payload, list)
        ids = {str(item["id"]) for item in payload}
        self.assertIn(str(self.record.id), ids)
        self.assertNotIn(str(unpublished.id), ids)

        item = next((row for row in payload if str(row["id"]) == str(self.record.id)), None)
        self.assertIsNotNone(item)
        self.assertNotIn("committee_recommendation", item)
        self.assertNotIn("publication_notes", item)
        self.assertNotIn("publication_document_hash", item)
        self.assertNotIn("vetting_case", item)

        detail_response = self.client.get(f"/api/public/transparency/appointments/{self.record.id}/")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(str(detail_payload["id"]), str(self.record.id))
        self.assertEqual(detail_payload.get("publication_status"), "published")

        detail_unpublished = self.client.get(f"/api/public/transparency/appointments/{unpublished.id}/")
        self.assertEqual(detail_unpublished.status_code, 404)

    def test_public_transparency_revoked_records_disappear_from_list_and_detail(self):
        publish_response = self._publish_record(actor=self.authority_user)
        self.assertEqual(publish_response.status_code, 200)

        self._authenticate_with_recent_auth(self.authority_user)
        revoke_response = self.client.post(
            f"/api/appointments/records/{self.record.id}/revoke-publication/",
            {"revocation_reason": "Public correction", "make_private": True},
            format="json",
        )
        self.assertEqual(revoke_response.status_code, 200)

        self.client.force_authenticate(user=None)
        list_response = self.client.get("/api/public/transparency/appointments/")
        self.assertEqual(list_response.status_code, 200)
        ids = {str(item["id"]) for item in list_response.json()}
        self.assertNotIn(str(self.record.id), ids)

        detail_response = self.client.get(f"/api/public/transparency/appointments/{self.record.id}/")
        self.assertEqual(detail_response.status_code, 404)

    def test_public_transparency_summary_positions_and_officeholders(self):
        publish_response = self._publish_record(actor=self.admin_user)
        self.assertEqual(publish_response.status_code, 200)

        officeholder = PersonnelRecord.objects.create(
            full_name="Public Officeholder",
            gender="female",
            bio_summary="Public service profile.",
            academic_qualifications=["LLB"],
            is_active_officeholder=True,
            is_public=True,
        )

        self.client.force_authenticate(user=None)
        summary_response = self.client.get("/api/public/transparency/summary/")
        self.assertEqual(summary_response.status_code, 200)
        summary_payload = summary_response.json()
        self.assertGreaterEqual(summary_payload.get("published_appointments", 0), 1)
        self.assertGreaterEqual(summary_payload.get("public_positions", 0), 1)
        self.assertGreaterEqual(summary_payload.get("active_public_officeholders", 0), 1)

        positions_response = self.client.get("/api/public/transparency/positions/")
        self.assertEqual(positions_response.status_code, 200)
        positions_payload = positions_response.json()
        self.assertTrue(any(str(item["id"]) == str(self.record.position_id) for item in positions_payload))
        first_position = positions_payload[0]
        self.assertNotIn("required_qualifications", first_position)
        self.assertNotIn("rubric", first_position)

        officeholders_response = self.client.get("/api/public/transparency/officeholders/")
        self.assertEqual(officeholders_response.status_code, 200)
        officeholders_payload = officeholders_response.json()
        self.assertTrue(any(str(item["id"]) == str(officeholder.id) for item in officeholders_payload))
        first_officeholder = officeholders_payload[0]
        self.assertNotIn("contact_email", first_officeholder)
        self.assertNotIn("national_id_hash", first_officeholder)


class AppointmentCommitteeBindingApiTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="appt-committee-org-a", name="Appointments Committee Org A")
        self.org_b = Organization.objects.create(code="appt-committee-org-b", name="Appointments Committee Org B")

        self.admin_user = User.objects.create_user(
            email="appt_committee_admin@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.member_user = User.objects.create_user(
            email="appt_committee_member@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Member",
            user_type="hr_manager",
        )
        self.chair_user = User.objects.create_user(
            email="appt_committee_chair@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Chair",
            user_type="hr_manager",
        )
        self.secretary_user = User.objects.create_user(
            email="appt_committee_secretary@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Secretary",
            user_type="hr_manager",
        )
        self.observer_user = User.objects.create_user(
            email="appt_committee_observer@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="Observer",
            user_type="hr_manager",
        )
        self.non_member_group_user = User.objects.create_user(
            email="appt_committee_group_only@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="GroupOnly",
            user_type="hr_manager",
        )
        self.cross_org_member_user = User.objects.create_user(
            email="appt_committee_cross_org@example.com",
            password="Pass1234!",
            first_name="Committee",
            last_name="CrossOrg",
            user_type="hr_manager",
        )

        self.committee_group, _ = Group.objects.get_or_create(name="committee_member")
        self.committee_chair_group, _ = Group.objects.get_or_create(name="committee_chair")
        self.non_member_group_user.groups.add(self.committee_group)
        self.cross_org_member_user.groups.add(self.committee_group)
        self.chair_user.groups.add(self.committee_chair_group)

        self.org_membership_member = OrganizationMembership.objects.create(
            user=self.member_user,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.org_membership_chair = OrganizationMembership.objects.create(
            user=self.chair_user,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.org_membership_secretary = OrganizationMembership.objects.create(
            user=self.secretary_user,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.org_membership_observer = OrganizationMembership.objects.create(
            user=self.observer_user,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.org_membership_non_member_group = OrganizationMembership.objects.create(
            user=self.non_member_group_user,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.org_membership_cross = OrganizationMembership.objects.create(
            user=self.cross_org_member_user,
            organization=self.org_b,
            is_active=True,
            is_default=True,
        )

        self.committee_a = Committee.objects.create(
            organization=self.org_a,
            code="committee-a-main",
            name="Committee A Main",
            committee_type="approval",
            is_active=True,
        )
        self.committee_b = Committee.objects.create(
            organization=self.org_b,
            code="committee-b-main",
            name="Committee B Main",
            committee_type="approval",
            is_active=True,
        )

        CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=self.member_user,
            organization_membership=self.org_membership_member,
            committee_role="member",
            can_vote=True,
            is_active=True,
        )
        CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=self.chair_user,
            organization_membership=self.org_membership_chair,
            committee_role="chair",
            can_vote=True,
            is_active=True,
        )
        CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=self.secretary_user,
            organization_membership=self.org_membership_secretary,
            committee_role="secretary",
            can_vote=True,
            is_active=True,
        )
        CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=self.observer_user,
            organization_membership=self.org_membership_observer,
            committee_role="observer",
            can_vote=False,
            is_active=True,
        )
        CommitteeMembership.objects.create(
            committee=self.committee_b,
            user=self.cross_org_member_user,
            organization_membership=self.org_membership_cross,
            committee_role="member",
            can_vote=True,
            is_active=True,
        )

        self.position = GovernmentPosition.objects.create(
            organization=self.org_a,
            title="Committee Binding Position",
            branch="executive",
            institution="Committee Secretariat",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        self.nominee = PersonnelRecord.objects.create(
            organization=self.org_a,
            full_name="Committee Binding Nominee",
            is_public=True,
        )

        self.template = ApprovalStageTemplate.objects.create(
            organization=self.org_a,
            name="Committee Binding Template",
            exercise_type="ministerial",
            created_by=self.admin_user,
        )
        self.stage_member = ApprovalStage.objects.create(
            template=self.template,
            order=1,
            name="Committee Review Stage",
            required_role="committee_member",
            is_required=True,
            maps_to_status="committee_review",
            committee=self.committee_a,
        )
        self.stage_chair = ApprovalStage.objects.create(
            template=self.template,
            order=2,
            name="Committee Chair Confirmation",
            required_role="committee_chair",
            is_required=False,
            maps_to_status="confirmation_pending",
            committee=self.committee_a,
        )
        self.stage_legacy = ApprovalStage.objects.create(
            template=self.template,
            order=3,
            name="Legacy Committee Fallback",
            required_role="committee_member",
            is_required=False,
            maps_to_status="committee_review",
            committee=None,
        )

        self.campaign = VettingCampaign.objects.create(
            organization=self.org_a,
            name="Committee Binding Campaign",
            initiated_by=self.admin_user,
            status="active",
            approval_template=self.template,
        )
        self.appointment = AppointmentRecord.objects.create(
            organization=self.org_a,
            committee=self.committee_a,
            position=self.position,
            nominee=self.nominee,
            appointment_exercise=self.campaign,
            nominated_by_user=self.admin_user,
            nominated_by_display="Authority",
            nomination_date=date.today(),
            status="under_vetting",
            is_public=False,
        )
        self.legacy_appointment = AppointmentRecord.objects.create(
            organization=self.org_a,
            committee=None,
            position=GovernmentPosition.objects.create(
                organization=self.org_a,
                title="Legacy Committee Position",
                branch="executive",
                institution="Legacy Secretariat",
                appointment_authority="President",
                is_vacant=True,
                is_public=True,
            ),
            nominee=PersonnelRecord.objects.create(
                organization=self.org_a,
                full_name="Legacy Committee Nominee",
                is_public=True,
            ),
            appointment_exercise=self.campaign,
            nominated_by_user=self.admin_user,
            nominated_by_display="Authority",
            nomination_date=date.today(),
            status="under_vetting",
            is_public=False,
        )

    def test_committee_member_allowed_for_bound_committee_stage(self):
        self.client.force_authenticate(self.member_user)
        response = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_non_member_denied_even_with_legacy_group(self):
        self.client.force_authenticate(self.non_member_group_user)
        response = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get("code"), "insufficient_role")

    def test_cross_org_committee_member_denied(self):
        self.client.force_authenticate(self.cross_org_member_user)
        response = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertIn(response.status_code, {403, 404})

    def test_chair_specific_stage_requires_chair_membership(self):
        self.appointment.status = "committee_review"
        self.appointment.save(update_fields=["status", "updated_at"])

        self.client.force_authenticate(self.member_user)
        denied = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "confirmation_pending", "stage_id": str(self.stage_chair.id)},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json().get("code"), "insufficient_role")

        self.client.force_authenticate(self.chair_user)
        allowed = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "confirmation_pending", "stage_id": str(self.stage_chair.id)},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)

    def test_observer_membership_cannot_take_committee_stage_action(self):
        self.client.force_authenticate(self.observer_user)
        response = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_legacy_stage_without_committee_keeps_group_based_fallback(self):
        legacy_template = ApprovalStageTemplate.objects.create(
            organization=self.org_a,
            name="Legacy Committee Fallback Template",
            exercise_type="ministerial",
            created_by=self.admin_user,
        )
        legacy_stage = ApprovalStage.objects.create(
            template=legacy_template,
            order=1,
            name="Legacy Committee Stage",
            required_role="committee_member",
            is_required=True,
            maps_to_status="committee_review",
            committee=None,
        )
        legacy_campaign = VettingCampaign.objects.create(
            organization=self.org_a,
            name="Legacy Committee Campaign",
            initiated_by=self.admin_user,
            status="active",
            approval_template=legacy_template,
        )
        legacy_appointment = AppointmentRecord.objects.create(
            organization=self.org_a,
            committee=None,
            position=GovernmentPosition.objects.create(
                organization=self.org_a,
                title="Legacy Committee Position Two",
                branch="executive",
                institution="Legacy Secretariat",
                appointment_authority="President",
                is_vacant=True,
                is_public=True,
            ),
            nominee=PersonnelRecord.objects.create(
                organization=self.org_a,
                full_name="Legacy Committee Nominee Two",
                is_public=True,
            ),
            appointment_exercise=legacy_campaign,
            nominated_by_user=self.admin_user,
            nominated_by_display="Authority",
            nomination_date=date.today(),
            status="under_vetting",
            is_public=False,
        )

        self.client.force_authenticate(self.non_member_group_user)
        response = self.client.post(
            f"/api/appointments/records/{legacy_appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(legacy_stage.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_committee_stage_transition_audit_includes_org_and_committee_context(self):
        if "apps.audit" not in settings.INSTALLED_APPS:
            self.skipTest("Audit app not enabled")
        from apps.audit.models import AuditLog

        self.client.force_authenticate(self.member_user)
        response = self.client.post(
            f"/api/appointments/records/{self.appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        transition_event = (
            AuditLog.objects.filter(
                entity_type="AppointmentRecord",
                entity_id=str(self.appointment.id),
                changes__event=APPOINTMENT_STAGE_TRANSITION_EVENT,
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(transition_event)
        payload = transition_event.changes or {}
        self.assertEqual(payload.get("organization_id"), str(self.org_a.id))
        self.assertEqual(payload.get("committee_id"), str(self.committee_a.id))

    def test_stage_actions_history_denies_non_member_when_record_has_no_bound_committee(self):
        appointment = AppointmentRecord.objects.create(
            organization=self.org_a,
            committee=None,
            position=GovernmentPosition.objects.create(
                organization=self.org_a,
                title="Legacy History Position",
                branch="executive",
                institution="Legacy Secretariat",
                appointment_authority="President",
                is_vacant=True,
                is_public=True,
            ),
            nominee=PersonnelRecord.objects.create(
                organization=self.org_a,
                full_name="Legacy History Nominee",
                is_public=True,
            ),
            appointment_exercise=self.campaign,
            nominated_by_user=self.admin_user,
            nominated_by_display="Legacy Committee Context",
            nominated_by_org="Org A",
            nomination_date=date.today(),
            status="under_vetting",
            is_public=False,
        )

        self.client.force_authenticate(self.member_user)
        transition = self.client.post(
            f"/api/appointments/records/{appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertEqual(transition.status_code, 200)

        self.client.force_authenticate(self.non_member_group_user)
        denied = self.client.get(f"/api/appointments/records/{appointment.id}/stage-actions/")
        self.assertEqual(denied.status_code, 403)

    def test_stage_actions_history_allows_member_when_record_has_no_bound_committee(self):
        appointment = AppointmentRecord.objects.create(
            organization=self.org_a,
            committee=None,
            position=GovernmentPosition.objects.create(
                organization=self.org_a,
                title="Legacy History Position Allowed",
                branch="executive",
                institution="Legacy Secretariat",
                appointment_authority="President",
                is_vacant=True,
                is_public=True,
            ),
            nominee=PersonnelRecord.objects.create(
                organization=self.org_a,
                full_name="Legacy History Nominee Allowed",
                is_public=True,
            ),
            appointment_exercise=self.campaign,
            nominated_by_user=self.admin_user,
            nominated_by_display="Legacy Committee Context",
            nominated_by_org="Org A",
            nomination_date=date.today(),
            status="under_vetting",
            is_public=False,
        )

        self.client.force_authenticate(self.member_user)
        transition = self.client.post(
            f"/api/appointments/records/{appointment.id}/advance-stage/",
            {"status": "committee_review", "stage_id": str(self.stage_member.id)},
            format="json",
        )
        self.assertEqual(transition.status_code, 200)

        allowed = self.client.get(f"/api/appointments/records/{appointment.id}/stage-actions/")
        self.assertEqual(allowed.status_code, 200)
        payload = allowed.json()
        self.assertIsInstance(payload, list)
        self.assertGreaterEqual(len(payload), 1)

class AppointmentOrganizationScopeTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="appt-org-a", name="Appointments Org A")
        self.org_b = Organization.objects.create(code="appt-org-b", name="Appointments Org B")

        self.hr_a = User.objects.create_user(
            email="appointments_scope_a@example.com",
            password="Pass1234!",
            first_name="Appointments",
            last_name="ScopeA",
            user_type="hr_manager",
        )
        self.admin_user = User.objects.create_user(
            email="appointments_scope_admin@example.com",
            password="Pass1234!",
            first_name="Appointments",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr_a,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )

        self.nominee_a = PersonnelRecord.objects.create(
            organization=self.org_a,
            full_name="Scope Nominee A",
        )
        self.nominee_b = PersonnelRecord.objects.create(
            organization=self.org_b,
            full_name="Scope Nominee B",
        )
        self.position_a = GovernmentPosition.objects.create(
            organization=self.org_a,
            title="Scoped Appointment Position A",
            branch="executive",
            institution="Appointments Org A Office",
            appointment_authority="President",
            is_vacant=True,
        )
        self.position_b = GovernmentPosition.objects.create(
            organization=self.org_b,
            title="Scoped Appointment Position B",
            branch="executive",
            institution="Appointments Org B Office",
            appointment_authority="President",
            is_vacant=True,
        )
        self.position_legacy = GovernmentPosition.objects.create(
            title="Legacy Appointment Position",
            branch="executive",
            institution="Legacy Office",
            appointment_authority="President",
            is_vacant=True,
        )
        self.campaign_a = VettingCampaign.objects.create(
            name="Scoped Appointments Campaign A",
            organization=self.org_a,
            initiated_by=self.admin_user,
            status="active",
        )
        self.campaign_b = VettingCampaign.objects.create(
            name="Scoped Appointments Campaign B",
            organization=self.org_b,
            initiated_by=self.admin_user,
            status="active",
        )
        self.appointment_org_a = AppointmentRecord.objects.create(
            organization=self.org_a,
            position=self.position_a,
            nominee=self.nominee_a,
            appointment_exercise=self.campaign_a,
            nominated_by_user=self.admin_user,
            nominated_by_display="Authority A",
            nomination_date=date.today(),
            status="nominated",
        )
        self.appointment_org_b = AppointmentRecord.objects.create(
            organization=self.org_b,
            position=self.position_b,
            nominee=self.nominee_b,
            appointment_exercise=self.campaign_b,
            nominated_by_user=self.admin_user,
            nominated_by_display="Authority B",
            nomination_date=date.today(),
            status="nominated",
        )
        self.appointment_legacy = AppointmentRecord.objects.create(
            position=self.position_legacy,
            nominee=PersonnelRecord.objects.create(full_name="Legacy Scope Nominee"),
            appointment_exercise=self.campaign_a,
            nominated_by_user=self.admin_user,
            nominated_by_display="Legacy Authority",
            nomination_date=date.today(),
            status="nominated",
        )

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def test_list_is_scoped_to_org_and_excludes_legacy_null_scope(self):
        self.client.force_authenticate(self.hr_a)
        response = self.client.get("/api/appointments/records/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._extract_results(response)}
        self.assertIn(str(self.appointment_org_a.id), ids)
        self.assertNotIn(str(self.appointment_legacy.id), ids)
        self.assertNotIn(str(self.appointment_org_b.id), ids)

    def test_update_outside_org_is_denied_for_hr_but_allowed_for_admin(self):
        self.client.force_authenticate(self.hr_a)
        denied = self.client.patch(
            f"/api/appointments/records/{self.appointment_org_b.id}/",
            {"nominated_by_display": "Blocked Cross Org Edit"},
            format="json",
        )
        self.assertIn(denied.status_code, {403, 404})

        self.client.force_authenticate(self.admin_user)
        allowed = self.client.patch(
            f"/api/appointments/records/{self.appointment_org_b.id}/",
            {"nominated_by_display": "Admin Cross Org Edit"},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)
