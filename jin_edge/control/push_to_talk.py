"""
Push-to-talk controller for microphone streaming.

Captures keyboard input to start/stop mic streaming over WebSocket.
Sends audio chunks and control messages without blocking mic capture.
"""

import asyncio
import json
import logging
from typing import Optional, TYPE_CHECKING
from audio.mic_stream import MicStream
from ws.client import WebSocketClient

if TYPE_CHECKING:
    from led.controller import LEDController

try:
    import aioconsole

    HAS_AIOCONSOLE = True
except ImportError:
    HAS_AIOCONSOLE = False

logger = logging.getLogger(__name__)


class PushToTalkController:
    """
    Push-to-talk controller for streaming microphone audio.

    Usage:
        ptt = PushToTalkController(
            ws_client=client,
            mic_stream=mic,
            trigger_key="Enter"
        )
        await ptt.start()
        # Press Enter to start streaming, Enter again to stop
        await ptt.stop()

    Features:
        - Non-blocking keyboard input
        - Sends audio_input_start/audio_input_end control messages
        - Streams audio chunks over existing WebSocket
        - Clean async design, no blocking of mic capture
    """

    def __init__(
        self,
        ws_client: WebSocketClient,
        mic_stream: Optional[MicStream] = None,
        trigger_key: str = "Enter",
        sample_rate: int = 16000,
        channels: int = 1,
        led_controller: Optional["LEDController"] = None,
    ):
        """
        Initialize push-to-talk controller.

        Args:
            ws_client: WebSocketClient instance for sending audio/messages
            mic_stream: Optional MicStream instance (creates one if None)
            trigger_key: Key description for user instructions (default: "Enter")
            sample_rate: Audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            led_controller: Optional LED controller for visual feedback
        """
        self.ws_client = ws_client
        self.mic_stream = mic_stream or MicStream(
            sample_rate=sample_rate, channels=channels
        )
        self.trigger_key = trigger_key
        self.sample_rate = sample_rate
        self.channels = channels
        self.led_controller = led_controller

        self._is_streaming = False
        self._is_running = False
        self._stream_task: Optional[asyncio.Task] = None
        self._input_task: Optional[asyncio.Task] = None

    async def start(self):
        """
        Start the push-to-talk controller.
        Begins listening for keyboard input.
        """
        if self._is_running:
            logger.warning("Controller already running")
            return

        if not HAS_AIOCONSOLE:
            logger.error(
                "aioconsole not installed. Install with: pip install aioconsole"
            )
            raise RuntimeError("aioconsole required for async keyboard input")

        self._is_running = True

        logger.info(
            f"Push-to-talk ready. Press {self.trigger_key} to start/stop streaming."
        )
        print(f"\n[Push-to-Talk] Press {self.trigger_key} to start/stop recording\n")

        # Start keyboard input listener
        self._input_task = asyncio.create_task(self._input_loop())

    async def stop(self):
        """Stop the push-to-talk controller and cleanup."""
        self._is_running = False

        # Stop streaming if active
        if self._is_streaming:
            await self._stop_streaming()

        # Cancel input listener
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass
            self._input_task = None

        logger.info("Push-to-talk controller stopped")

    async def _input_loop(self):
        """
        Async keyboard input loop.
        Toggles streaming on each trigger key press.
        """
        try:
            while self._is_running:
                # Wait for Enter key (non-blocking)
                line = await aioconsole.ainput()

                if not self._is_running:
                    break

                # Toggle streaming state
                if self._is_streaming:
                    await self._stop_streaming()
                else:
                    await self._start_streaming()

        except asyncio.CancelledError:
            logger.debug("Input loop cancelled")
        except Exception as e:
            logger.error(f"Input loop error: {e}")

    async def _start_streaming(self):
        """Start streaming microphone audio over WebSocket."""
        if self._is_streaming:
            logger.warning("Already streaming")
            return

        try:
            # Send audio_input_start control message
            control_msg = json.dumps(
                {
                    "type": "audio_input_start",
                    "sample_rate": self.sample_rate,
                    "channels": self.channels,
                    "format": "pcm_s16le",
                }
            )
            await self.ws_client.send_text(control_msg)
            logger.info("Sent audio_input_start message")

            # Start streaming task
            self._is_streaming = True
            self._stream_task = asyncio.create_task(self._stream_audio())
            
            # Set LED to listening state
            if self.led_controller:
                await self.led_controller.set_listening()

            print("[Push-to-Talk] 🔴 Recording... Press Enter to stop\n")

        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self._is_streaming = False

    async def _stop_streaming(self):
        """Stop streaming microphone audio."""
        if not self._is_streaming:
            logger.warning("Not streaming")
            return

        try:
            # Stop streaming flag first
            self._is_streaming = False

            # Wait for stream task to complete
            if self._stream_task:
                await self._stream_task
                self._stream_task = None

            # Send audio_input_end control message
            control_msg = json.dumps({"type": "audio_input_end"})
            await self.ws_client.send_text(control_msg)
            logger.info("Sent audio_input_end message")
            
            # Turn off LED
            if self.led_controller:
                await self.led_controller.set_off()

            print("[Push-to-Talk] ⏹️  Recording stopped. Press Enter to start\n")

        except Exception as e:
            logger.error(f"Failed to stop streaming: {e}")

    async def _stream_audio(self):
        """
        Stream audio chunks from mic to WebSocket.
        Runs in background task, doesn't block input loop.
        """
        try:
            # Run mic capture in executor to avoid blocking
            loop = asyncio.get_event_loop()

            for chunk in self.mic_stream.stream():
                if not self._is_streaming:
                    # Stop signal received
                    self.mic_stream.stop()
                    break

                # Send audio chunk over WebSocket
                try:
                    await self.ws_client.send_binary(chunk)
                except Exception as e:
                    logger.error(f"Failed to send audio chunk: {e}")
                    break

                # Yield control to event loop (important for async)
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
            self._is_streaming = False
        finally:
            logger.debug("Audio streaming task completed")


async def main():
    """
    Example usage of PushToTalkController.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create WebSocket client
    ws_url = "ws://localhost:8000/ws"  # Replace with actual server URL
    ws_client = WebSocketClient(url=ws_url)

    # Connect to server
    await ws_client.connect()
    await asyncio.sleep(1)  # Wait for connection

    # Create and start push-to-talk controller
    ptt = PushToTalkController(ws_client=ws_client)

    try:
        await ptt.start()

        # Run indefinitely (until Ctrl+C)
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await ptt.stop()
        await ws_client.close()


if __name__ == "__main__":
    asyncio.run(main())
