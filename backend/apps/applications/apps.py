from django.apps import AppConfig
from importlib import import_module


class ApplicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.applications'

    def ready(self):
        import_module("apps.applications.signal")
