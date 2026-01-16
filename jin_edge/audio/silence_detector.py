"""
Lightweight silence detector for PCM audio.
Detects speech start/end based on RMS energy level.
"""

import logging
import struct
from typing import Callable, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SpeechEvent(Enum):
    """Speech detection events."""

    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"


class SilenceDetector:
    """
    Detect silence in PCM audio streams using RMS energy.

    Usage:
        detector = SilenceDetector(
            sample_rate=16000,
            silence_threshold=500,
            silence_duration_ms=800,
            on_speech_start=lambda: print("Speaking..."),
            on_speech_end=lambda: print("Silence detected")
        )

        for chunk in audio_stream:
            event = detector.process(chunk)
            if event:
                print(f"Event: {event}")

    Features:
        - RMS energy calculation
        - Configurable silence threshold
        - Sustained silence detection (prevents flapping)
        - No external dependencies (uses only struct)
        - Lightweight for Raspberry Pi
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        silence_threshold: float = 500.0,
        silence_duration_ms: int = 800,
        speech_threshold: Optional[float] = None,
        chunk_duration_ms: int = 30,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
        use_relative_threshold: bool = False,
        relative_threshold_ratio: float = 0.35,
    ):
        """
        Initialize silence detector.

        Args:
            sample_rate: Audio sample rate in Hz (default: 16000)
            silence_threshold: RMS threshold below which audio is silence (default: 500)
            silence_duration_ms: Milliseconds of silence needed to trigger event (default: 800)
            speech_threshold: RMS threshold above which audio is speech (default: silence_threshold * 1.2)
            chunk_duration_ms: Expected chunk duration in ms (default: 30)
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends
            use_relative_threshold: Use relative energy threshold instead of absolute (default: False)
            relative_threshold_ratio: When using relative threshold, the ratio of baseline energy
                                     below which audio is considered silence (default: 0.35 = 35%)
        """
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.speech_threshold = speech_threshold or (silence_threshold * 1.2)
        self.chunk_duration_ms = chunk_duration_ms

        # Calculate number of chunks needed for silence duration
        self.silence_chunks_needed = max(
            1, int(silence_duration_ms / chunk_duration_ms)
        )

        self._is_speaking = False
        self._silence_chunk_count = 0
        self._speech_chunk_count = 0

        # Relative threshold mode
        self.use_relative_threshold = use_relative_threshold
        self.relative_threshold_ratio = relative_threshold_ratio
        self._baseline_energy: Optional[float] = None
        self._relative_silence_threshold: Optional[float] = None

        # Callbacks
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

    def set_baseline_energy(self, energy: float):
        """
        Set the baseline energy level for relative threshold detection.
        Call this after wake word is detected to establish the reference level.

        Args:
            energy: The baseline RMS energy level
        """
        self._baseline_energy = energy
        if self.use_relative_threshold and energy > 0:
            self._relative_silence_threshold = energy * self.relative_threshold_ratio
            logger.debug(
                f"Set baseline energy: {energy:.1f}, "
                f"relative silence threshold: {self._relative_silence_threshold:.1f}"
            )

    def process(self, pcm_bytes: bytes) -> Optional[SpeechEvent]:
        """
        Process audio chunk and detect silence/speech.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            SpeechEvent if state changed, None otherwise
        """
        if not pcm_bytes or len(pcm_bytes) < 2:
            return None

        # Calculate RMS energy
        rms = self._calculate_rms(pcm_bytes)

        # Determine which threshold to use
        if self.use_relative_threshold and self._relative_silence_threshold is not None:
            silence_threshold = self._relative_silence_threshold
            speech_threshold = self._relative_silence_threshold * 1.2
        else:
            silence_threshold = self.silence_threshold
            speech_threshold = self.speech_threshold

        # Update state based on RMS
        if rms < silence_threshold:
            # Audio is silent
            self._silence_chunk_count += 1
            self._speech_chunk_count = 0

            # Check if we've had enough sustained silence
            if (
                self._is_speaking
                and self._silence_chunk_count >= self.silence_chunks_needed
            ):
                self._is_speaking = False
                if self.on_speech_end:
                    self.on_speech_end()
                return SpeechEvent.SPEECH_ENDED

        elif rms > speech_threshold:
            # Audio has speech
            self._speech_chunk_count += 1
            self._silence_chunk_count = 0

            # Trigger speech start immediately
            if not self._is_speaking:
                self._is_speaking = True
                if self.on_speech_start:
                    self.on_speech_start()
                return SpeechEvent.SPEECH_STARTED

        return None

    def _calculate_rms(self, pcm_bytes: bytes) -> float:
        """
        Calculate RMS (Root Mean Square) energy of PCM audio.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            RMS energy value
        """
        # Unpack 16-bit signed integers
        num_samples = len(pcm_bytes) // 2

        if num_samples == 0:
            return 0.0

        # Use struct to unpack bytes to integers
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)

        # Calculate RMS: sqrt(mean(x^2))
        sum_squares = sum(sample * sample for sample in samples)
        mean_square = sum_squares / num_samples
        rms = mean_square**0.5

        return rms

    def calculate_peak(self, pcm_bytes: bytes) -> int:
        """
        Calculate peak amplitude of PCM audio.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            Peak amplitude (absolute max value)
        """
        num_samples = len(pcm_bytes) // 2

        if num_samples == 0:
            return 0

        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)
        return max(abs(sample) for sample in samples)

    def reset(self):
        """Reset detector state."""
        self._is_speaking = False
        self._silence_chunk_count = 0
        self._speech_chunk_count = 0
        # Don't reset baseline energy - it should persist across sessions
        # unless explicitly cleared with clear_baseline()

    def clear_baseline(self):
        """Clear the baseline energy level."""
        self._baseline_energy = None
        self._relative_silence_threshold = None

    @property
    def is_speaking(self) -> bool:
        """Check if currently detecting speech."""
        return self._is_speaking

    @property
    def silence_duration_ms(self) -> float:
        """Get current silence duration in milliseconds."""
        return self._silence_chunk_count * self.chunk_duration_ms

    @property
    def speech_duration_ms(self) -> float:
        """Get current speech duration in milliseconds."""
        return self._speech_chunk_count * self.chunk_duration_ms


def main():
    """Example usage of SilenceDetector with live mic input."""
    import time
    import random

    def on_start():
        print("🗣️  Speech started!")

    def on_end():
        print("🤐 Speech ended (silence detected)")

    # Create detector
    detector = SilenceDetector(
        sample_rate=16000,
        silence_threshold=500,
        silence_duration_ms=800,
        on_speech_start=on_start,
        on_speech_end=on_end,
    )

    print("Silence Detector - Continuous Mode")
    print("Threshold: 500 | Silence duration: 800ms")
    print("Press Ctrl+C to stop\n")

    # Simulate some audio chunks
    # Silent chunk (all zeros)
    silent_chunk = b"\x00\x00" * 480  # 30ms at 16kHz

    # Loud chunk (simulate speech)
    loud_samples = [1000] * 480
    loud_chunk = struct.pack(f"<{len(loud_samples)}h", *loud_samples)

    # Medium chunk (background noise)
    medium_samples = [300] * 480
    medium_chunk = struct.pack(f"<{len(medium_samples)}h", *medium_samples)

    try:
        chunk_count = 0
        while True:
            # Simulate varying audio levels
            # Randomly switch between silence and speech
            rand = random.random()
            if rand < 0.3:
                # 30% silence
                chunk = silent_chunk
                level = "silent"
            elif rand < 0.6:
                # 30% medium (below threshold)
                chunk = medium_chunk
                level = "quiet"
            else:
                # 40% loud (speech)
                chunk = loud_chunk
                level = "loud"

            # Process chunk
            event = detector.process(chunk)

            # Log every 10 chunks or on events
            if event or chunk_count % 10 == 0:
                rms = detector._calculate_rms(chunk)
                status = "🗣️  SPEAKING" if detector.is_speaking else "🤐 SILENT"
                print(
                    f"[{chunk_count:04d}] {status} | RMS: {rms:6.1f} | Level: {level:6s}",
                    end="",
                )
                if event:
                    print(f" | ⚡ Event: {event.value}")
                else:
                    print()

            chunk_count += 1
            time.sleep(0.03)  # 30ms chunks

    except KeyboardInterrupt:
        print("\n\n✅ Stopped by user")
        print(f"Processed {chunk_count} chunks ({chunk_count * 30}ms of audio)")


if __name__ == "__main__":
    main()
