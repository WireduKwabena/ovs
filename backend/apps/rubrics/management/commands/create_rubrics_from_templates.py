"""Create rubric records from curated template definitions."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.authentication.models import User
from apps.rubrics.templates import RUBRIC_TEMPLATES, create_rubric_from_template


class Command(BaseCommand):
    help = "Create or refresh rubrics from predefined templates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner-email",
            type=str,
            default="hr@system.local",
            help="Email of rubric owner (created as internal reviewer if missing).",
        )
        parser.add_argument(
            "--template",
            type=str,
            default="",
            help="Optional template key to create a single template only.",
        )

    def _get_or_create_owner(self, email: str) -> User:
        owner = User.objects.filter(email=email).first()
        if owner:
            if owner.user_type not in {"internal", "admin"}:
                owner.user_type = "internal"
                owner.is_staff = True
                owner.save(update_fields=["user_type", "is_staff", "updated_at"])
            return owner

        owner = User.objects.create_user(
            email=email,
            password="ChangeMe123!",
            first_name="Internal",
            last_name="Reviewer",
            user_type="internal",
            is_staff=True,
            email_verified=True,
        )
        self.stdout.write(
            self.style.WARNING(
                f"Created owner user '{email}' with temporary password 'ChangeMe123!'."
            )
        )
        return owner

    def handle(self, *args, **options):
        owner = self._get_or_create_owner(options["owner_email"])
        template_key = (options.get("template") or "").strip()

        keys = [template_key] if template_key else list(RUBRIC_TEMPLATES.keys())
        created = 0
        failed = 0

        for key in keys:
            try:
                rubric = create_rubric_from_template(key, created_by=owner)
                self.stdout.write(self.style.SUCCESS(f"Created/updated: {rubric.name}"))
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Failed template '{key}': {exc}"))
                failed += 1

        if failed:
            self.stdout.write(self.style.WARNING(f"Completed with {failed} failure(s)."))
        self.stdout.write(self.style.SUCCESS(f"Processed {created} template(s) successfully."))

