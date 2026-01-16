"""
WebSocket URL routing configuration.
"""

from django.urls import re_path
from agents.ws.consumers import AudioStreamConsumer
from agents.ws.optimized_streaming_consumer import OptimizedStreamingConsumer
from agents.ws.stt_consumer import STTConsumer

websocket_urlpatterns = [
    # Legacy endpoint (batch processing)
    re_path(r"^ws/audio/?$", AudioStreamConsumer.as_asgi()),
    # Optimized streaming endpoint (low latency)
    re_path(
        r"^ws/stream/(?P<session_id>[^/]+)/?$", OptimizedStreamingConsumer.as_asgi()
    ),
    # STT-only endpoint
    re_path(r"^ws/stt/(?P<session_id>[^/]+)/?$", STTConsumer.as_asgi()),
]
