"""
Main entry point for Jin Edge audio client.
Connects to backend WebSocket server and plays audio.

Modes:
- Default: Receive and play audio from server
- Push-to-talk (--ptt): Manual recording with Enter key
- Wake word (--wakeword): Hands-free voice activation
"""

import asyncio
import logging
import signal
import sys
from audio.buffer import AudioBuffer
from audio.player import AudioPlayer
from protocol.audio import AudioStreamHandler
from ws.client import WebSocketClient
from control.push_to_talk import PushToTalkController
from control.wakeword_streamer import WakeWordStreamer
from led.controller import LEDController
import env_vars


# Configure logging
logging.basicConfig(
    level=getattr(logging, env_vars.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class JinEdgeClient:
    """
    Main orchestrator for Jin Edge audio client.

    Manages WebSocket connection, audio playback, and input modes.
    """

    def __init__(
        self, enable_push_to_talk: bool = False, enable_wakeword: bool = False
    ):
        # LED Controller
        self.led_controller = LEDController()
        
        self.audio_player = AudioPlayer(
            sample_rate=env_vars.AUDIO_SAMPLE_RATE,
            channels=env_vars.AUDIO_CHANNELS,
            buffer_size=env_vars.AUDIO_BUFFER_SIZE,
            chunk_size=env_vars.AUDIO_CHUNK_SIZE,
            device=env_vars.AUDIO_DEVICE,
        )
        # Use the player's internal buffer directly
        self.protocol_handler = AudioStreamHandler(
            self.audio_player._buffer, self.audio_player, self.led_controller
        )
        self.ws_client: WebSocketClient | None = None
        self.push_to_talk: PushToTalkController | None = None
        self.wakeword_streamer: WakeWordStreamer | None = None
        self.enable_push_to_talk = enable_push_to_talk
        self.enable_wakeword = enable_wakeword
        self.running = False

        # Validate mode selection
        if enable_push_to_talk and enable_wakeword:
            raise ValueError("Cannot enable both push-to-talk and wake word modes")

    def on_connect(self):
        """Called when WebSocket connection is established."""
        logger.info("✅ Connected to backend server")

    def on_disconnect(self):
        """Called when WebSocket connection is lost."""
        logger.warning("❌ Disconnected from backend server")

    async def start(self):
        """Start the audio client."""
        logger.info("🚀 Starting Jin Edge audio client...")

        # Start audio player
        logger.info("🔊 Initializing audio player...")
        await self.audio_player.start()

        # Create WebSocket client with protocol handler
        self.ws_client = WebSocketClient(
            url=env_vars.WEBSOCKET_URL,
            protocol_handler=self.protocol_handler,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            max_retries=env_vars.WS_MAX_RETRIES,
            initial_retry_delay=env_vars.WS_INITIAL_RETRY_DELAY,
            max_retry_delay=env_vars.WS_MAX_RETRY_DELAY,
        )

        # Connect to WebSocket server
        logger.info(f"🔌 Connecting to {env_vars.WEBSOCKET_URL}...")
        await self.ws_client.connect()

        # Start input mode if enabled
        if self.enable_push_to_talk:
            logger.info("🎤 Enabling push-to-talk mode (Press Enter to record)...")
            self.push_to_talk = PushToTalkController(
                ws_client=self.ws_client,
                sample_rate=env_vars.AUDIO_SAMPLE_RATE,
                channels=env_vars.AUDIO_CHANNELS,
                led_controller=self.led_controller,
            )
            await self.push_to_talk.start()
        elif self.enable_wakeword:
            logger.info("🎤 Enabling wake word mode (Say 'hey jin')...")
            self.wakeword_streamer = WakeWordStreamer(
                ws_client=self.ws_client,
                wake_word="hey jin",
                sample_rate=env_vars.AUDIO_SAMPLE_RATE,
                channels=env_vars.AUDIO_CHANNELS,
                silence_threshold=500,
                led_controller=self.led_controller,
                # silence_duration_ms uses env_vars.SILENCE_DURATION_MS (default 3000ms)
            )
            await self.wakeword_streamer.start()

        # Keep running until stopped
        mode_str = (
            "push-to-talk"
            if self.enable_push_to_talk
            else "wake word" if self.enable_wakeword else "playback only"
        )
        logger.info(f"🎵 Audio client running in {mode_str} mode...")
        self.running = True
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")

    async def stop(self):
        """Stop the audio client and cleanup all components."""
        logger.info("🛑 Stopping Jin Edge audio client...")
        self.running = False

        # Stop input controllers
        if self.push_to_talk:
            await self.push_to_talk.stop()

        if self.wakeword_streamer:
            await self.wakeword_streamer.stop()

        # Close WebSocket connection
        if self.ws_client:
            await self.ws_client.close()

        # Stop audio player
        await self.audio_player.stop()
        
        # Turn off LEDs
        await self.led_controller.off()

        logger.info("✅ Stopped")


async def main():
    """Main entry point with mode selection."""
    # Parse command line arguments (flags override environment variables)
    has_ptt_flag = "--ptt" in sys.argv or "-p" in sys.argv
    has_wakeword_flag = "--wakeword" in sys.argv or "-w" in sys.argv

    # Determine modes: CLI flags take precedence over env vars
    if has_ptt_flag or has_wakeword_flag:
        enable_ptt = has_ptt_flag
        enable_wakeword = has_wakeword_flag
    else:
        # No CLI flags, use environment variable
        enable_ptt = env_vars.ENABLE_PUSH_TO_TALK
        enable_wakeword = False

    # Create client with selected mode
    try:
        client = JinEdgeClient(
            enable_push_to_talk=enable_ptt, enable_wakeword=enable_wakeword
        )
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("⚠️  Received shutdown signal")
        asyncio.create_task(client.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("⚠️  Keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        await client.stop()


if __name__ == "__main__":
    logger.info("🎯 Jin Edge - Audio Client for Raspberry Pi")
    logger.info("Modes: Default | --ptt (push-to-talk) | --wakeword (voice activation)")
    asyncio.run(main())
