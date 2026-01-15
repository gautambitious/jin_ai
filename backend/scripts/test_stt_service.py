"""
Test script for STT Service - Webhook Audio Example

This script demonstrates how to use the STT service to transcribe
audio chunks received from webhooks or streaming sources.
"""

import sys
import os
import time

# Add the core directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from agents.services.stt_service import STTService


def test_stt_with_file():
    """
    Test STT service by reading audio from a file in chunks.
    This simulates receiving audio chunks from a webhook.
    """
    print("=" * 60)
    print("STT Service - Webhook Audio Chunk Test")
    print("=" * 60)

    # Replace this with your actual audio file path
    # The audio should be in the format specified (linear16, 24kHz, mono)
    audio_file_path = "test_audio.raw"  # Raw PCM audio file

    if not os.path.exists(audio_file_path):
        print(f"\n⚠️  Audio file not found: {audio_file_path}")
        print("Creating a test with simulated chunks instead...")
        test_stt_simulated()
        return

    print(f"\n📁 Reading audio from: {audio_file_path}")
    print("\n🎤 Starting STT transcription...\n")

    # Track transcripts
    transcripts = []
    final_transcripts = []

    def on_transcript(text, metadata):
        """Handle transcript results"""
        is_final = metadata.get("is_final", False)
        confidence = metadata.get("confidence", 0)

        if is_final:
            final_transcripts.append(text)
            print(f"✅ FINAL: {text}")
            print(f"   Confidence: {confidence:.2%}")
        else:
            transcripts.append(text)
            print(f"⏳ INTERIM: {text}")

    def on_error(error_message):
        """Handle errors"""
        print(f"❌ ERROR: {error_message}")

    try:
        # Create STT service
        stt = STTService()

        # Start transcription
        success = stt.start_transcription(
            on_transcript=on_transcript,
            on_error=on_error,
            language="en-US",
            smart_format=True,
            interim_results=True,
            encoding="linear16",
            sample_rate=24000,
            channels=1,
        )

        if not success:
            print("❌ Failed to start transcription")
            return

        # Simulate receiving audio chunks from webhook
        # Read file in chunks (similar to receiving chunks from webhook)
        chunk_size = 8192  # 8KB chunks

        with open(audio_file_path, "rb") as audio_file:
            chunk_num = 0
            while True:
                chunk = audio_file.read(chunk_size)
                if not chunk:
                    break

                chunk_num += 1
                print(f"📤 Sending chunk {chunk_num} ({len(chunk)} bytes)...")
                stt.send_audio(chunk)

                # Small delay to simulate real-time streaming
                time.sleep(0.1)

        # Finalize and wait for final results
        print("\n🏁 Finalizing transcription...")
        stt.finalize()

        # Wait a moment for final results
        time.sleep(2)

        # Stop transcription
        stt.stop_transcription()

        # Display results
        print("\n" + "=" * 60)
        print("TRANSCRIPTION RESULTS")
        print("=" * 60)
        print(f"\n📊 Total interim results: {len(transcripts)}")
        print(f"📊 Total final results: {len(final_transcripts)}")

        if final_transcripts:
            print("\n📝 Complete Transcript:")
            print("-" * 60)
            for i, transcript in enumerate(final_transcripts, 1):
                print(f"{i}. {transcript}")
        else:
            print("\n⚠️  No final transcripts received")

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback

        traceback.print_exc()


def test_stt_simulated():
    """
    Test STT service with simulated webhook behavior.
    This shows the structure without requiring an actual audio file.
    """
    print("\n" + "=" * 60)
    print("STT Service - Simulated Webhook Test")
    print("=" * 60)

    print("\n📝 This test demonstrates the structure for webhook integration:")
    print("\n1️⃣  Start transcription session with callbacks")
    print("2️⃣  Receive audio chunks from webhook")
    print("3️⃣  Send each chunk to STT service")
    print("4️⃣  Process transcripts in real-time")
    print("5️⃣  Finalize when audio stream ends")

    print("\n" + "=" * 60)
    print("EXAMPLE WEBHOOK INTEGRATION CODE")
    print("=" * 60)

    example_code = '''
# Django webhook view example
from django.views import View
from django.http import JsonResponse
from agents.services.stt_service import STTService

class AudioWebhookView(View):
    def __init__(self):
        super().__init__()
        self.stt = STTService()
        self.transcripts = []
        
    def on_transcript(self, text, metadata):
        """Handle transcription results"""
        if metadata.get("is_final"):
            self.transcripts.append(text)
            # Process final transcript (save to DB, trigger action, etc.)
            print(f"Final transcript: {text}")
    
    def post(self, request):
        """Handle incoming audio chunks from webhook"""
        try:
            # Get audio data from request
            audio_chunk = request.body
            
            # If first chunk, start transcription
            if not self.stt.is_connected:
                self.stt.start_transcription(
                    on_transcript=self.on_transcript,
                    language="en-US",
                    encoding="linear16",
                    sample_rate=24000,
                )
            
            # Send audio chunk to STT
            self.stt.send_audio(audio_chunk)
            
            # If end of stream signal, finalize
            if request.headers.get("X-Audio-Stream-End"):
                self.stt.finalize()
                self.stt.stop_transcription()
                
                return JsonResponse({
                    "status": "complete",
                    "transcripts": self.transcripts
                })
            
            return JsonResponse({"status": "processing"})
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
'''

    print(example_code)


def test_stt_context_manager():
    """
    Test STT service using context manager pattern.
    This is useful for automatic cleanup.
    """
    print("\n" + "=" * 60)
    print("STT Service - Context Manager Pattern")
    print("=" * 60)

    print("\n📝 Example using context manager for automatic cleanup:\n")

    example_code = '''
from agents.services.stt_service import STTService

def transcribe_webhook_audio(audio_chunks):
    """Transcribe audio chunks from webhook"""
    results = []
    
    def on_transcript(text, metadata):
        if metadata.get("is_final"):
            results.append(text)
    
    # Using context manager - automatic cleanup
    with STTService() as stt:
        stt.start_transcription(
            on_transcript=on_transcript,
            language="en-US",
        )
        
        # Process each audio chunk
        for chunk in audio_chunks:
            stt.send_audio(chunk)
        
        # Finalize
        stt.finalize()
    
    # Connection automatically closed when exiting context
    return results
'''

    print(example_code)


if __name__ == "__main__":
    print("\n🎯 STT Service Test Suite")
    print("=" * 60)

    # Test with file if available, otherwise show examples
    test_stt_with_file()

    # Show webhook integration examples
    test_stt_context_manager()

    print("\n✨ Test suite complete!")
    print("\n💡 To test with real audio:")
    print("   1. Create a raw PCM audio file (linear16, 24kHz, mono)")
    print("   2. Save it as 'test_audio.raw' in the scripts directory")
    print("   3. Run this script again")
    print("\n💡 Or record audio using:")
    print("   ffmpeg -f avfoundation -i ':0' -ar 24000 -ac 1 -f s16le test_audio.raw")
