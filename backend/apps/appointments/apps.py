from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AppointmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.appointments"
    verbose_name = "Government Appointments"

    def ready(self):
        post_migrate.connect(_ensure_appointment_role_groups, sender=self)


def _ensure_appointment_role_groups(sender, **kwargs):
    from django.contrib.auth.models import Group

    for name in ("vetting_officer", "committee_member", "appointing_authority", "registry_admin"):
        Group.objects.get_or_create(name=name)
