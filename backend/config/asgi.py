"""
ASGI config for backend project.
"""

import os

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

django_asgi_app = get_asgi_application()

if not getattr(settings, "ENABLE_REALTIME", False):
    application = django_asgi_app
else:
    try:
        from channels.auth import AuthMiddlewareStack
        from channels.routing import ProtocolTypeRouter, URLRouter
        from apps.interviews.routing import websocket_urlpatterns
    except ModuleNotFoundError:
        application = django_asgi_app
    else:
        application = ProtocolTypeRouter(
            {
                "http": django_asgi_app,
                "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
            }
        )
