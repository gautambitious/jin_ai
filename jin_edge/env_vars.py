"""Environment variables - Direct access to configuration."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the jin_edge directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

# WebSocket Configuration
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:8000/ws/audio")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Audio Settings (from JSON)
_AUDIO_DEFAULTS = {
    "sample_rate": 16000,
    "channels": 1,
    "buffer_size": 1048576,
    "chunk_size": 2048,
}
_audio_config = json.loads(os.getenv("AUDIO_CONFIG", json.dumps(_AUDIO_DEFAULTS)))
AUDIO_SAMPLE_RATE = _audio_config.get("sample_rate", 16000)
AUDIO_CHANNELS = _audio_config.get("channels", 1)
AUDIO_BUFFER_SIZE = _audio_config.get("buffer_size", 1048576)
AUDIO_CHUNK_SIZE = _audio_config.get("chunk_size", 2048)

# Connection Settings (from JSON)
_WS_DEFAULTS = {
    "max_retries": 10,
    "initial_retry_delay": 1.0,
    "max_retry_delay": 60.0,
}
_ws_config = json.loads(os.getenv("WS_CONFIG", json.dumps(_WS_DEFAULTS)))
WS_MAX_RETRIES = _ws_config.get("max_retries", 10)
WS_INITIAL_RETRY_DELAY = _ws_config.get("initial_retry_delay", 1.0)
WS_MAX_RETRY_DELAY = _ws_config.get("max_retry_delay", 60.0)

__all__ = [
    "WEBSOCKET_URL",
    "AUDIO_SAMPLE_RATE",
    "AUDIO_CHANNELS",
    "AUDIO_BUFFER_SIZE",
    "AUDIO_CHUNK_SIZE",
    "LOG_LEVEL",
    "WS_MAX_RETRIES",
    "WS_INITIAL_RETRY_DELAY",
    "WS_MAX_RETRY_DELAY",
]
