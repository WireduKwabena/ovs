from django.apps import AppConfig
from importlib import import_module


class InterviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.interviews'

    def ready(self):
        import_module("apps.interviews.signals")
