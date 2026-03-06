from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.applications.models import VettingCase
from apps.invitations.models import Invitation
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition

from .models import AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from .services import InvalidTransitionError, StageAuthorizationError, advance_stage, ensure_vetting_linkage_for_appointment


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
        self.vetting_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.committee_group, _ = Group.objects.get_or_create(name="committee_member")
        self.authority_group, _ = Group.objects.get_or_create(name="appointing_authority")
        self.vetting_user.groups.add(self.vetting_group)
        self.committee_user.groups.add(self.committee_group)
        self.authority_user.groups.add(self.authority_group)

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
