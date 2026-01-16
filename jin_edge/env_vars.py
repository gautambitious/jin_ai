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

# Optimized Streaming Configuration
USE_STREAMING_ENDPOINT = os.getenv("USE_STREAMING_ENDPOINT", "false").lower() in (
    "true",
    "1",
    "yes",
)
DEVICE_ID = os.getenv("DEVICE_ID", "edge_device_001")  # Unique device identifier


# Get the appropriate WebSocket URL based on mode
def get_websocket_url():
    if USE_STREAMING_ENDPOINT:
        # Extract base URL and port from WEBSOCKET_URL
        base_url = WEBSOCKET_URL.rsplit("/", 2)[0]  # Remove /ws/audio
        return f"{base_url}/ws/stream/{DEVICE_ID}"
    return WEBSOCKET_URL


# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Push-to-Talk Mode
ENABLE_PUSH_TO_TALK = os.getenv("ENABLE_PUSH_TO_TALK", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Porcupine Wake Word Settings
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")
PORCUPINE_MODEL_PATH = os.getenv(
    "PORCUPINE_MODEL_PATH", os.path.join(BASE_DIR, "Hey-Jin_en_mac_v4_0_0.ppn")
)

# Silence Detection
SILENCE_DURATION_MS = int(
    os.getenv("SILENCE_DURATION_MS", "2000")
)  # Default: 2 seconds

# Listening Timeout - Maximum time to listen after wake word (in seconds)
LISTENING_TIMEOUT_SECONDS = int(
    os.getenv("LISTENING_TIMEOUT_SECONDS", "10")
)  # Default: 10 seconds

# Relative Silence Threshold - Percentage drop from wake word energy level
# If energy drops below this percentage of wake word level, consider it silence
RELATIVE_SILENCE_THRESHOLD = float(
    os.getenv("RELATIVE_SILENCE_THRESHOLD", "0.35")
)  # Default: 35% (i.e., 65% drop)

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

# Audio Device (to avoid PWM conflicts with LEDs on GPIO 18)
# None = default, or specify device index (e.g., 4 for dmix)
AUDIO_DEVICE = os.getenv("AUDIO_DEVICE")
if AUDIO_DEVICE is not None:
    AUDIO_DEVICE = int(AUDIO_DEVICE) if AUDIO_DEVICE.isdigit() else AUDIO_DEVICE

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

# LED Settings (from JSON)
_LED_DEFAULTS = {
    "enabled": True,
    "gpio_pin": 18,
    "num_pixels": 10,
    "brightness": 0.3,
    "pulse_speed": 0.05,
    "spin_speed": 0.1,
}
LED_CONFIG = json.loads(os.getenv("LED_CONFIG", json.dumps(_LED_DEFAULTS)))

# LED Auto-off timeout in seconds (default: 30 seconds)
LED_AUTO_OFF_TIMEOUT = int(os.getenv("LED_AUTO_OFF_TIMEOUT", "30"))

__all__ = [
    "WEBSOCKET_URL",
    "AUDIO_SAMPLE_RATE",
    "AUDIO_CHANNELS",
    "AUDIO_BUFFER_SIZE",
    "AUDIO_CHUNK_SIZE",
    "AUDIO_DEVICE",
    "LOG_LEVEL",
    "WS_MAX_RETRIES",
    "WS_INITIAL_RETRY_DELAY",
    "WS_MAX_RETRY_DELAY",
    "ENABLE_PUSH_TO_TALK",
    "PORCUPINE_ACCESS_KEY",
    "PORCUPINE_MODEL_PATH",
    "SILENCE_DURATION_MS",
    "LISTENING_TIMEOUT_SECONDS",
    "RELATIVE_SILENCE_THRESHOLD",
    "LED_CONFIG",
    "LED_AUTO_OFF_TIMEOUT",
]
