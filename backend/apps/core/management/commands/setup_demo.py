from __future__ import annotations

from datetime import date

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import AppointmentPublication, AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.governance.models import Committee, CommitteeMembership, Organization, OrganizationMembership
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition


APPOINTMENT_ROLE_GROUPS = (
    "vetting_officer",
    "committee_member",
    "committee_chair",
    "appointing_authority",
    "registry_admin",
    "publication_officer",
    "auditor",
)
ACTIVE_APPOINTMENT_STATUSES = {
    "nominated",
    "under_vetting",
    "committee_review",
    "confirmation_pending",
    "appointed",
    "serving",
}


class Command(BaseCommand):
    help = "Bootstrap a safe, idempotent GAMS demo workspace (users, roles, and sample government workflow records)."

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", default="gams.admin@demo.local")
        parser.add_argument("--admin-password", default="DemoAdmin123!")

        parser.add_argument("--vetting-email", default="gams.vetting@demo.local")
        parser.add_argument("--vetting-password", default="DemoVetting123!")

        parser.add_argument("--committee-email", default="gams.committee@demo.local")
        parser.add_argument("--committee-password", default="DemoCommittee123!")

        parser.add_argument("--authority-email", default="gams.authority@demo.local")
        parser.add_argument("--authority-password", default="DemoAuthority123!")

        parser.add_argument("--registry-email", default="gams.registry@demo.local")
        parser.add_argument("--registry-password", default="DemoRegistry123!")

        parser.add_argument("--publication-email", default="gams.publication@demo.local")
        parser.add_argument("--publication-password", default="DemoPublication123!")

        parser.add_argument("--auditor-email", default="gams.auditor@demo.local")
        parser.add_argument("--auditor-password", default="DemoAuditor123!")

        parser.add_argument(
            "--skip-sample-data",
            action="store_true",
            help="Create role accounts/groups only; skip campaign/position/personnel/appointment demo records.",
        )

    def handle(self, *args, **options):
        self._ensure_governance_schema_ready()
        if not options["skip_sample_data"]:
            self._ensure_sample_data_schema_ready()

        with transaction.atomic():
            groups = self._ensure_groups()
            users = self._ensure_users(options=options, groups=groups)
            organizations = self._ensure_governance_foundation(users=users)

            if not options["skip_sample_data"]:
                self._ensure_sample_data(users=users, organizations=organizations)

        self.stdout.write(self.style.SUCCESS("GAMS demo setup completed."))
        self.stdout.write("Demo sign-in accounts:")
        self.stdout.write(f"  Admin:     {options['admin_email']} / {options['admin_password']}")
        self.stdout.write(f"  Vetting:   {options['vetting_email']} / {options['vetting_password']}")
        self.stdout.write(f"  Committee: {options['committee_email']} / {options['committee_password']}")
        self.stdout.write(f"  Authority: {options['authority_email']} / {options['authority_password']}")
        self.stdout.write(f"  Registry:  {options['registry_email']} / {options['registry_password']}")
        self.stdout.write(f"  Publication: {options['publication_email']} / {options['publication_password']}")
        self.stdout.write(f"  Auditor:  {options['auditor_email']} / {options['auditor_password']}")

    def _ensure_sample_data_schema_ready(self) -> None:
        required_tables = {
            ApprovalStageTemplate._meta.db_table,
            ApprovalStage._meta.db_table,
            AppointmentRecord._meta.db_table,
            AppointmentPublication._meta.db_table,
            VettingCampaign._meta.db_table,
            GovernmentPosition._meta.db_table,
            PersonnelRecord._meta.db_table,
        }
        existing_tables = set(connection.introspection.table_names())
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            raise CommandError(
                "Cannot seed demo sample records because required tables are missing: "
                f"{', '.join(missing_tables)}. Run `python manage.py migrate` and retry."
            )

    def _ensure_governance_schema_ready(self) -> None:
        required_tables = {
            Organization._meta.db_table,
            OrganizationMembership._meta.db_table,
            Committee._meta.db_table,
            CommitteeMembership._meta.db_table,
        }
        existing_tables = set(connection.introspection.table_names())
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            raise CommandError(
                "Cannot seed governance demo records because required tables are missing: "
                f"{', '.join(missing_tables)}. Run `python manage.py migrate` and retry."
            )

    def _ensure_groups(self) -> dict[str, Group]:
        groups: dict[str, Group] = {}
        for name in APPOINTMENT_ROLE_GROUPS:
            group, _ = Group.objects.get_or_create(name=name)
            groups[name] = group
        return groups

    def _ensure_users(self, *, options, groups: dict[str, Group]) -> dict[str, User]:
        admin_user = self._upsert_user(
            email=options["admin_email"],
            password=options["admin_password"],
            first_name="GAMS",
            last_name="Administrator",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
            organization="Public Service Commission",
            department="Appointments Secretariat",
        )
        admin_user.groups.add(*groups.values())

        vetting_user = self._upsert_user(
            email=options["vetting_email"],
            password=options["vetting_password"],
            first_name="Vetting",
            last_name="Officer",
            user_type="hr_manager",
            is_staff=False,
            is_superuser=False,
            organization="Appointments Secretariat",
            department="Vetting",
        )
        vetting_user.groups.add(groups["vetting_officer"])

        committee_user = self._upsert_user(
            email=options["committee_email"],
            password=options["committee_password"],
            first_name="Committee",
            last_name="Member",
            user_type="hr_manager",
            is_staff=False,
            is_superuser=False,
            organization="Parliamentary Appointments Committee",
            department="Review",
        )
        committee_user.groups.add(groups["committee_member"])

        authority_user = self._upsert_user(
            email=options["authority_email"],
            password=options["authority_password"],
            first_name="Appointing",
            last_name="Authority",
            user_type="hr_manager",
            is_staff=False,
            is_superuser=False,
            organization="Office of the President",
            department="Executive",
        )
        authority_user.groups.add(groups["appointing_authority"])

        registry_user = self._upsert_user(
            email=options["registry_email"],
            password=options["registry_password"],
            first_name="Registry",
            last_name="Officer",
            user_type="hr_manager",
            is_staff=False,
            is_superuser=False,
            organization="Gazette and Records Office",
            department="Records",
        )
        registry_user.groups.add(groups["registry_admin"])

        publication_user = self._upsert_user(
            email=options["publication_email"],
            password=options["publication_password"],
            first_name="Publication",
            last_name="Officer",
            user_type="hr_manager",
            is_staff=False,
            is_superuser=False,
            organization="Gazette and Records Office",
            department="Publication",
        )
        publication_user.groups.add(groups["publication_officer"])

        auditor_user = self._upsert_user(
            email=options["auditor_email"],
            password=options["auditor_password"],
            first_name="Government",
            last_name="Auditor",
            user_type="hr_manager",
            is_staff=False,
            is_superuser=False,
            organization="Audit Service",
            department="Compliance",
        )
        auditor_user.groups.add(groups["auditor"])

        return {
            "admin": admin_user,
            "vetting": vetting_user,
            "committee": committee_user,
            "authority": authority_user,
            "registry": registry_user,
            "publication": publication_user,
            "auditor": auditor_user,
        }

    def _ensure_governance_foundation(self, *, users: dict[str, User]) -> dict[str, Organization]:
        organization_specs = {
            "admin": {
                "name": "Public Service Commission",
                "code": "public-service-commission",
                "organization_type": "agency",
            },
            "vetting": {
                "name": "Appointments Secretariat",
                "code": "appointments-secretariat",
                "organization_type": "agency",
            },
            "committee": {
                "name": "Parliamentary Appointments Committee",
                "code": "parliamentary-appointments-committee",
                "organization_type": "committee_secretariat",
            },
            "authority": {
                "name": "Office of the President",
                "code": "office-of-the-president",
                "organization_type": "executive_office",
            },
            "registry": {
                "name": "Gazette and Records Office",
                "code": "gazette-and-records-office",
                "organization_type": "agency",
            },
            "publication": {
                "name": "Gazette and Records Office",
                "code": "gazette-and-records-office",
                "organization_type": "agency",
            },
            "auditor": {
                "name": "Audit Service",
                "code": "audit-service",
                "organization_type": "audit",
            },
        }

        organizations: dict[str, Organization] = {}
        for key, spec in organization_specs.items():
            organization = self._upsert_organization(
                code=spec["code"],
                name=spec["name"],
                organization_type=spec["organization_type"],
            )
            organizations[key] = organization

        memberships: dict[str, OrganizationMembership] = {}
        memberships["admin"] = self._upsert_org_membership(
            user=users["admin"],
            organization=organizations["admin"],
            membership_role="system_admin",
            is_default=True,
        )
        memberships["vetting"] = self._upsert_org_membership(
            user=users["vetting"],
            organization=organizations["vetting"],
            membership_role="vetting_officer",
            is_default=True,
        )
        memberships["committee"] = self._upsert_org_membership(
            user=users["committee"],
            organization=organizations["committee"],
            membership_role="committee_member",
            is_default=True,
        )
        memberships["authority"] = self._upsert_org_membership(
            user=users["authority"],
            organization=organizations["authority"],
            membership_role="appointing_authority",
            is_default=True,
        )
        memberships["registry"] = self._upsert_org_membership(
            user=users["registry"],
            organization=organizations["registry"],
            membership_role="registry_admin",
            is_default=True,
        )
        memberships["publication"] = self._upsert_org_membership(
            user=users["publication"],
            organization=organizations["publication"],
            membership_role="publication_officer",
            is_default=True,
        )
        memberships["auditor"] = self._upsert_org_membership(
            user=users["auditor"],
            organization=organizations["auditor"],
            membership_role="auditor",
            is_default=True,
        )

        committee = self._upsert_committee(
            organization=organizations["committee"],
            code="parliamentary-appointments-main",
            name="Parliamentary Appointments Main Committee",
            committee_type="approval",
            created_by=users["admin"],
            description="Primary committee for the demo approval-chain walkthrough.",
        )

        self._upsert_committee_membership(
            committee=committee,
            user=users["committee"],
            organization_membership=memberships["committee"],
            committee_role="member",
            can_vote=True,
        )

        return organizations

    def _upsert_organization(
        self,
        *,
        code: str,
        name: str,
        organization_type: str,
    ) -> Organization:
        organization, _created = Organization.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "organization_type": organization_type,
                "is_active": True,
            },
        )
        updated_fields: list[str] = []
        for field, value in {
            "name": name,
            "organization_type": organization_type,
            "is_active": True,
        }.items():
            if getattr(organization, field) != value:
                setattr(organization, field, value)
                updated_fields.append(field)
        if updated_fields:
            organization.save(update_fields=updated_fields + ["updated_at"])
        return organization

    def _upsert_org_membership(
        self,
        *,
        user: User,
        organization: Organization,
        membership_role: str,
        is_default: bool,
    ) -> OrganizationMembership:
        membership, _created = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=organization,
            defaults={
                "membership_role": membership_role,
                "is_active": True,
                "is_default": is_default,
                "joined_at": timezone.now(),
            },
        )

        if is_default:
            OrganizationMembership.objects.filter(user=user, is_default=True).exclude(pk=membership.pk).update(is_default=False)

        updated_fields: list[str] = []
        for field, value in {
            "membership_role": membership_role,
            "is_active": True,
            "is_default": is_default,
            "left_at": None,
        }.items():
            if getattr(membership, field) != value:
                setattr(membership, field, value)
                updated_fields.append(field)

        if membership.joined_at is None:
            membership.joined_at = timezone.now()
            updated_fields.append("joined_at")

        if updated_fields:
            membership.save(update_fields=updated_fields + ["updated_at"])
        return membership

    def _upsert_committee(
        self,
        *,
        organization: Organization,
        code: str,
        name: str,
        committee_type: str,
        created_by: User,
        description: str,
    ) -> Committee:
        committee, _created = Committee.objects.get_or_create(
            organization=organization,
            code=code,
            defaults={
                "name": name,
                "committee_type": committee_type,
                "description": description,
                "is_active": True,
                "created_by": created_by,
            },
        )
        updated_fields: list[str] = []
        for field, value in {
            "name": name,
            "committee_type": committee_type,
            "description": description,
            "is_active": True,
            "created_by": created_by,
        }.items():
            if getattr(committee, field) != value:
                setattr(committee, field, value)
                updated_fields.append(field)
        if updated_fields:
            committee.save(update_fields=updated_fields + ["updated_at"])
        return committee

    def _upsert_committee_membership(
        self,
        *,
        committee: Committee,
        user: User,
        organization_membership: OrganizationMembership,
        committee_role: str,
        can_vote: bool,
    ) -> CommitteeMembership:
        if committee_role == "observer":
            can_vote = False

        membership, _created = CommitteeMembership.objects.get_or_create(
            committee=committee,
            user=user,
            defaults={
                "organization_membership": organization_membership,
                "committee_role": committee_role,
                "can_vote": can_vote,
                "is_active": True,
                "joined_at": timezone.now(),
            },
        )

        updated_fields: list[str] = []
        for field, value in {
            "organization_membership": organization_membership,
            "committee_role": committee_role,
            "can_vote": can_vote,
            "is_active": True,
            "left_at": None,
        }.items():
            if getattr(membership, field) != value:
                setattr(membership, field, value)
                updated_fields.append(field)

        if membership.joined_at is None:
            membership.joined_at = timezone.now()
            updated_fields.append("joined_at")

        if updated_fields:
            membership.save(update_fields=updated_fields + ["updated_at"])
        return membership

    def _upsert_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        user_type: str,
        is_staff: bool,
        is_superuser: bool,
        organization: str,
        department: str,
    ) -> User:
        user, created = User.objects.get_or_create(
            email=email.lower().strip(),
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "user_type": user_type,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "email_verified": True,
                "organization": organization,
                "department": department,
            },
        )
        updated_fields: list[str] = []

        for field, value in {
            "first_name": first_name,
            "last_name": last_name,
            "user_type": user_type,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
            "organization": organization,
            "department": department,
            "email_verified": True,
            "is_active": True,
        }.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                updated_fields.append(field)

        user.set_password(password)
        updated_fields.append("password")

        if created:
            user.save()
        else:
            user.save(update_fields=sorted(set(updated_fields + ["updated_at"])))

        return user

    def _ensure_sample_data(self, *, users: dict[str, User], organizations: dict[str, Organization]) -> None:
        authority_user = users["authority"]
        workflow_org = organizations.get("admin")
        primary_committee = Committee.objects.filter(code="parliamentary-appointments-main", is_active=True).first()
        committee_for_records = (
            primary_committee
            if (
                workflow_org is not None
                and primary_committee is not None
                and primary_committee.organization_id == workflow_org.id
            )
            else None
        )
        stage_template = self._ensure_stage_template(
            created_by=users["admin"],
            committee=committee_for_records,
            organization=workflow_org,
        )

        minister_position = self._ensure_position(
            organization=workflow_org,
            title="GAMS Demo Minister of Health",
            branch="executive",
            institution="Ministry of Health",
            appointment_authority="President",
            confirmation_required=False,
            is_public=True,
        )
        justice_position = self._ensure_position(
            organization=workflow_org,
            title="GAMS Demo Chief Justice",
            branch="judicial",
            institution="Judiciary",
            appointment_authority="President",
            confirmation_required=True,
            is_public=True,
        )

        nominee_pending = self._ensure_personnel(
            organization=workflow_org,
            full_name="GAMS Demo Dr. Ama Mensah",
            contact_email="ama.mensah@demo.local",
            is_active_officeholder=False,
            is_public=True,
        )
        nominee_serving = self._ensure_personnel(
            organization=workflow_org,
            full_name="GAMS Demo Hon. Kojo Asante",
            contact_email="kojo.asante@demo.local",
            is_active_officeholder=True,
            is_public=True,
        )

        campaign = self._ensure_campaign(
            organization=workflow_org,
            initiated_by=users["admin"],
            stage_template=stage_template,
            positions=[minister_position, justice_position],
        )

        nomination_record = self._ensure_nomination_record(
            organization=workflow_org,
            position=minister_position,
            nominee=nominee_pending,
            campaign=campaign,
            nominated_by=authority_user,
            committee=committee_for_records,
        )
        self._ensure_draft_publication(nomination_record)

        serving_record = self._ensure_serving_record(
            organization=workflow_org,
            position=justice_position,
            nominee=nominee_serving,
            campaign=campaign,
            decided_by=authority_user,
            committee=committee_for_records,
        )
        self._ensure_published_publication(serving_record, publisher=authority_user)

    def _ensure_stage_template(
        self,
        *,
        created_by: User,
        committee: Committee | None = None,
        organization: Organization | None = None,
    ) -> ApprovalStageTemplate:
        template, created = ApprovalStageTemplate.objects.get_or_create(
            name="GAMS Demo Ministerial Chain",
            exercise_type="ministerial",
            defaults={"created_by": created_by, "organization": organization},
        )
        template_update_fields: list[str] = []
        if not created and template.created_by_id is None:
            template.created_by = created_by
            template_update_fields.append("created_by")
        if template.organization_id != getattr(organization, "id", None):
            template.organization = organization
            template_update_fields.append("organization")
        if template_update_fields:
            template.save(update_fields=template_update_fields)

        if committee is not None and organization is not None and committee.organization_id != organization.id:
            committee = None

        stage_specs = [
            (1, "Intake Check", "vetting_officer", "under_vetting", None),
            (2, "Committee Review", "committee_member", "committee_review", committee),
            (3, "Approval Chain", "appointing_authority", "confirmation_pending", None),
            (4, "Final Appointment Decision", "appointing_authority", "appointed", None),
        ]
        for order, name, required_role, maps_to_status, stage_committee in stage_specs:
            stage = ApprovalStage.objects.filter(template=template, order=order).first()
            if stage is None:
                ApprovalStage.objects.create(
                    template=template,
                    order=order,
                    name=name,
                    required_role=required_role,
                    is_required=True,
                    maps_to_status=maps_to_status,
                    committee=stage_committee,
                )
                continue

            updated_fields: list[str] = []
            for field, value in {
                "name": name,
                "required_role": required_role,
                "is_required": True,
                "maps_to_status": maps_to_status,
                "committee": stage_committee,
            }.items():
                if getattr(stage, field) != value:
                    setattr(stage, field, value)
                    updated_fields.append(field)
            if updated_fields:
                stage.save(update_fields=updated_fields)

        return template

    def _ensure_position(
        self,
        *,
        organization: Organization | None,
        title: str,
        branch: str,
        institution: str,
        appointment_authority: str,
        confirmation_required: bool,
        is_public: bool,
    ) -> GovernmentPosition:
        position = GovernmentPosition.objects.filter(title=title, institution=institution).order_by("created_at").first()
        if position is None:
            return GovernmentPosition.objects.create(
                organization=organization,
                title=title,
                branch=branch,
                institution=institution,
                appointment_authority=appointment_authority,
                confirmation_required=confirmation_required,
                is_public=is_public,
                is_vacant=True,
                constitutional_basis="Demo constitutional reference",
            )

        updated_fields: list[str] = []
        for field, value in {
            "organization": organization,
            "branch": branch,
            "appointment_authority": appointment_authority,
            "confirmation_required": confirmation_required,
            "is_public": is_public,
        }.items():
            if getattr(position, field) != value:
                setattr(position, field, value)
                updated_fields.append(field)
        if updated_fields:
            position.save(update_fields=updated_fields + ["updated_at"])
        return position

    def _ensure_personnel(
        self,
        *,
        organization: Organization | None,
        full_name: str,
        contact_email: str,
        is_active_officeholder: bool,
        is_public: bool,
    ) -> PersonnelRecord:
        record = PersonnelRecord.objects.filter(full_name=full_name, contact_email=contact_email).order_by("created_at").first()
        if record is None:
            return PersonnelRecord.objects.create(
                organization=organization,
                full_name=full_name,
                contact_email=contact_email,
                nationality="Ghanaian",
                is_active_officeholder=is_active_officeholder,
                is_public=is_public,
                bio_summary="Demo personnel profile for government appointment walkthrough.",
            )

        updated_fields: list[str] = []
        for field, value in {
            "organization": organization,
            "is_active_officeholder": is_active_officeholder,
            "is_public": is_public,
            "nationality": "Ghanaian",
        }.items():
            if getattr(record, field) != value:
                setattr(record, field, value)
                updated_fields.append(field)
        if updated_fields:
            record.save(update_fields=updated_fields + ["updated_at"])
        return record

    def _ensure_campaign(
        self,
        *,
        organization: Organization | None,
        initiated_by: User,
        stage_template: ApprovalStageTemplate,
        positions: list[GovernmentPosition],
    ) -> VettingCampaign:
        campaign = VettingCampaign.objects.filter(name="GAMS Demo Ministerial Exercise").order_by("created_at").first()
        if campaign is None:
            campaign = VettingCampaign.objects.create(
                organization=organization,
                name="GAMS Demo Ministerial Exercise",
                description="Demo campaign linking appointments to vetting and approval-chain governance.",
                status="active",
                exercise_type="ministerial",
                jurisdiction="executive",
                approval_template=stage_template,
                appointment_authority="President",
                requires_parliamentary_confirmation=False,
                gazette_reference="GAMS-DEMO-GAZ-2026",
                initiated_by=initiated_by,
            )
        else:
            campaign.organization = organization
            campaign.description = "Demo campaign linking appointments to vetting and approval-chain governance."
            campaign.status = "active"
            campaign.exercise_type = "ministerial"
            campaign.jurisdiction = "executive"
            campaign.approval_template = stage_template
            campaign.appointment_authority = "President"
            campaign.requires_parliamentary_confirmation = False
            campaign.gazette_reference = "GAMS-DEMO-GAZ-2026"
            campaign.save(
                update_fields=[
                    "description",
                    "organization",
                    "status",
                    "exercise_type",
                    "jurisdiction",
                    "approval_template",
                    "appointment_authority",
                    "requires_parliamentary_confirmation",
                    "gazette_reference",
                    "updated_at",
                ]
            )

        campaign.positions.add(*positions)
        return campaign

    def _ensure_nomination_record(
        self,
        *,
        organization: Organization | None,
        position: GovernmentPosition,
        nominee: PersonnelRecord,
        campaign: VettingCampaign,
        nominated_by: User,
        committee: Committee | None,
    ) -> AppointmentRecord:
        record = (
            AppointmentRecord.objects.filter(
                position=position,
                nominee=nominee,
                status__in=ACTIVE_APPOINTMENT_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )
        if record is None:
            record = AppointmentRecord.objects.create(
                organization=organization,
                position=position,
                nominee=nominee,
                appointment_exercise=campaign,
                nominated_by_user=nominated_by,
                nominated_by_display="H.E. President",
                nominated_by_org="Office of the President",
                nomination_date=date.today(),
                status="nominated",
                is_public=False,
                committee=committee,
            )
        else:
            record.organization = organization
            record.appointment_exercise = campaign
            record.status = "nominated"
            record.nominated_by_user = nominated_by
            record.committee = committee
            if not record.nominated_by_display:
                record.nominated_by_display = "H.E. President"
            if not record.nominated_by_org:
                record.nominated_by_org = "Office of the President"
            record.nomination_date = record.nomination_date or date.today()
            record.committee_recommendation = ""
            record.final_decision_by_user = None
            record.final_decision_by_display = ""
            record.appointment_date = None
            record.gazette_number = ""
            record.gazette_date = None
            record.exit_date = None
            record.exit_reason = ""
            record.is_public = False
            record.save(
                update_fields=[
                    "organization",
                    "appointment_exercise",
                    "status",
                    "nominated_by_user",
                    "nominated_by_display",
                    "nominated_by_org",
                    "nomination_date",
                    "committee",
                    "committee_recommendation",
                    "final_decision_by_user",
                    "final_decision_by_display",
                    "appointment_date",
                    "gazette_number",
                    "gazette_date",
                    "exit_date",
                    "exit_reason",
                    "is_public",
                    "updated_at",
                ]
            )

        position_updates: list[str] = []
        if position.current_holder_id is not None:
            position.current_holder = None
            position_updates.append("current_holder")
        if not position.is_vacant:
            position.is_vacant = True
            position_updates.append("is_vacant")
        if position_updates:
            position.save(update_fields=position_updates + ["updated_at"])
        return record

    def _ensure_serving_record(
        self,
        *,
        organization: Organization | None,
        position: GovernmentPosition,
        nominee: PersonnelRecord,
        campaign: VettingCampaign,
        decided_by: User,
        committee: Committee | None,
    ) -> AppointmentRecord:
        record = AppointmentRecord.objects.filter(position=position, status="serving").order_by("-created_at").first()
        if record is None:
            record = (
                AppointmentRecord.objects.filter(position=position, nominee=nominee, status__in=ACTIVE_APPOINTMENT_STATUSES)
                .order_by("-created_at")
                .first()
            )

        if record is None:
            record = AppointmentRecord.objects.create(
                organization=organization,
                position=position,
                nominee=nominee,
                appointment_exercise=campaign,
                nominated_by_user=decided_by,
                nominated_by_display="H.E. President",
                nominated_by_org="Office of the President",
                nomination_date=date.today(),
                status="serving",
                appointment_date=date.today(),
                final_decision_by_user=decided_by,
                final_decision_by_display=decided_by.get_full_name() or decided_by.email,
                is_public=True,
                gazette_number="GAMS-DEMO-GAZ-2026-001",
                gazette_date=date.today(),
                committee=committee,
            )
        else:
            record.organization = organization
            record.status = "serving"
            record.appointment_exercise = campaign
            record.nominee = nominee
            record.committee = committee
            record.appointment_date = record.appointment_date or date.today()
            record.final_decision_by_user = record.final_decision_by_user or decided_by
            if not record.final_decision_by_display:
                record.final_decision_by_display = decided_by.get_full_name() or decided_by.email
            record.is_public = True
            record.gazette_number = record.gazette_number or "GAMS-DEMO-GAZ-2026-001"
            record.gazette_date = record.gazette_date or date.today()
            record.exit_date = None
            record.exit_reason = ""
            record.save(
                update_fields=[
                    "organization",
                    "status",
                    "appointment_exercise",
                    "nominee",
                    "committee",
                    "appointment_date",
                    "final_decision_by_user",
                    "final_decision_by_display",
                    "is_public",
                    "gazette_number",
                    "gazette_date",
                    "exit_date",
                    "exit_reason",
                    "updated_at",
                ]
            )

        position.current_holder = nominee
        position.is_vacant = False
        position.save(update_fields=["current_holder", "is_vacant", "updated_at"])

        nominee.is_active_officeholder = True
        nominee.save(update_fields=["is_active_officeholder", "updated_at"])

        return record

    def _ensure_draft_publication(self, appointment: AppointmentRecord) -> AppointmentPublication:
        publication, _ = AppointmentPublication.objects.get_or_create(
            appointment=appointment,
            defaults={
                "status": "draft",
                "publication_reference": "",
                "publication_document_hash": "",
                "publication_notes": "",
            },
        )
        updated_fields: list[str] = []
        for field, value in {
            "status": "draft",
            "publication_reference": "",
            "publication_document_hash": "",
            "publication_notes": "",
            "published_by": None,
            "published_at": None,
            "revoked_by": None,
            "revoked_at": None,
            "revocation_reason": "",
        }.items():
            if getattr(publication, field) != value:
                setattr(publication, field, value)
                updated_fields.append(field)

        if updated_fields:
            publication.save(update_fields=updated_fields + ["updated_at"])
        return publication

    def _ensure_published_publication(self, appointment: AppointmentRecord, *, publisher: User) -> AppointmentPublication:
        publication, _ = AppointmentPublication.objects.get_or_create(
            appointment=appointment,
            defaults={
                "status": "published",
                "publication_reference": "GAMS-DEMO-GAZ-2026-001",
                "publication_document_hash": "",
                "publication_notes": "Demo publication seeded for supervisor walkthrough.",
                "published_by": publisher,
                "published_at": timezone.now(),
            },
        )

        updated_fields: list[str] = []
        if publication.status != "published":
            publication.status = "published"
            updated_fields.append("status")
        if not publication.publication_reference:
            publication.publication_reference = "GAMS-DEMO-GAZ-2026-001"
            updated_fields.append("publication_reference")
        if not publication.publication_notes:
            publication.publication_notes = "Demo publication seeded for supervisor walkthrough."
            updated_fields.append("publication_notes")
        if publication.published_by_id is None:
            publication.published_by = publisher
            updated_fields.append("published_by")
        if publication.published_at is None:
            publication.published_at = timezone.now()
            updated_fields.append("published_at")
        if publication.revoked_by_id is not None:
            publication.revoked_by = None
            updated_fields.append("revoked_by")
        if publication.revoked_at is not None:
            publication.revoked_at = None
            updated_fields.append("revoked_at")
        if publication.revocation_reason:
            publication.revocation_reason = ""
            updated_fields.append("revocation_reason")

        if updated_fields:
            publication.save(update_fields=updated_fields + ["updated_at"])

        return publication
