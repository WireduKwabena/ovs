from django.apps import AppConfig


class AuthActionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auth_actions'
    label = 'auth_actions'  # Explicit label to avoid conflicts with django.contrib.auth
