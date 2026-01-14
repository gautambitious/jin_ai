"""
WebSocket URL routing configuration.
"""

from django.urls import re_path
from agents.ws.consumers import AudioStreamConsumer

websocket_urlpatterns = [
    re_path(r"^ws/audio/?$", AudioStreamConsumer.as_asgi()),
]
