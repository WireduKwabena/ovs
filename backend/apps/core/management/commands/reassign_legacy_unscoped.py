from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.appointments.models import AppointmentRecord, ApprovalStageTemplate
from apps.applications.models import VettingCase
from apps.campaigns.models import VettingCampaign
from apps.tenants.models import Organization
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition
from apps.rubrics.models import VettingRubric


class Command(BaseCommand):
    help = (
        "Reassign organization-owned internal records currently attached to the "
        "legacy-unscoped quarantine organization to a target organization."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-org-code",
            default="legacy-unscoped",
            help="Source organization code to move records from (default: legacy-unscoped).",
        )
        parser.add_argument(
            "--target-org-code",
            default="public-service-commission",
            help="Target organization code to move records to (default: public-service-commission).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview reassignment counts without writing changes.",
        )

    def handle(self, *args, **options):
        source_code = str(options.get("source_org_code") or "").strip()
        target_code = str(options.get("target_org_code") or "").strip()
        dry_run = bool(options.get("dry_run"))

        if not source_code or not target_code:
            raise CommandError("Both --source-org-code and --target-org-code are required.")
        if source_code == target_code:
            raise CommandError("Source and target organization codes must be different.")

        source_org = Organization.objects.filter(code=source_code).first()
        if source_org is None:
            self.stdout.write(self.style.WARNING(f"Source organization '{source_code}' does not exist. Nothing to reassign."))
            return

        target_org = Organization.objects.filter(code=target_code).first()
        if target_org is None:
            raise CommandError(f"Target organization '{target_code}' was not found.")

        model_specs = (
            ("positions.GovernmentPosition", GovernmentPosition),
            ("personnel.PersonnelRecord", PersonnelRecord),
            ("campaigns.VettingCampaign", VettingCampaign),
            ("applications.VettingCase", VettingCase),
            ("appointments.ApprovalStageTemplate", ApprovalStageTemplate),
            ("appointments.AppointmentRecord", AppointmentRecord),
            ("rubrics.VettingRubric", VettingRubric),
        )

        reassigned_total = 0
        with transaction.atomic():
            for label, model in model_specs:
                qs = model.objects.filter(organization_id=source_org.id)
                count = qs.count()
                self.stdout.write(f"{label}: {count}")
                if count and not dry_run:
                    qs.update(organization_id=target_org.id)
                    reassigned_total += count

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run complete. No records were updated."))
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"Reassignment complete. Moved {reassigned_total} record(s) "
                f"from '{source_code}' to '{target_code}'."
            )
        )

