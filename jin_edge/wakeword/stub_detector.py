"""
Stub wake word detector using RMS energy threshold.

Temporary placeholder for real ML-based wake word detection.
Maintains interface compatibility for future implementation.
"""

import struct
import logging
from typing import Callable, Optional

try:
    from wakeword.base import WakeWordDetector, WakeWordEvent
except ImportError:
    from base import WakeWordDetector, WakeWordEvent

logger = logging.getLogger(__name__)


class StubWakeWordDetector(WakeWordDetector):
    """
    Stub wake word detector using simple RMS energy threshold.

    This is a temporary placeholder that triggers on loud audio.
    NOT ACCURATE - should be replaced with proper ML-based detector
    (e.g., Porcupine, Picovoice, or custom model).

    Maintains the same interface so it can be swapped out easily.

    Usage:
        detector = StubWakeWordDetector(
            wake_word="hey jin",
            on_detection=handle_wake_word,
            detection_threshold=2000,  # Adjust based on mic sensitivity
            cooldown_ms=3000  # 3 second cooldown between detections
        )

        for chunk in mic_stream:
            event = detector.process_chunk(chunk)
            if event:
                # Wake word detected - start recording
                pass

    Features:
        - RMS energy calculation
        - Configurable threshold
        - Cooldown period to prevent rapid re-triggering
        - Compatible with future ML-based detector interface
    """

    def __init__(
        self,
        wake_word: str = "hey jin",
        on_detection: Optional[Callable[[], None]] = None,
        detection_threshold: float = 2500.0,
        sustained_duration_ms: int = 100,
        cooldown_ms: int = 3000,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
    ):
        """
        Initialize stub wake word detector.

        Args:
            wake_word: The wake word phrase (not used in stub, for interface compat)
            on_detection: Callback when wake word is detected
            detection_threshold: RMS energy threshold for detection (default: 2500, adjust for your mic)
            sustained_duration_ms: Milliseconds of sustained loud audio needed to trigger (default: 100)
            cooldown_ms: Milliseconds to wait before allowing another detection (default: 3000)
            sample_rate: Audio sample rate in Hz
            chunk_duration_ms: Expected chunk duration in milliseconds
        """
        super().__init__(wake_word, on_detection)
        self.detection_threshold = detection_threshold
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms

        # Sustained detection - require multiple consecutive chunks above threshold
        self.sustained_chunks_needed = max(
            1, int(sustained_duration_ms / chunk_duration_ms)
        )
        self._sustained_counter = 0

        # Calculate cooldown in chunks
        self.cooldown_chunks = max(1, int(cooldown_ms / chunk_duration_ms))
        self._cooldown_counter = 0

        logger.info(
            f"Stub wake word detector initialized "
            f"(threshold={detection_threshold}, sustained={sustained_duration_ms}ms, cooldown={cooldown_ms}ms)"
        )

    def process_chunk(self, pcm_bytes: bytes) -> Optional[WakeWordEvent]:
        """
        Process audio chunk and detect wake word based on sustained RMS threshold.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int, mono)

        Returns:
            WakeWordEvent.DETECTED if sustained threshold exceeded, None otherwise
        """
        if not self._is_listening:
            return None

        if not pcm_bytes or len(pcm_bytes) < 2:
            return None

        # Handle cooldown period
        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1
            self._sustained_counter = 0  # Reset sustained counter during cooldown
            return None

        # Calculate RMS energy
        rms = self._calculate_rms(pcm_bytes)

        # Sustained detection - require multiple consecutive chunks above threshold
        if rms > self.detection_threshold:
            self._sustained_counter += 1
            logger.debug(
                f"Above threshold: RMS={rms:.1f}, counter={self._sustained_counter}/{self.sustained_chunks_needed}"
            )

            # Check if we've sustained the threshold long enough
            if self._sustained_counter >= self.sustained_chunks_needed:
                logger.debug(
                    f"Wake word detected: RMS={rms:.1f}, "
                    f"sustained for {self._sustained_counter} chunks"
                )
                self._cooldown_counter = self.cooldown_chunks
                self._sustained_counter = 0
                return self._trigger_detection()
        else:
            # Reset counter if we drop below threshold
            if self._sustained_counter > 0:
                logger.debug(
                    f"Below threshold: RMS={rms:.1f}, resetting counter from {self._sustained_counter}"
                )
            self._sustained_counter = 0

        return None

    def _calculate_rms(self, pcm_bytes: bytes) -> float:
        """
        Calculate RMS (Root Mean Square) energy of PCM audio.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            RMS energy value
        """
        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return 0.0

        # Unpack 16-bit signed integers
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)

        # Calculate RMS: sqrt(mean(x^2))
        sum_squares = sum(sample * sample for sample in samples)
        mean_square = sum_squares / num_samples
        rms = mean_square**0.5

        return rms

    def reset(self) -> None:
        """Reset detector state."""
        self._cooldown_counter = 0
        self._sustained_counter = 0
        logger.debug("Stub detector state reset")

    def set_threshold(self, threshold: float) -> None:
        """
        Update detection threshold dynamically.

        Args:
            threshold: New RMS threshold value
        """
        old_threshold = self.detection_threshold
        self.detection_threshold = threshold
        logger.info(f"Detection threshold updated: {old_threshold} -> {threshold}")

    @property
    def cooldown_active(self) -> bool:
        """Check if detector is in cooldown period."""
        return self._cooldown_counter > 0

    @property
    def cooldown_remaining_ms(self) -> float:
        """Get remaining cooldown time in milliseconds."""
        return self._cooldown_counter * self.chunk_duration_ms


def main():
    """Test stub wake word detector with simulated audio."""
    import time
    import random

    def on_wake_word():
        print("\n🎤 ⚡ WAKE WORD DETECTED! ⚡\n")

    # Create detector
    detector = StubWakeWordDetector(
        wake_word="Hey Jin",
        on_detection=on_wake_word,
        detection_threshold=1200,
        sustained_duration_ms=100,
        cooldown_ms=3000,
    )

    print("Stub Wake Word Detector Test")
    print(f"Wake word: '{detector.wake_word}'")
    print(f"Threshold: {detector.detection_threshold}")
    print(f"Sustained: 100ms ({detector.sustained_chunks_needed} chunks)")
    print(f"Cooldown: 3000ms")
    print("Press Ctrl+C to stop\n")
    print(f"Cooldown: 3000ms")
    print("Press Ctrl+C to stop\n")

    # Create audio chunks
    silent_chunk = b"\x00\x00" * 480  # 30ms at 16kHz

    # Different intensity levels
    quiet_samples = [800] * 480
    quiet_chunk = struct.pack(f"<{len(quiet_samples)}h", *quiet_samples)

    medium_samples = [1500] * 480
    medium_chunk = struct.pack(f"<{len(medium_samples)}h", *medium_samples)

    loud_samples = [3000] * 480
    loud_chunk = struct.pack(f"<{len(loud_samples)}h", *loud_samples)

    try:
        chunk_count = 0
        while True:
            # Simulate varying audio levels
            rand = random.random()
            if rand < 0.7:
                # 70% silence or quiet
                chunk = silent_chunk if rand < 0.5 else quiet_chunk
                level = "silent" if rand < 0.5 else "quiet"
            elif rand < 0.9:
                # 20% medium
                chunk = medium_chunk
                level = "medium"
            else:
                # 10% loud (triggers detection)
                chunk = loud_chunk
                level = "LOUD"

            # Process chunk
            event = detector.process_chunk(chunk)

            # Log status periodically
            if chunk_count % 33 == 0 or event:  # ~1 second intervals
                rms = detector._calculate_rms(chunk)
                status = "🎧 Listening" if detector.is_listening else "💤 Paused"
                cooldown = ""
                if detector.cooldown_active:
                    cooldown = f" | Cooldown: {detector.cooldown_remaining_ms:.0f}ms"

                print(
                    f"[{chunk_count:04d}] {status} | RMS: {rms:6.1f} | "
                    f"Level: {level:6s}{cooldown}"
                )

            chunk_count += 1
            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n\n✅ Stopped by user")
        print(f"Processed {chunk_count} chunks ({chunk_count * 30}ms of audio)")


if __name__ == "__main__":
    main()
