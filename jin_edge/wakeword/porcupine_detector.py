"""
Porcupine wake word detector implementation.

Uses Picovoice's Porcupine for accurate wake word detection.
Low CPU, optimized for Raspberry Pi.
"""

import struct
import logging
from typing import Callable, Optional
import os

try:
    import pvporcupine

    HAS_PORCUPINE = True
except ImportError:
    HAS_PORCUPINE = False

try:
    from wakeword.base import WakeWordDetector, WakeWordEvent
except ImportError:
    from base import WakeWordDetector, WakeWordEvent

logger = logging.getLogger(__name__)


class PorcupineDetector(WakeWordDetector):
    """
    Porcupine-based wake word detector.

    Accurate, low-CPU wake word detection using ML model.
    Requires Porcupine access key and .ppn model file.

    Usage:
        detector = PorcupineDetector(
            access_key="your-access-key",
            model_path="/path/to/model.ppn",
            on_detection=handle_wake_word
        )

        for chunk in mic_stream:
            event = detector.process_chunk(chunk)
            if event:
                # Wake word detected
                pass

    Features:
        - High accuracy ML-based detection
        - Low CPU usage (optimized for Pi)
        - Custom wake word models (.ppn files)
        - No false positives from RMS threshold
    """

    def __init__(
        self,
        access_key: str,
        model_path: str,
        wake_word: str = "hey jin",
        on_detection: Optional[Callable[[], None]] = None,
        sensitivity: float = 0.5,
    ):
        """
        Initialize Porcupine wake word detector.

        Args:
            access_key: Porcupine access key from Picovoice Console
            model_path: Path to .ppn model file
            wake_word: Wake word phrase (for display only)
            on_detection: Callback when wake word is detected
            sensitivity: Detection sensitivity 0.0-1.0 (default: 0.5)
        """
        super().__init__(wake_word, on_detection)

        if not HAS_PORCUPINE:
            raise RuntimeError(
                "pvporcupine not installed. Install with: pip install pvporcupine"
            )

        if not access_key:
            raise ValueError("Porcupine access key required")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.access_key = access_key
        self.model_path = model_path
        self.sensitivity = sensitivity

        # Initialize Porcupine
        try:
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[model_path],
                sensitivities=[sensitivity],
            )
            logger.info(
                f"Porcupine detector initialized "
                f"(model={os.path.basename(model_path)}, "
                f"sensitivity={sensitivity}, "
                f"sample_rate={self._porcupine.sample_rate}, "
                f"frame_length={self._porcupine.frame_length})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Porcupine: {e}")
            raise

        # Audio buffer for accumulating samples
        self._audio_buffer = []
        self._samples_needed = self._porcupine.frame_length

    def process_chunk(self, pcm_bytes: bytes) -> Optional[WakeWordEvent]:
        """
        Process audio chunk and detect wake word.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit signed int)

        Returns:
            WakeWordEvent.DETECTED if wake word found, None otherwise
        """
        if not self._is_listening:
            return None

        if not pcm_bytes or len(pcm_bytes) < 2:
            return None

        # Convert bytes to 16-bit samples
        num_samples = len(pcm_bytes) // 2
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)

        # Add to buffer
        self._audio_buffer.extend(samples)

        # Process when we have enough samples
        while len(self._audio_buffer) >= self._samples_needed:
            # Extract frame
            frame = self._audio_buffer[: self._samples_needed]
            self._audio_buffer = self._audio_buffer[self._samples_needed :]

            # Run detection
            try:
                keyword_index = self._porcupine.process(frame)

                if keyword_index >= 0:
                    logger.info(
                        f"Porcupine detected wake word "
                        f"(keyword_index={keyword_index})"
                    )
                    return self._trigger_detection()

            except Exception as e:
                logger.error(f"Porcupine processing error: {e}")

        return None

    def reset(self) -> None:
        """Reset detector state."""
        self._audio_buffer.clear()
        logger.debug("Porcupine detector reset")

    def cleanup(self) -> None:
        """Clean up Porcupine resources."""
        if hasattr(self, "_porcupine") and self._porcupine:
            self._porcupine.delete()
            logger.debug("Porcupine resources released")

    def __del__(self):
        """Ensure cleanup on deletion."""
        self.cleanup()

    @property
    def sample_rate(self) -> int:
        """Get required sample rate for this detector."""
        return self._porcupine.sample_rate if self._porcupine else 16000

    @property
    def frame_length(self) -> int:
        """Get frame length required by Porcupine."""
        return self._porcupine.frame_length if self._porcupine else 512


def create_porcupine_detector(
    access_key: str,
    model_path: str,
    wake_word: str = "hey jin",
    on_detection: Optional[Callable[[], None]] = None,
    sensitivity: float = 0.5,
) -> PorcupineDetector:
    """
    Factory function to create Porcupine detector.

    Args:
        access_key: Porcupine access key
        model_path: Path to .ppn model file
        wake_word: Wake word phrase
        on_detection: Callback when detected
        sensitivity: Detection sensitivity 0.0-1.0

    Returns:
        PorcupineDetector instance
    """
    return PorcupineDetector(
        access_key=access_key,
        model_path=model_path,
        wake_word=wake_word,
        on_detection=on_detection,
        sensitivity=sensitivity,
    )


def main():
    """Test Porcupine detector with actual microphone input."""
    import sys
    from pathlib import Path
    
    # Add parent directory to path to import env_vars
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    import env_vars
    
    # Import MicStream for actual audio input
    try:
        from audio.mic_stream import MicStream
        from audio.device import list_input_devices, find_usb_mic
    except ImportError:
        sys.path.insert(0, str(parent_dir))
        from audio.mic_stream import MicStream
        from audio.device import list_input_devices, find_usb_mic

    def on_wake_word():
        print("\n🎤 ⚡ WAKE WORD DETECTED BY PORCUPINE! ⚡\n")

    # Auto-detect microphone device
    print("Detecting audio input devices...")
    input_devices = list_input_devices()
    
    if not input_devices:
        print("❌ No input devices found!")
        return
    
    print("\nAvailable input devices:")
    for dev in input_devices:
        print(f"  [{dev['index']}] {dev['name']} - {dev['channels']} ch, {dev['sample_rate']} Hz")
    
    # Try to find USB mic, otherwise use default
    usb_mic = find_usb_mic()
    if usb_mic:
        mic_device = usb_mic['index']
        print(f"\n✓ Using USB microphone: {usb_mic['name']}")
    else:
        mic_device = None
        print("\n✓ Using default input device")
    
    print()

    # Create detector
    try:
        detector = create_porcupine_detector(
            access_key=env_vars.PORCUPINE_ACCESS_KEY,
            model_path=env_vars.PORCUPINE_MODEL_PATH,
            wake_word="hey jin",
            on_detection=on_wake_word,
            sensitivity=0.5,
        )
    except Exception as e:
        logger.error(f"Failed to create detector: {e}")
        print("\n❌ Error creating Porcupine detector")
        print("Make sure PORCUPINE_ACCESS_KEY is set in .env")
        print(f"Model path: {env_vars.PORCUPINE_MODEL_PATH}")
        return

    print("Porcupine Wake Word Detector Test")
    print(f"Wake word: '{detector.wake_word}'")
    print(f"Model: {os.path.basename(detector.model_path)}")
    print(f"Sample rate: {detector.sample_rate} Hz")
    print(f"Frame length: {detector.frame_length} samples")
    print("\n🎙️  Recording from microphone...")
    print("Speak 'Hey Jin' to test detection")
    print("Press Ctrl+C to stop\n")

    # Create mic stream with detected device
    try:
        mic = MicStream(
            sample_rate=detector.sample_rate,
            channels=1,
            chunk_duration_ms=30,
            device=mic_device
        )
    except Exception as e:
        print(f"❌ Failed to create mic stream: {e}")
        print("\nTrying with default device...")
        try:
            mic = MicStream(
                sample_rate=detector.sample_rate,
                channels=1,
                chunk_duration_ms=30,
                device=None
            )
        except Exception as e2:
            print(f"❌ Still failed: {e2}")
            detector.cleanup()
            return

    try:
        chunk_count = 0
        for chunk in mic.stream():
            event = detector.process_chunk(chunk)

            if event or chunk_count % 50 == 0:
                status = "🎧 Listening..." if detector.is_listening else "💤 Paused"
                print(f"[{chunk_count:04d}] {status}", end="")
                if event:
                    print(f" | ⚡ {event.value}")
                else:
                    print()

            chunk_count += 1

    except KeyboardInterrupt:
        print("\n\n✅ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error during detection: {e}")
        logger.exception("Detection error")
    finally:
        detector.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
