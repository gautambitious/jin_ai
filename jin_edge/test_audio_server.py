"""
Test WebSocket server that streams audio chunks.
Generates simple tone audio for testing.
"""

import asyncio
import json
import logging
import numpy as np
import websockets
from websockets.asyncio.server import serve


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_tone(frequency: int, duration: float, sample_rate: int = 16000) -> bytes:
    """
    Generate a simple sine wave tone as PCM bytes.

    Args:
        frequency: Tone frequency in Hz
        duration: Duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        Raw PCM bytes (16-bit, mono)
    """
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, False)
    tone = np.sin(2 * np.pi * frequency * t)

    # Convert to 16-bit PCM
    audio_data = (tone * 32767).astype(np.int16)
    return audio_data.tobytes()


async def audio_stream_handler(websocket):
    """
    Handle WebSocket connection and stream audio.

    Args:
        websocket: WebSocket connection
    """
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"Client connected: {client_id}")

    try:
        # Send audio_start message
        stream_id = f"test_stream_{asyncio.get_event_loop().time()}"
        sample_rate = 16000

        start_msg = {
            "type": "audio_start",
            "stream_id": stream_id,
            "sample_rate": sample_rate,
        }
        await websocket.send(json.dumps(start_msg))
        logger.info(f"Sent audio_start: {start_msg}")

        # Wait a bit before sending audio
        await asyncio.sleep(0.5)

        # Generate and send multiple tones
        tones = [
            (440, 1.0),  # A4 for 1 second
            (523, 1.0),  # C5 for 1 second
            (659, 1.0),  # E5 for 1 second
            (784, 1.0),  # G5 for 1 second
        ]

        for frequency, duration in tones:
            logger.info(f"Generating {frequency}Hz tone for {duration}s")
            audio_data = generate_tone(frequency, duration, sample_rate)

            # Send audio in chunks (simulate streaming)
            chunk_size = 4096
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i : i + chunk_size]
                await websocket.send(chunk)
                logger.debug(f"Sent {len(chunk)} bytes")

                # Small delay to simulate streaming
                await asyncio.sleep(0.02)

            # Small gap between tones
            await asyncio.sleep(0.1)

        # Wait before ending
        await asyncio.sleep(0.5)

        # Send audio_end message
        end_msg = {"type": "audio_end", "stream_id": stream_id}
        await websocket.send(json.dumps(end_msg))
        logger.info(f"Sent audio_end: {end_msg}")

        # Keep connection open for a bit
        await asyncio.sleep(2)

    except websockets.ConnectionClosed:
        logger.info(f"Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Error handling client {client_id}: {e}")
    finally:
        logger.info(f"Connection closed: {client_id}")


async def main():
    """Start the WebSocket audio server."""
    host = "localhost"
    port = 8765

    logger.info(f"Starting audio server on ws://{host}:{port}")

    async with serve(audio_stream_handler, host, port):
        logger.info(f"Server ready! Connect client to ws://{host}:{port}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
