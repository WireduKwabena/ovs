from django.apps import AppConfig
from django.db.models.signals import post_migrate
import os


class AppointmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.appointments"
    verbose_name = "Government Appointments"

    def ready(self):
        # Only connect signal if not in initialization mode (env var set by entrypoint)
        if not os.environ.get("DJANGO_SKIP_POST_MIGRATE_SIGNALS"):
            post_migrate.connect(_ensure_appointment_role_groups, sender=self)


def _ensure_appointment_role_groups(sender, **kwargs):
    from django.contrib.auth.models import Group

    for name in (
        "vetting_officer",
        "committee_member",
        "committee_chair",
        "appointing_authority",
        "registry_admin",
        "publication_officer",
        "auditor",
    ):
        Group.objects.get_or_create(name=name)
