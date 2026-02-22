from django.urls import re_path

from .websocket_handler import InterviewConsumer


websocket_urlpatterns = [
    re_path(r"^ws/interview/(?P<session_id>[^/]+)/$", InterviewConsumer.as_asgi()),
    re_path(r"^ws/interviews/(?P<session_id>[^/]+)/$", InterviewConsumer.as_asgi()),
]
