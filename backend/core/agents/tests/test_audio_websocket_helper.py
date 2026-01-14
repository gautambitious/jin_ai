"""
Unit tests for AudioWebSocketHelper service.

Tests the audio streaming helper functionality without requiring
actual WebSocket connections or TTS API calls.
"""

import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.services.audio_websocket_helper import (
    AudioWebSocketHelper,
    play_text_on_websocket,
)


class MockWebSocket:
    """Mock WebSocket consumer for testing."""

    def __init__(self):
        self.sent_messages = []
        self.send = AsyncMock(side_effect=self._capture_send)

    async def _capture_send(self, text_data=None, bytes_data=None):
        """Capture sent messages for verification."""
        if text_data:
            self.sent_messages.append(("text", text_data))
        if bytes_data:
            self.sent_messages.append(("bytes", bytes_data))


class TestAudioWebSocketHelper(unittest.TestCase):
    """Test cases for AudioWebSocketHelper."""

    def setUp(self):
        """Set up test fixtures."""
        self.websocket = MockWebSocket()
        self.helper = AudioWebSocketHelper(
            websocket=self.websocket,
            sample_rate=16000,
            channels=1,
        )

    def test_initialization(self):
        """Test helper initialization."""
        self.assertIsNotNone(self.helper)
        self.assertEqual(self.helper.sample_rate, 16000)
        self.assertEqual(self.helper.channels, 1)
        self.assertIsNotNone(self.helper.tts_service)

    def test_stream_audio_buffer_empty(self):
        """Test streaming empty audio buffer."""

        async def run_test():
            await self.helper.stream_audio_buffer(b"")
            # Should not send any messages for empty buffer
            self.assertEqual(len(self.websocket.sent_messages), 0)

        asyncio.run(run_test())

    def test_stream_audio_buffer_with_data(self):
        """Test streaming audio buffer with data."""

        async def run_test():
            # 1 second of audio at 16kHz, 16-bit PCM
            audio_buffer = b"\x00\x00" * 16000

            await self.helper.stream_audio_buffer(
                audio_buffer,
                chunk_duration_ms=20,
            )

            # Should send: audio_start (text) + chunks (bytes) + audio_end (text)
            # Expect at least 3 messages (start, some chunks, end)
            self.assertGreater(len(self.websocket.sent_messages), 3)

            # First message should be text (audio_start)
            self.assertEqual(self.websocket.sent_messages[0][0], "text")

            # Last message should be text (audio_end)
            self.assertEqual(self.websocket.sent_messages[-1][0], "text")

            # Middle messages should be bytes (audio chunks)
            middle_messages = self.websocket.sent_messages[1:-1]
            for msg_type, _ in middle_messages:
                self.assertEqual(msg_type, "bytes")

        asyncio.run(run_test())

    @patch("agents.services.audio_websocket_helper.TTSService")
    def test_text_to_speech_stream_empty_text(self, mock_tts_class):
        """Test text-to-speech with empty text."""

        async def run_test():
            await self.helper.text_to_speech_stream("")

            # Should not send any messages for empty text
            self.assertEqual(len(self.websocket.sent_messages), 0)

        asyncio.run(run_test())

    @patch("agents.services.audio_websocket_helper.TTSService")
    def test_text_to_speech_stream_with_text(self, mock_tts_class):
        """Test text-to-speech streaming with valid text."""

        async def run_test():
            # Mock TTS service to return audio chunks
            mock_tts = MagicMock()
            mock_tts.generate_audio.return_value = [
                b"chunk1",
                b"chunk2",
                b"chunk3",
            ]
            self.helper.tts_service = mock_tts

            await self.helper.text_to_speech_stream("Hello, this is a test.")

            # Should send: audio_start + 3 chunks + audio_end = 5 messages
            self.assertEqual(len(self.websocket.sent_messages), 5)

            # Verify TTS was called
            mock_tts.generate_audio.assert_called_once()

        asyncio.run(run_test())

    def test_stop_playback(self):
        """Test stop playback command."""

        async def run_test():
            await self.helper.stop_playback()

            # Should send one stop message
            self.assertEqual(len(self.websocket.sent_messages), 1)
            self.assertEqual(self.websocket.sent_messages[0][0], "text")

        asyncio.run(run_test())


class TestConvenienceFunction(unittest.TestCase):
    """Test cases for convenience functions."""

    @patch("agents.services.audio_websocket_helper.TTSService")
    def test_play_text_on_websocket(self, mock_tts_class):
        """Test convenience function."""

        async def run_test():
            websocket = MockWebSocket()

            # Mock TTS service
            mock_tts = MagicMock()
            mock_tts.generate_audio.return_value = [b"chunk1", b"chunk2"]
            mock_tts_class.return_value = mock_tts

            await play_text_on_websocket(
                websocket=websocket,
                text="Test message",
            )

            # Should have sent messages
            self.assertGreater(len(websocket.sent_messages), 0)

        asyncio.run(run_test())


class TestChunkCalculations(unittest.TestCase):
    """Test audio chunking calculations."""

    def test_chunk_duration_calculation(self):
        """Test chunk duration matches expected values."""
        # 16kHz, 16-bit PCM, 20ms chunks
        sample_rate = 16000
        chunk_duration_ms = 20
        bytes_per_sample = 2

        samples_per_chunk = int((sample_rate * chunk_duration_ms) / 1000)
        expected_chunk_size = samples_per_chunk * bytes_per_sample

        # 16000 * 0.02 * 2 = 640 bytes
        self.assertEqual(expected_chunk_size, 640)

    def test_total_chunks_calculation(self):
        """Test total number of chunks for audio duration."""
        # 1 second of audio, 20ms chunks
        audio_duration_sec = 1
        chunk_duration_ms = 20

        expected_chunks = (audio_duration_sec * 1000) / chunk_duration_ms

        # 1000ms / 20ms = 50 chunks
        self.assertEqual(expected_chunks, 50)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestAudioWebSocketHelper))
    suite.addTests(loader.loadTestsFromTestCase(TestConvenienceFunction))
    suite.addTests(loader.loadTestsFromTestCase(TestChunkCalculations))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
