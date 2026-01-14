"""
Debug TTS Audio Format

This script tests different audio formats to help debug the static noise issue.
"""

import sys
import os
import asyncio

# Setup paths
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
core_dir = os.path.join(backend_dir, "core")

sys.path.insert(0, core_dir)
sys.path.insert(0, backend_dir)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.services import TTSService


def test_formats():
    """Test different audio formats."""
    print("\n" + "=" * 60)
    print("🎤 Testing TTS Audio Formats")
    print("=" * 60)

    tts = TTSService()
    test_text = "Testing audio format"

    formats = [
        ("linear16", 16000, "Raw PCM 16-bit"),
        ("opus", None, "Opus compressed"),
        ("mp3", None, "MP3 compressed"),
    ]

    for encoding, sample_rate, description in formats:
        print(f"\nTesting: {encoding} - {description}")
        print("-" * 60)

        try:
            kwargs = {
                "text": test_text,
                "encoding": encoding,
            }
            if sample_rate:
                kwargs["sample_rate"] = sample_rate

            chunks = list(tts.generate_audio(**kwargs))
            total_bytes = sum(len(chunk) for chunk in chunks)

            print(f"✅ Success!")
            print(f"   Chunks: {len(chunks)}")
            print(f"   Total bytes: {total_bytes:,}")
            print(f"   Avg chunk size: {total_bytes // len(chunks) if chunks else 0}")

        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n" + "=" * 60)
    print("\nRecommendation:")
    print("- For WebSocket streaming to simple clients: use 'linear16'")
    print("- For compressed streaming: use 'opus' (requires client decoder)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    test_formats()
