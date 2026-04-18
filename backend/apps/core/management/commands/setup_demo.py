from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from django_tenants.utils import schema_context

from apps.appointments.models import AppointmentPublication, AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from apps.users.models import User
from apps.billing.models import BillingSubscription, OrganizationOnboardingToken
from apps.billing.services import create_organization_onboarding_token, get_active_onboarding_token_for_organization
from apps.campaigns.models import VettingCampaign
from apps.governance.models import Committee, CommitteeMembership, OrganizationMembership
from apps.notifications.models import Notification
from apps.tenants.models import Organization
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

# (arg-prefix, default-email, default-password)
_DEMO_USERS: tuple[tuple[str, str, str], ...] = (
    ("admin",           "gams.admin@demo.local",          "DemoAdmin123!"),
    ("vetting",         "gams.vetting@demo.local",         "DemoVetting123!"),
    ("committee",       "gams.committee@demo.local",       "DemoCommittee123!"),
    ("committee-chair", "gams.committeechair@demo.local",  "DemoCommitteeChair123!"),
    ("authority",       "gams.authority@demo.local",       "DemoAuthority123!"),
    ("registry",        "gams.registry@demo.local",        "DemoRegistry123!"),
    ("publication",     "gams.publication@demo.local",     "DemoPublication123!"),
    ("auditor",         "gams.auditor@demo.local",         "DemoAuditor123!"),
)

DEMO_NOTIFICATIONS = [
    {
        "subject": "Vetting case assigned to you",
        "message": (
            "A new vetting case has been assigned to you for review. "
            "Please open the case and begin the initial document verification."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "high",
        "metadata": {"event_type": "case_assigned", "case_id": "DEMO-CASE-001"},
    },
    {
        "subject": "AI analysis complete",
        "message": (
            "The AI vetting analysis for case DEMO-CASE-001 is complete. "
            "Recommendation: manual review required. Confidence score: 72%."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "normal",
        "metadata": {
            "event_type": "ai_analysis_complete",
            "case_id": "DEMO-CASE-001",
            "recommendation": "recommend_manual_review",
            "score": "72",
        },
    },
    {
        "subject": "Committee review scheduled",
        "message": (
            "A committee review session has been scheduled for nominee "
            "John Addo on Thursday at 10:00 AM. Please confirm your attendance."
        ),
        "notification_type": "in_app",
        "status": "read",
        "priority": "normal",
        "metadata": {"event_type": "committee_review_scheduled"},
    },
    {
        "subject": "Document verification failed",
        "message": (
            "The national ID document submitted for case DEMO-CASE-002 "
            "failed authenticity verification. A fraud flag has been raised for manual review."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "urgent",
        "metadata": {
            "event_type": "document_verification_failed",
            "case_id": "DEMO-CASE-002",
            "document_type": "national_id",
            "document_status": "failed",
        },
    },
    {
        "subject": "Appointment approved",
        "message": (
            "The appointment for Justice Kwame Asante to the position of "
            "Director of Public Prosecutions has been approved and signed off."
        ),
        "notification_type": "in_app",
        "status": "read",
        "priority": "normal",
        "metadata": {"event_type": "appointment_approved", "new_status": "appointed"},
    },
    {
        "subject": "New organization registered",
        "message": (
            "A new organization 'Ghana Audit Service' has registered on the platform "
            "and is pending onboarding review."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "low",
        "metadata": {"event_type": "org_registered"},
    },
    {
        "subject": "Interview session ready",
        "message": (
            "The AI interview session for candidate Abena Mensah is ready to begin. "
            "Click below to join the vetting interview."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "high",
        "metadata": {"event_type": "interview_ready", "case_id": "DEMO-CASE-003"},
    },
    {
        "subject": "Gazette published",
        "message": (
            "The appointment gazette for Q1 2026 has been published. "
            "3 new appointments are now publicly visible on the transparency portal."
        ),
        "notification_type": "in_app",
        "status": "read",
        "priority": "normal",
        "metadata": {"event_type": "gazette_published"},
    },
]


class Command(BaseCommand):
    help = "Bootstrap a safe, idempotent GAMS demo workspace (users, roles, sample workflow records, and notifications)."

    def add_arguments(self, parser):
        for role, default_email, default_password in _DEMO_USERS:
            parser.add_argument(f"--{role}-email", default=default_email)
            parser.add_argument(f"--{role}-password", default=default_password)
        parser.add_argument(
            "--skip-sample-data",
            action="store_true",
            help="Create role accounts/groups only; skip campaign/position/personnel/appointment demo records.",
        )
        parser.add_argument(
            "--skip-notifications",
            action="store_true",
            help="Skip seeding demo in-app notifications.",
        )
        parser.add_argument(
            "--clear-notifications",
            action="store_true",
            help="Delete existing demo notifications before re-seeding them.",
        )
        parser.add_argument(
            "--org-slug",
            default="public-service-commission",
            help=(
                "Code/slug of the primary demo organisation tenant that owns all workflow data. "
                "The PostgreSQL schema is created automatically if it does not exist yet. "
                "Defaults to 'public-service-commission'."
            ),
        )

    def handle(self, *args, **options):
        # ── Step 1: verify public-schema tables (Organisation lives in the shared schema) ──
        self._ensure_schema_ready({Organization}, "tenant registry")

        # ── Step 2: ensure ALL demo organisations exist in the public schema.
        #    Organisation is a TenantMixin model that lives in the *public* schema.
        #    It must never be created inside a schema_context() block — doing so
        #    causes django-tenants to raise "Can't create tenant outside the public schema".
        primary_org = self._upsert_organization(
            name="Public Service Commission",
            code=options["org_slug"],
            organization_type="agency",
        )
        secondary_org_specs = {
            "vetting":   ("Appointments Secretariat",             "appointments-secretariat",            "agency"),
            "committee": ("Parliamentary Appointments Committee", "parliamentary-appointments-committee", "committee_secretariat"),
            "authority": ("Office of the President",              "office-of-the-president",             "executive_office"),
            "registry":  ("Gazette and Records Office",           "gazette-and-records-office",          "agency"),
            "auditor":   ("Audit Service",                        "audit-service",                       "audit"),
        }
        organizations: dict[str, Organization] = {
            key: self._upsert_organization(name=name, code=code, organization_type=org_type)
            for key, (name, code, org_type) in secondary_org_specs.items()
        }
        organizations["admin"] = primary_org
        organizations["publication"] = organizations["registry"]

        # ── Step 3: all tenant-app operations must run inside the org's schema context.
        #    Management commands have no HTTP request, so TenantMiddleware never fires;
        #    without schema_context the connection stays in the public schema where
        #    TENANT_APP tables (Committee, VettingCampaign, …) do not exist.
        with schema_context(primary_org.schema_name):
            self._ensure_schema_ready(
                {Committee, CommitteeMembership, OrganizationMembership},
                "governance",
            )
            if not options["skip_sample_data"]:
                self._ensure_schema_ready(
                    {
                        ApprovalStageTemplate, ApprovalStage, AppointmentRecord, AppointmentPublication,
                        VettingCampaign, GovernmentPosition, PersonnelRecord,
                        BillingSubscription, OrganizationOnboardingToken,
                    },
                    "sample data",
                )

            with transaction.atomic():
                groups = self._ensure_groups()
                users = self._ensure_users(options=options, groups=groups)
                organizations = self._ensure_governance_foundation(
                    users=users, primary_org=primary_org, organizations=organizations,
                )

                if not options["skip_sample_data"]:
                    self._ensure_sample_data(users=users, organizations=organizations)

            if not options["skip_notifications"]:
                self._seed_notifications(
                    users=users,
                    clear=options["clear_notifications"],
                )

        self.stdout.write(self.style.SUCCESS("GAMS demo setup completed."))
        self.stdout.write("Demo sign-in accounts:")
        for role, _, _ in _DEMO_USERS:
            key = role.replace("-", "_")
            label = role.replace("-", " ").title()
            self.stdout.write(f"  {label:<20s} {options[f'{key}_email']} / {options[f'{key}_password']}")

    # ── Schema guards ─────────────────────────────────────────────────────────

    def _ensure_schema_ready(self, models: set, context: str) -> None:
        required_tables = {m._meta.db_table for m in models}
        existing_tables = set(connection.introspection.table_names())
        missing = sorted(required_tables - existing_tables)
        if missing:
            raise CommandError(
                f"Cannot seed {context} demo records because required tables are missing: "
                f"{', '.join(missing)}. Run `python manage.py migrate` and retry."
            )

    # ── Field-diff helper ──────────────────────────────────────────────────────

    def _update_fields(self, instance, fields: dict) -> list[str]:
        """Assign each field where the current value differs; return list of changed field names."""
        changed: list[str] = []
        for field, value in fields.items():
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                changed.append(field)
        return changed

    # ── Groups ────────────────────────────────────────────────────────────────

    def _ensure_groups(self) -> dict[str, Group]:
        groups: dict[str, Group] = {}
        for name in APPOINTMENT_ROLE_GROUPS:
            group, _ = Group.objects.get_or_create(name=name)
            groups[name] = group
        return groups

    # ── Users ─────────────────────────────────────────────────────────────────

    def _ensure_users(self, *, options: dict, groups: dict[str, Group]) -> dict[str, User]:
        def opt(role: str, suffix: str) -> str:
            return options[f"{role.replace('-', '_')}_{suffix}"]

        admin_user = self._upsert_user(
            email=opt("admin", "email"),
            password=opt("admin", "password"),
            first_name="GAMS", last_name="Administrator",
            user_type="admin", is_staff=True, is_superuser=True,
            organization="Public Service Commission", department="Appointments Secretariat",
        )
        # Platform superusers must not inherit tenant workflow roles.
        admin_user.groups.remove(*groups.values())

        vetting_user = self._upsert_user(
            email=opt("vetting", "email"),
            password=opt("vetting", "password"),
            first_name="Vetting", last_name="Officer",
            user_type="internal",
            organization="Appointments Secretariat", department="Vetting",
        )
        vetting_user.groups.add(groups["vetting_officer"])

        committee_user = self._upsert_user(
            email=opt("committee", "email"),
            password=opt("committee", "password"),
            first_name="Committee", last_name="Member",
            user_type="internal",
            organization="Parliamentary Appointments Committee", department="Review",
        )
        committee_user.groups.add(groups["committee_member"])

        committee_chair_user = self._upsert_user(
            email=opt("committee-chair", "email"),
            password=opt("committee-chair", "password"),
            first_name="Committee", last_name="Chair",
            user_type="internal",
            organization="Parliamentary Appointments Committee", department="Review",
        )
        committee_chair_user.groups.add(groups["committee_chair"])

        authority_user = self._upsert_user(
            email=opt("authority", "email"),
            password=opt("authority", "password"),
            first_name="Appointing", last_name="Authority",
            user_type="internal",
            organization="Office of the President", department="Executive",
        )
        authority_user.groups.add(groups["appointing_authority"])

        registry_user = self._upsert_user(
            email=opt("registry", "email"),
            password=opt("registry", "password"),
            first_name="Registry", last_name="Officer",
            user_type="internal",
            organization="Gazette and Records Office", department="Records",
        )
        registry_user.groups.add(groups["registry_admin"])

        publication_user = self._upsert_user(
            email=opt("publication", "email"),
            password=opt("publication", "password"),
            first_name="Publication", last_name="Officer",
            user_type="internal",
            organization="Gazette and Records Office", department="Publication",
        )
        publication_user.groups.add(groups["publication_officer"])

        auditor_user = self._upsert_user(
            email=opt("auditor", "email"),
            password=opt("auditor", "password"),
            first_name="Government", last_name="Auditor",
            user_type="internal",
            organization="Audit Service", department="Compliance",
        )
        auditor_user.groups.add(groups["auditor"])

        return {
            "admin": admin_user,
            "vetting": vetting_user,
            "committee": committee_user,
            "committee_chair": committee_chair_user,
            "authority": authority_user,
            "registry": registry_user,
            "publication": publication_user,
            "auditor": auditor_user,
        }

    # ── Governance foundation ──────────────────────────────────────────────────

    def _ensure_governance_foundation(
        self,
        *,
        users: dict[str, User],
        primary_org: Organization,
        organizations: dict[str, Organization],
    ) -> dict[str, Organization]:
        # All Organisation objects were created in the public schema (in handle())
        # before schema_context was entered.  This method only creates tenant-app
        # records (OrganizationMembership, Committee, CommitteeMembership).
        workflow_org = organizations["admin"]

        # Platform superusers are system-wide operators, not tenant members.
        self._remove_org_memberships(user=users["admin"])

        # Memberships for roles that don't participate in committee setup.
        for key, role in {
            "vetting":     "vetting_officer",
            "authority":   "appointing_authority",
            "registry":    "registry_admin",
            "publication": "publication_officer",
            "auditor":     "auditor",
        }.items():
            self._upsert_org_membership(
                user=users[key], membership_role=role, is_default=True,
            )

        # Capture these two for committee membership assignment below.
        committee_membership = self._upsert_org_membership(
            user=users["committee"], membership_role="committee_member", is_default=True,
        )
        chair_membership = self._upsert_org_membership(
            user=users["committee_chair"], membership_role="committee_chair", is_default=True,
        )

        committee = self._upsert_committee(
            code="parliamentary-appointments-main",
            name="Parliamentary Appointments Main Committee",
            committee_type="approval",
            created_by=users["admin"],
            description="Primary committee for the demo approval-chain walkthrough.",
        )
        self._upsert_committee_membership(
            committee=committee,
            user=users["committee"],
            organization_membership=committee_membership,
            committee_role="member",
            can_vote=True,
        )
        CommitteeMembership.assign_active_chair(
            committee=committee,
            user=users["committee_chair"],
            organization_membership=chair_membership,
            can_vote=True,
        )

        return organizations

    # ── Sample data ───────────────────────────────────────────────────────────

    def _ensure_sample_data(self, *, users: dict[str, User], organizations: dict[str, Organization]) -> None:
        workflow_org = organizations["admin"]

        self._ensure_billing_demo_state(organization=workflow_org, org_admin_user=users["registry"])

        committee_for_records = (
            Committee.objects.filter(
                code="parliamentary-appointments-main",
                is_active=True,
            )
            .order_by("-updated_at")
            .first()
        )
        if committee_for_records is None:
            raise CommandError(
                "Committee 'parliamentary-appointments-main' was not found in the current tenant schema. "
                "Run setup_demo without --skip-sample-data at least once first, or check that "
                "_ensure_governance_foundation completed successfully."
            )

        stage_template = self._ensure_stage_template(
            created_by=users["admin"],
            committee=committee_for_records,
        )

        minister_position = self._ensure_position(
            title="GAMS Demo Minister of Health",
            branch="executive",
            institution="Ministry of Health",
            appointment_authority="President",
            confirmation_required=False,
            is_public=True,
        )
        justice_position = self._ensure_position(
            title="GAMS Demo Chief Justice",
            branch="judicial",
            institution="Judiciary",
            appointment_authority="President",
            confirmation_required=True,
            is_public=True,
        )

        nominee_pending = self._ensure_personnel(
            full_name="GAMS Demo Dr. Ama Mensah",
            contact_email="ama.mensah@demo.local",
            is_active_officeholder=False,
            is_public=True,
        )
        nominee_serving = self._ensure_personnel(
            full_name="GAMS Demo Hon. Kojo Asante",
            contact_email="kojo.asante@demo.local",
            is_active_officeholder=True,
            is_public=True,
        )

        campaign = self._ensure_campaign(
            initiated_by=users["admin"],
            stage_template=stage_template,
            positions=[minister_position, justice_position],
        )

        nomination_record = self._ensure_nomination_record(
            position=minister_position,
            nominee=nominee_pending,
            campaign=campaign,
            nominated_by=users["authority"],
            committee=committee_for_records,
        )
        self._ensure_draft_publication(nomination_record)

        serving_record = self._ensure_serving_record(
            position=justice_position,
            nominee=nominee_serving,
            campaign=campaign,
            decided_by=users["authority"],
            committee=committee_for_records,
        )
        self._ensure_published_publication(serving_record, publisher=users["publication"])

    # ── Notifications ─────────────────────────────────────────────────────────

    def _seed_notifications(self, *, users: dict[str, User], clear: bool) -> None:
        """Seed demo in-app notifications for all demo users. Must be called inside schema_context."""
        demo_subjects = [n["subject"] for n in DEMO_NOTIFICATIONS]
        all_users = list(users.values())

        if clear:
            deleted, _ = Notification.objects.filter(
                recipient__in=all_users,
                subject__in=demo_subjects,
            ).delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing demo notifications."))

        now = timezone.now()
        created_count = 0

        for user in all_users:
            for i, demo in enumerate(DEMO_NOTIFICATIONS):
                offset_minutes = i * 47 + 3
                created_at = now - timedelta(minutes=offset_minutes)

                notif = Notification(
                    recipient=user,
                    subject=demo["subject"],
                    message=demo["message"],
                    notification_type=demo["notification_type"],
                    status=demo["status"],
                    priority=demo["priority"],
                    metadata=demo["metadata"],
                    is_archived=False,
                    sent_at=created_at if demo["status"] in ("sent", "read") else None,
                    read_at=created_at + timedelta(minutes=5) if demo["status"] == "read" else None,
                )
                notif.save()
                Notification.objects.filter(pk=notif.pk).update(created_at=created_at)
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_count} notifications across {len(all_users)} demo user(s)."
            )
        )

    # ── Billing & onboarding token ────────────────────────────────────────────

    def _ensure_billing_demo_state(self, *, organization: Organization, org_admin_user: User) -> None:
        normalized_email = str(org_admin_user.email or "").strip().lower()
        subscription, _ = BillingSubscription.objects.get_or_create(
            reference="GAMS-DEMO-ORG-SUBSCRIPTION",
            defaults={
                "provider": "sandbox",
                "status": "complete",
                "payment_status": "paid",
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "annual",
                "payment_method": "card",
                "amount_usd": Decimal("3990.00"),
                "registration_consumed_at": timezone.now(),
                "registration_consumed_by_email": normalized_email,
                "metadata": {"seeded_by": "setup_demo", "organization_id": str(organization.id)},
            },
        )

        changed = self._update_fields(subscription, {
            "provider": "sandbox",
            "status": "complete",
            "payment_status": "paid",
            "plan_id": "growth",
            "plan_name": "Growth",
            "billing_cycle": "annual",
            "payment_method": "card",
            "amount_usd": Decimal("3990.00"),
            "registration_consumed_by_email": normalized_email,
        })
        if not subscription.registration_consumed_at:
            subscription.registration_consumed_at = timezone.now()
            changed.append("registration_consumed_at")
        metadata = subscription.metadata if isinstance(subscription.metadata, dict) else {}
        if metadata.get("organization_id") != str(organization.id):
            metadata.update({"organization_id": str(organization.id), "seeded_by": "setup_demo"})
            subscription.metadata = metadata
            changed.append("metadata")
        if changed:
            subscription.save(update_fields=changed + ["updated_at"])

        now = timezone.now()
        active_token = get_active_onboarding_token_for_organization(organization_id=str(organization.id))
        token_still_usable = bool(
            active_token
            and active_token.is_active
            and (active_token.expires_at is None or active_token.expires_at > now)
            and (active_token.max_uses is None or int(active_token.uses or 0) < int(active_token.max_uses))
        )
        if token_still_usable and active_token is not None:
            token_changed = self._update_fields(active_token, {
                "subscription": subscription,
                "max_uses": active_token.max_uses or 50,
                "expires_at": active_token.expires_at or now + timedelta(days=30),
            })
            if token_changed:
                active_token.save(update_fields=token_changed + ["updated_at"])
            return

        create_organization_onboarding_token(
            organization=organization,
            subscription=subscription,
            created_by=org_admin_user,
            expires_at=now + timedelta(days=30),
            max_uses=50,
            allowed_email_domain="",
            rotate=True,
            metadata={"seeded_by": "setup_demo"},
        )

    # ── Stage template ─────────────────────────────────────────────────────────

    def _ensure_stage_template(
        self,
        *,
        created_by: User,
        committee: Committee | None = None,
    ) -> ApprovalStageTemplate:
        template, _ = ApprovalStageTemplate.objects.get_or_create(
            name="GAMS Demo Ministerial Chain",
            exercise_type="ministerial",
            defaults={"created_by": created_by},
        )
        changed: list[str] = []
        if template.created_by_id is None:
            template.created_by = created_by
            changed.append("created_by")
        if changed:
            template.save(update_fields=changed + ["updated_at"])

        stage_specs = [
            (1, "Intake Check",              "vetting_officer",      "under_vetting",        None),
            (2, "Committee Review",          "committee_member",     "committee_review",     committee),
            (3, "Approval Chain",            "appointing_authority", "confirmation_pending", None),
            (4, "Final Appointment Decision","appointing_authority", "appointed",            None),
        ]
        for order, name, required_role, maps_to_status, stage_committee in stage_specs:
            stage, stage_created = ApprovalStage.objects.get_or_create(
                template=template,
                order=order,
                defaults={
                    "name": name, "required_role": required_role, "is_required": True,
                    "maps_to_status": maps_to_status, "committee": stage_committee,
                },
            )
            if not stage_created:
                stage_changed = self._update_fields(stage, {
                    "name": name, "required_role": required_role, "is_required": True,
                    "maps_to_status": maps_to_status, "committee": stage_committee,
                })
                if stage_changed:
                    stage.save(update_fields=stage_changed)

        return template

    # ── Positions & personnel ──────────────────────────────────────────────────

    def _ensure_position(
        self,
        *,
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
                title=title, branch=branch, institution=institution,
                appointment_authority=appointment_authority, confirmation_required=confirmation_required,
                is_public=is_public, is_vacant=True, constitutional_basis="Demo constitutional reference",
            )
        changed = self._update_fields(position, {
            "branch": branch,
            "appointment_authority": appointment_authority,
            "confirmation_required": confirmation_required, "is_public": is_public,
        })
        if changed:
            position.save(update_fields=changed + ["updated_at"])
        return position

    def _ensure_personnel(
        self,
        *,
        full_name: str,
        contact_email: str,
        is_active_officeholder: bool,
        is_public: bool,
    ) -> PersonnelRecord:
        record = PersonnelRecord.objects.filter(full_name=full_name, contact_email=contact_email).order_by("created_at").first()
        if record is None:
            return PersonnelRecord.objects.create(
                full_name=full_name, contact_email=contact_email,
                nationality="Ghanaian", is_active_officeholder=is_active_officeholder, is_public=is_public,
                bio_summary="Demo personnel profile for government appointment walkthrough.",
            )
        changed = self._update_fields(record, {
            "is_active_officeholder": is_active_officeholder,
            "is_public": is_public, "nationality": "Ghanaian",
        })
        if changed:
            record.save(update_fields=changed + ["updated_at"])
        return record

    # ── Campaign ───────────────────────────────────────────────────────────────

    def _ensure_campaign(
        self,
        *,
        initiated_by: User,
        stage_template: ApprovalStageTemplate,
        positions: list[GovernmentPosition],
    ) -> VettingCampaign:
        desired = {
            "description": "Demo campaign linking appointments to vetting and approval-chain governance.",
            "status": "active",
            "exercise_type": "ministerial",
            "jurisdiction": "executive",
            "approval_template": stage_template,
            "appointment_authority": "President",
            "requires_parliamentary_confirmation": False,
            "gazette_reference": "GAMS-DEMO-GAZ-2026",
        }
        campaign = VettingCampaign.objects.filter(name="GAMS Demo Ministerial Exercise").order_by("created_at").first()
        if campaign is None:
            campaign = VettingCampaign.objects.create(
                name="GAMS Demo Ministerial Exercise",
                initiated_by=initiated_by,
                **desired,
            )
        else:
            changed = self._update_fields(campaign, desired)
            if changed:
                campaign.save(update_fields=changed + ["updated_at"])
        campaign.positions.add(*positions)
        return campaign

    # ── Appointment records ────────────────────────────────────────────────────

    def _ensure_nomination_record(
        self,
        *,
        position: GovernmentPosition,
        nominee: PersonnelRecord,
        campaign: VettingCampaign,
        nominated_by: User,
        committee: Committee | None,
    ) -> AppointmentRecord:
        record = (
            AppointmentRecord.objects.filter(
                position=position, nominee=nominee, status__in=ACTIVE_APPOINTMENT_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )
        if record is None:
            record = AppointmentRecord.objects.create(
                position=position, nominee=nominee,
                appointment_exercise=campaign, nominated_by_user=nominated_by,
                nominated_by_display="H.E. President", nominated_by_org="Office of the President",
                nomination_date=date.today(), status="nominated", is_public=False, committee=committee,
            )
        else:
            changed = self._update_fields(record, {
                "appointment_exercise": campaign,
                "status": "nominated",
                "nominated_by_user": nominated_by,
                "nominated_by_display": record.nominated_by_display or "H.E. President",
                "nominated_by_org": record.nominated_by_org or "Office of the President",
                "nomination_date": record.nomination_date or date.today(),
                "committee": committee,
                "committee_recommendation": "",
                "final_decision_by_user": None,
                "final_decision_by_display": "",
                "appointment_date": None,
                "gazette_number": "",
                "gazette_date": None,
                "exit_date": None,
                "exit_reason": "",
                "is_public": False,
            })
            if changed:
                record.save(update_fields=changed + ["updated_at"])

        position_changed = self._update_fields(position, {"current_holder": None, "is_vacant": True})
        if position_changed:
            position.save(update_fields=position_changed + ["updated_at"])
        return record

    def _ensure_serving_record(
        self,
        *,
        position: GovernmentPosition,
        nominee: PersonnelRecord,
        campaign: VettingCampaign,
        decided_by: User,
        committee: Committee | None,
    ) -> AppointmentRecord:
        record = AppointmentRecord.objects.filter(position=position, status="serving").order_by("-created_at").first()
        if record is None:
            record = (
                AppointmentRecord.objects.filter(
                    position=position, nominee=nominee, status__in=ACTIVE_APPOINTMENT_STATUSES,
                )
                .order_by("-created_at")
                .first()
            )

        if record is None:
            record = AppointmentRecord.objects.create(
                position=position, nominee=nominee,
                appointment_exercise=campaign, nominated_by_user=decided_by,
                nominated_by_display="H.E. President", nominated_by_org="Office of the President",
                nomination_date=date.today(), status="serving", appointment_date=date.today(),
                final_decision_by_user=decided_by,
                final_decision_by_display=decided_by.get_full_name() or decided_by.email,
                is_public=True, gazette_number="GAMS-DEMO-GAZ-2026-001",
                gazette_date=date.today(), committee=committee,
            )
        else:
            changed = self._update_fields(record, {
                "status": "serving",
                "appointment_exercise": campaign,
                "nominee": nominee,
                "committee": committee,
                "appointment_date": record.appointment_date or date.today(),
                "final_decision_by_user": record.final_decision_by_user or decided_by,
                "final_decision_by_display": record.final_decision_by_display or (decided_by.get_full_name() or decided_by.email),
                "is_public": True,
                "gazette_number": record.gazette_number or "GAMS-DEMO-GAZ-2026-001",
                "gazette_date": record.gazette_date or date.today(),
                "exit_date": None,
                "exit_reason": "",
            })
            if changed:
                record.save(update_fields=changed + ["updated_at"])

        position_changed = self._update_fields(position, {"current_holder": nominee, "is_vacant": False})
        if position_changed:
            position.save(update_fields=position_changed + ["updated_at"])

        nominee_changed = self._update_fields(nominee, {"is_active_officeholder": True})
        if nominee_changed:
            nominee.save(update_fields=nominee_changed + ["updated_at"])

        return record

    # ── Publications ───────────────────────────────────────────────────────────

    def _ensure_draft_publication(self, appointment: AppointmentRecord) -> AppointmentPublication:
        desired = {
            "status": "draft",
            "publication_reference": "",
            "publication_document_hash": "",
            "publication_notes": "",
            "published_by": None,
            "published_at": None,
            "revoked_by": None,
            "revoked_at": None,
            "revocation_reason": "",
        }
        publication, _ = AppointmentPublication.objects.get_or_create(appointment=appointment, defaults=desired)
        changed = self._update_fields(publication, desired)
        if changed:
            publication.save(update_fields=changed + ["updated_at"])
        return publication

    def _ensure_published_publication(
        self, appointment: AppointmentRecord, *, publisher: User
    ) -> AppointmentPublication:
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
        changed = self._update_fields(publication, {
            "status": "published",
            "publication_reference": publication.publication_reference or "GAMS-DEMO-GAZ-2026-001",
            "publication_notes": publication.publication_notes or "Demo publication seeded for supervisor walkthrough.",
            "published_by": publication.published_by or publisher,
            "published_at": publication.published_at or timezone.now(),
            "revoked_by": None,
            "revoked_at": None,
            "revocation_reason": "",
        })
        if changed:
            publication.save(update_fields=changed + ["updated_at"])
        return publication

    # ── Low-level upsert helpers ───────────────────────────────────────────────

    def _upsert_organization(self, *, code: str, name: str, organization_type: str) -> Organization:
        # schema_name is required by TenantMixin (maps to the PostgreSQL schema name).
        # Derive it from the slug: hyphens are not valid in PG identifiers.
        schema_name = code.replace("-", "_")
        organization, _ = Organization.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "schema_name": schema_name,
                "organization_type": organization_type,
                "is_active": True,
            },
        )
        changed = self._update_fields(organization, {"name": name, "organization_type": organization_type, "is_active": True})
        if changed:
            organization.save(update_fields=changed + ["updated_at"])
        return organization

    def _upsert_org_membership(
        self, *, user: User, membership_role: str, is_default: bool
    ) -> OrganizationMembership:
        membership, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            defaults={
                "membership_role": membership_role, "is_active": True,
                "is_default": is_default, "joined_at": timezone.now(),
            },
        )
        if is_default:
            OrganizationMembership.objects.filter(user=user, is_default=True).exclude(pk=membership.pk).update(is_default=False)
        changed = self._update_fields(membership, {
            "membership_role": membership_role, "is_active": True, "is_default": is_default, "left_at": None,
        })
        if membership.joined_at is None:
            membership.joined_at = timezone.now()
            changed.append("joined_at")
        if changed:
            membership.save(update_fields=changed + ["updated_at"])
        return membership

    def _remove_org_memberships(self, *, user: User) -> None:
        OrganizationMembership.objects.filter(user=user).delete()

    def _upsert_committee(
        self,
        *,
        code: str,
        name: str,
        committee_type: str,
        created_by: User,
        description: str,
    ) -> Committee:
        committee, _ = Committee.objects.get_or_create(
            code=code,
            defaults={
                "name": name, "committee_type": committee_type,
                "description": description, "is_active": True, "created_by": created_by,
            },
        )
        # `created_by` is intentionally excluded from the update dict: it is an
        # immutable audit field that should only be set on first creation.
        # Including it here would overwrite the original creator on every re-run.
        changed = self._update_fields(committee, {
            "name": name, "committee_type": committee_type,
            "description": description, "is_active": True,
        })
        if changed:
            committee.save(update_fields=changed + ["updated_at"])
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
        membership, _ = CommitteeMembership.objects.get_or_create(
            committee=committee,
            user=user,
            defaults={
                "organization_membership": organization_membership, "committee_role": committee_role,
                "can_vote": can_vote, "is_active": True, "joined_at": timezone.now(),
            },
        )
        changed = self._update_fields(membership, {
            "organization_membership": organization_membership, "committee_role": committee_role,
            "can_vote": can_vote, "is_active": True, "left_at": None,
        })
        if membership.joined_at is None:
            membership.joined_at = timezone.now()
            changed.append("joined_at")
        if changed:
            membership.save(update_fields=changed + ["updated_at"])
        return membership

    def _upsert_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        user_type: str,
        is_staff: bool = False,
        is_superuser: bool = False,
        organization: str,
        department: str,
    ) -> User:
        user, created = User.objects.get_or_create(
            email=email.lower().strip(),
            defaults={
                "first_name": first_name, "last_name": last_name, "user_type": user_type,
                "is_staff": is_staff, "is_superuser": is_superuser, "email_verified": True,
                "organization": organization, "department": department,
            },
        )
        changed = self._update_fields(user, {
            "first_name": first_name, "last_name": last_name, "user_type": user_type,
            "is_staff": is_staff, "is_superuser": is_superuser, "organization": organization,
            "department": department, "email_verified": True, "is_active": True,
        })
        user.set_password(password)
        changed.append("password")
        if created:
            user.save()
        else:
            user.save(update_fields=sorted(set(changed + ["updated_at"])))
        return user
