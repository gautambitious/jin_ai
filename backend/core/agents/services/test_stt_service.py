#!/Users/gautam/Dev/jin_ai/env/bin/python
"""
Test script for STT service.

This script tests the STT service by transcribing an audio file.
"""

import os
import sys

# Add core directory to path so Django can find 'main' module
core_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, core_dir)

from agents.services.stt_service import (
    STTService,
    STTServiceError,
    transcribe_audio_bytes,
)


def test_transcribe_audio_file(audio_file_path: str):
    """
    Test transcribing an audio file.

    Args:
        audio_file_path: Path to the audio file to transcribe
    """
    print(f"\n{'='*60}")
    print(f"Testing STT Service with: {audio_file_path}")
    print(f"{'='*60}\n")

    # Check if file exists
    if not os.path.exists(audio_file_path):
        print(f"Error: Audio file not found: {audio_file_path}")
        return

    # Read audio file
    print(f"Reading audio file...")
    with open(audio_file_path, "rb") as f:
        audio_data = f.read()

    file_size_mb = len(audio_data) / (1024 * 1024)
    print(f"Audio file size: {file_size_mb:.2f} MB ({len(audio_data)} bytes)\n")

    # Test 1: Using STTService directly with full result
    print("Test 1: Full transcription with metadata")
    print("-" * 60)
    try:
        stt = STTService()
        result = stt.transcribe_audio(audio_data)

        print(f"✓ Transcription successful!")
        print(f"\nTranscript:")
        print(f"  {result['transcript']}\n")

        if result["confidence"]:
            print(f"Confidence: {result['confidence']:.2%}")

        if result["metadata"]:
            print(f"\nMetadata:")
            for key, value in result["metadata"].items():
                print(f"  {key}: {value}")

        if result["words"]:
            print(f"\nWord count: {len(result['words'])} words")
            print(f"First few words with timing:")
            for word_info in result["words"][:5]:
                print(
                    f"  {word_info['punctuated_word']}: "
                    f"{word_info['start']:.2f}s - {word_info['end']:.2f}s "
                    f"(confidence: {word_info['confidence']:.2%})"
                )

        print("\n" + "=" * 60)

    except STTServiceError as e:
        print(f"✗ STT Error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()

    # Test 2: Using convenience function for simple text output
    print("\n\nTest 2: Simple text-only transcription")
    print("-" * 60)
    try:
        text = transcribe_audio_bytes(audio_data)
        print(f"✓ Transcription successful!")
        print(f"\nTranscript:")
        print(f"  {text}")
        print("\n" + "=" * 60)

    except STTServiceError as e:
        print(f"✗ STT Error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    # Test 3: With language detection
    print("\n\nTest 3: With automatic language detection")
    print("-" * 60)
    try:
        stt = STTService()
        result = stt.transcribe_audio(audio_data, detect_language=True)

        print(f"✓ Transcription successful!")
        if "detected_language" in result:
            print(f"Detected language: {result.get('detected_language', 'Unknown')}")
        print(f"\nTranscript:")
        print(f"  {result['transcript']}")
        print("\n" + "=" * 60)

    except STTServiceError as e:
        print(f"✗ STT Error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python test_stt_service.py <audio_file_path>")
        print("\nExample:")
        print("  python test_stt_service.py ~/audio/sample.wav")
        print("  python test_stt_service.py ~/audio/sample.mp3")
        print("\nSupported formats: WAV, MP3, FLAC, OGG, and more")
        sys.exit(1)

    audio_file_path = sys.argv[1]

    # Expand user path if needed
    audio_file_path = os.path.expanduser(audio_file_path)

    test_transcribe_audio_file(audio_file_path)


if __name__ == "__main__":
    main()
