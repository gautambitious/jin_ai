"""
Wake word detector interface and base implementations.

Provides pluggable backend for wake word detection with clean event-based API.
No WebSocket logic - pure audio processing.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WakeWordEvent(Enum):
    """Wake word detection events."""

    DETECTED = "wake_word_detected"


class WakeWordDetector(ABC):
    """
    Abstract base class for wake word detectors.

    Implementations should process audio chunks and emit events
    when the wake word is detected.

    Usage:
        detector = MyWakeWordDetector(
            wake_word="hey jin",
            on_detection=lambda: print("Wake word detected!")
        )

        for chunk in audio_stream:
            detector.process_chunk(chunk)

    Attributes:
        wake_word: The wake word phrase to detect
        on_detection: Callback function when wake word is detected
    """

    def __init__(
        self,
        wake_word: str = "hey jin",
        on_detection: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize wake word detector.

        Args:
            wake_word: The wake word phrase to detect
            on_detection: Callback when wake word is detected
        """
        self.wake_word = wake_word
        self.on_detection = on_detection
        self._is_listening = True

    @abstractmethod
    def process_chunk(self, pcm_bytes: bytes) -> Optional[WakeWordEvent]:
        """
        Process audio chunk and detect wake word.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            WakeWordEvent.DETECTED if wake word found, None otherwise
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset detector state."""
        pass

    def start_listening(self) -> None:
        """Enable wake word detection."""
        self._is_listening = True
        logger.info("Wake word detection started")

    def stop_listening(self) -> None:
        """Disable wake word detection."""
        self._is_listening = False
        logger.info("Wake word detection stopped")

    @property
    def is_listening(self) -> bool:
        """Check if detector is actively listening."""
        return self._is_listening

    def _trigger_detection(self) -> WakeWordEvent:
        """
        Internal method to trigger detection event.

        Returns:
            WakeWordEvent.DETECTED
        """
        logger.info(f"Wake word detected: '{self.wake_word}'")
        if self.on_detection:
            self.on_detection()
        return WakeWordEvent.DETECTED


class StubWakeWordDetector(WakeWordDetector):
    """
    Stub implementation for testing.

    Detects wake word based on simple RMS threshold crossing.
    Not accurate - for development/testing only.
    """

    def __init__(
        self,
        wake_word: str = "hey jin",
        on_detection: Optional[Callable[[], None]] = None,
        detection_threshold: float = 2000.0,
        cooldown_chunks: int = 100,
    ):
        """
        Initialize stub wake word detector.

        Args:
            wake_word: The wake word phrase (ignored in stub)
            on_detection: Callback when wake word is detected
            detection_threshold: RMS threshold for fake detection
            cooldown_chunks: Chunks to wait before allowing another detection
        """
        super().__init__(wake_word, on_detection)
        self.detection_threshold = detection_threshold
        self.cooldown_chunks = cooldown_chunks
        self._cooldown_counter = 0

    def process_chunk(self, pcm_bytes: bytes) -> Optional[WakeWordEvent]:
        """
        Process audio chunk with stub detection logic.

        Args:
            pcm_bytes: Raw PCM audio bytes

        Returns:
            WakeWordEvent.DETECTED if threshold exceeded, None otherwise
        """
        if not self._is_listening:
            return None

        if not pcm_bytes or len(pcm_bytes) < 2:
            return None

        # Count down cooldown
        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1
            return None

        # Calculate RMS
        rms = self._calculate_rms(pcm_bytes)

        # Simple threshold detection
        if rms > self.detection_threshold:
            self._cooldown_counter = self.cooldown_chunks
            return self._trigger_detection()

        return None

    def _calculate_rms(self, pcm_bytes: bytes) -> float:
        """
        Calculate RMS energy of PCM audio.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            RMS energy value
        """
        import struct

        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return 0.0

        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)
        sum_squares = sum(sample * sample for sample in samples)
        mean_square = sum_squares / num_samples
        rms = mean_square**0.5

        return rms

    def reset(self) -> None:
        """Reset detector state."""
        self._cooldown_counter = 0
        logger.debug("Stub detector reset")


class PassthroughDetector(WakeWordDetector):
    """
    Passthrough detector that never detects wake word.

    Useful for testing or when wake word detection is disabled.
    """

    def process_chunk(self, pcm_bytes: bytes) -> Optional[WakeWordEvent]:
        """Process chunk without detection."""
        return None

    def reset(self) -> None:
        """Reset detector state (no-op)."""
        pass


def create_detector(
    backend: str = "stub",
    wake_word: str = "hey jin",
    on_detection: Optional[Callable[[], None]] = None,
    **kwargs,
) -> WakeWordDetector:
    """
    Factory function to create wake word detector.

    Args:
        backend: Detector backend ("stub", "passthrough", or custom)
        wake_word: The wake word phrase to detect
        on_detection: Callback when wake word is detected
        **kwargs: Additional backend-specific arguments

    Returns:
        WakeWordDetector instance

    Example:
        detector = create_detector(
            backend="stub",
            wake_word="hey jin",
            on_detection=handle_wake_word,
            detection_threshold=2000
        )
    """
    if backend == "stub":
        return StubWakeWordDetector(wake_word, on_detection, **kwargs)
    elif backend == "passthrough":
        return PassthroughDetector(wake_word, on_detection)
    else:
        raise ValueError(f"Unknown wake word detector backend: {backend}")


def main():
    """Example usage of wake word detector."""
    import struct
    import time

    def on_wake_word():
        print("🎤 WAKE WORD DETECTED!")

    # Create detector
    detector = create_detector(
        backend="stub",
        wake_word="hey jin",
        on_detection=on_wake_word,
        detection_threshold=2000,
        cooldown_chunks=100,
    )

    print("Wake Word Detector Test")
    print(f"Wake word: '{detector.wake_word}'")
    print(f"Backend: StubWakeWordDetector")
    print("Press Ctrl+C to stop\n")

    # Simulate audio chunks
    silent_chunk = b"\x00\x00" * 480  # 30ms at 16kHz
    loud_samples = [3000] * 480
    loud_chunk = struct.pack(f"<{len(loud_samples)}h", *loud_samples)

    try:
        chunk_count = 0
        while True:
            # Alternate between silence and loud bursts
            if chunk_count % 150 < 10:  # Every ~4.5s, send 10 loud chunks
                chunk = loud_chunk
                level = "LOUD"
            else:
                chunk = silent_chunk
                level = "quiet"

            # Process chunk
            event = detector.process_chunk(chunk)

            # Log
            if event or chunk_count % 50 == 0:
                status = "🎧 Listening" if detector.is_listening else "💤 Paused"
                print(f"[{chunk_count:04d}] {status} | Level: {level:5s}", end="")
                if event:
                    print(f" | ⚡ {event.value}")
                else:
                    print()

            chunk_count += 1
            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n\n✅ Stopped by user")
        print(f"Processed {chunk_count} chunks")


if __name__ == "__main__":
    main()
