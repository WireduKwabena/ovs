from datetime import date

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.audit.contracts import (
    APPOINTMENT_RECORD_CREATED_EVENT,
    APPOINTMENT_RECORD_DELETED_EVENT,
    APPOINTMENT_RECORD_UPDATED_EVENT,
    APPOINTMENT_STAGE_TRANSITION_EVENT,
    APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
)
from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.applications.models import VettingCase
from apps.invitations.models import Invitation
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition

from .models import AppointmentRecord, ApprovalStage, ApprovalStageTemplate
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
        self.authority_user = User.objects.create_user(
            email="authority.user@example.com",
            password="Pass1234!",
            first_name="Authority",
            last_name="User",
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
        self.authority_group, _ = Group.objects.get_or_create(name="appointing_authority")
        self.vetting_user.groups.add(self.vetting_group)
        self.committee_user.groups.add(self.committee_group)
        self.authority_user.groups.add(self.authority_group)

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def _assert_audit_row_exists(self, *, action: str, entity_id: str, expected_event: str | None = None):
        if "apps.audit" not in settings.INSTALLED_APPS:
            return
        from apps.audit.models import AuditLog

        row = (
            AuditLog.objects.filter(
                action=action,
                entity_type="AppointmentRecord",
                entity_id=str(entity_id),
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(row)
        if expected_event:
            self.assertEqual((row.changes or {}).get("event"), expected_event)

    def test_create_record_auto_links_vetting_case(self):
        response = self.client.post(
            "/api/appointments/records/",
            {
                "position": str(self.record.position_id),
                "nominee": str(self.record.nominee_id),
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
        payload = {
            "position": str(self.record.position_id),
            "nominee": str(self.record.nominee_id),
            "nominated_by_display": "H.E. President",
            "nominated_by_org": "Office of the President",
            "nomination_date": str(date.today()),
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
        admin_allowed = self.client.post("/api/appointments/records/", payload, format="json")
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
        blocked_record = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=self.record.nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="Blocked Delete",
            nomination_date=date.today(),
            status="nominated",
            is_public=False,
        )
        hr_record = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=self.record.nominee,
            appointment_exercise=self.record.appointment_exercise,
            nominated_by_user=self.admin_user,
            nominated_by_display="HR Delete",
            nomination_date=date.today(),
            status="nominated",
            is_public=False,
        )
        admin_record = AppointmentRecord.objects.create(
            position=self.record.position,
            nominee=self.record.nominee,
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

        self.client.force_authenticate(self.authority_user)
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

        self.client.force_authenticate(self.authority_user)
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

    def test_public_gazette_feed_redacts_internal_fields(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/appointments/records/gazette-feed/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)
        if payload:
            item = payload[0]
            self.assertNotIn("vetting_case", item)
            self.assertNotIn("committee_recommendation", item)
            self.assertIn("position_title", item)
