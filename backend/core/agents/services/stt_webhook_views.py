"""
HTTP Webhook Views for Speech-to-Text

This module provides HTTP webhook endpoints for receiving audio chunks
and returning transcriptions. Useful for integrating with external services
that POST audio data.
"""

import json
import logging
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from agents.services.stt_service import STTService
from agents.constants import STTDefaults

logger = logging.getLogger(__name__)


# In-memory session storage (use Redis/DB for production)
_stt_sessions = {}


@method_decorator(csrf_exempt, name="dispatch")
class AudioWebhookView(View):
    """
    HTTP Webhook endpoint for receiving audio chunks and returning transcripts.

    This view supports two modes:
    1. Single-shot: Send complete audio file, get transcript
    2. Streaming: Send audio chunks with session management

    Endpoints:
        POST /webhook/stt/start/ - Start a transcription session
        POST /webhook/stt/audio/ - Send audio chunk
        POST /webhook/stt/finalize/ - Finalize and get results
        POST /webhook/stt/transcribe/ - Single-shot transcription

    Example Usage (Streaming):
        # Start session
        response = requests.post('/webhook/stt/start/', json={
            'language': 'en-US',
            'encoding': 'linear16',
            'sample_rate': 24000
        })
        session_id = response.json()['session_id']

        # Send audio chunks
        for chunk in audio_chunks:
            requests.post('/webhook/stt/audio/', data=chunk, headers={
                'X-Session-Id': session_id,
                'Content-Type': 'application/octet-stream'
            })

        # Get final transcript
        response = requests.post('/webhook/stt/finalize/', json={
            'session_id': session_id
        })
        transcript = response.json()['transcript']

    Example Usage (Single-shot):
        with open('audio.raw', 'rb') as f:
            response = requests.post('/webhook/stt/transcribe/',
                data=f.read(),
                headers={
                    'Content-Type': 'application/octet-stream',
                    'X-Language': 'en-US',
                    'X-Encoding': 'linear16',
                    'X-Sample-Rate': '24000'
                }
            )
        transcript = response.json()['transcript']
    """

    def post(self, request, action="transcribe"):
        """Handle POST requests for different STT actions"""
        try:
            if action == "start":
                return self._start_session(request)
            elif action == "audio":
                return self._process_audio(request)
            elif action == "finalize":
                return self._finalize_session(request)
            elif action == "transcribe":
                return self._single_shot_transcribe(request)
            else:
                return JsonResponse({"error": f"Unknown action: {action}"}, status=400)

        except Exception as e:
            logger.error(f"Error in AudioWebhookView: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

    def _start_session(self, request):
        """Start a new transcription session"""
        try:
            # Parse configuration
            if request.content_type == "application/json":
                config = json.loads(request.body)
            else:
                config = {}

            # Extract settings
            language = config.get("language", STTDefaults.DEFAULT_LANGUAGE)
            encoding = config.get("encoding", STTDefaults.DEFAULT_ENCODING)
            sample_rate = config.get("sample_rate", STTDefaults.DEFAULT_SAMPLE_RATE)
            channels = config.get("channels", STTDefaults.DEFAULT_CHANNELS)
            smart_format = config.get("smart_format", True)
            interim_results = config.get("interim_results", False)

            # Generate session ID
            import uuid

            session_id = str(uuid.uuid4())

            # Create STT service
            stt = STTService()

            # Storage for transcripts
            transcripts = []
            errors = []

            def on_transcript(text, metadata):
                """Collect transcripts"""
                if metadata.get("is_final"):
                    transcripts.append(
                        {
                            "text": text,
                            "confidence": metadata.get("confidence", 0),
                            "duration": metadata.get("duration", 0),
                            "words": metadata.get("words", []),
                        }
                    )

            def on_error(error_message):
                """Collect errors"""
                errors.append(error_message)

            # Start transcription
            success = stt.start_transcription(
                on_transcript=on_transcript,
                on_error=on_error,
                language=language,
                encoding=encoding,
                sample_rate=sample_rate,
                channels=channels,
                smart_format=smart_format,
                interim_results=interim_results,
            )

            if not success:
                return JsonResponse(
                    {"error": "Failed to start transcription"}, status=500
                )

            # Store session
            _stt_sessions[session_id] = {
                "stt": stt,
                "transcripts": transcripts,
                "errors": errors,
                "config": config,
            }

            logger.info(f"Started STT session: {session_id}")

            return JsonResponse(
                {"session_id": session_id, "config": config, "status": "started"}
            )

        except Exception as e:
            logger.error(f"Error starting session: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

    def _process_audio(self, request):
        """Process audio chunk for an existing session"""
        try:
            # Get session ID from header or query param
            session_id = request.headers.get("X-Session-Id") or request.GET.get(
                "session_id"
            )

            if not session_id:
                return JsonResponse({"error": "Missing session_id"}, status=400)

            # Get session
            session = _stt_sessions.get(session_id)
            if not session:
                return JsonResponse(
                    {"error": "Invalid or expired session_id"}, status=404
                )

            # Get audio data
            audio_data = request.body
            if not audio_data:
                return JsonResponse({"error": "No audio data received"}, status=400)

            # Send to STT
            stt = session["stt"]
            stt.send_audio(audio_data)

            logger.debug(f"Processed {len(audio_data)} bytes for session {session_id}")

            return JsonResponse(
                {
                    "status": "processing",
                    "bytes_received": len(audio_data),
                    "transcripts_count": len(session["transcripts"]),
                }
            )

        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

    def _finalize_session(self, request):
        """Finalize session and return all transcripts"""
        try:
            # Parse request
            if request.content_type == "application/json":
                data = json.loads(request.body)
            else:
                data = {}

            session_id = (
                data.get("session_id")
                or request.headers.get("X-Session-Id")
                or request.GET.get("session_id")
            )

            if not session_id:
                return JsonResponse({"error": "Missing session_id"}, status=400)

            # Get session
            session = _stt_sessions.get(session_id)
            if not session:
                return JsonResponse(
                    {"error": "Invalid or expired session_id"}, status=404
                )

            # Finalize STT
            stt = session["stt"]
            stt.finalize()

            # Wait a moment for final results
            import time

            time.sleep(1)

            # Stop transcription
            stt.stop_transcription()

            # Get results
            transcripts = session["transcripts"]
            errors = session["errors"]

            # Combine transcripts
            full_transcript = " ".join([t["text"] for t in transcripts])

            # Clean up session
            del _stt_sessions[session_id]

            logger.info(f"Finalized STT session: {session_id}")

            return JsonResponse(
                {
                    "session_id": session_id,
                    "status": "completed",
                    "transcript": full_transcript,
                    "segments": transcripts,
                    "errors": errors,
                }
            )

        except Exception as e:
            logger.error(f"Error finalizing session: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

    def _single_shot_transcribe(self, request):
        """
        Single-shot transcription: send all audio at once, get transcript.
        This is simpler but less suitable for real-time streaming.
        """
        try:
            # Get audio data
            audio_data = request.body
            if not audio_data:
                return JsonResponse({"error": "No audio data received"}, status=400)

            # Get configuration from headers
            language = request.headers.get("X-Language", STTDefaults.DEFAULT_LANGUAGE)
            encoding = request.headers.get("X-Encoding", STTDefaults.DEFAULT_ENCODING)
            sample_rate = int(
                request.headers.get("X-Sample-Rate", STTDefaults.DEFAULT_SAMPLE_RATE)
            )

            logger.info(
                f"Single-shot transcription: {len(audio_data)} bytes, {language}, {encoding}, {sample_rate}Hz"
            )

            # Create STT service
            stt = STTService()

            # Collect transcripts
            transcripts = []
            errors = []

            def on_transcript(text, metadata):
                if metadata.get("is_final"):
                    transcripts.append(text)

            def on_error(error_message):
                errors.append(error_message)

            # Start transcription
            stt.start_transcription(
                on_transcript=on_transcript,
                on_error=on_error,
                language=language,
                encoding=encoding,
                sample_rate=sample_rate,
                interim_results=False,
            )

            # Send all audio at once (in chunks for better handling)
            chunk_size = 8192
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i : i + chunk_size]
                stt.send_audio(chunk)

            # Finalize
            stt.finalize()

            # Wait for results
            import time

            time.sleep(2)

            # Stop
            stt.stop_transcription()

            # Combine results
            full_transcript = " ".join(transcripts)

            return JsonResponse(
                {
                    "transcript": full_transcript,
                    "segments": transcripts,
                    "bytes_processed": len(audio_data),
                    "errors": errors,
                }
            )

        except Exception as e:
            logger.error(f"Error in single-shot transcription: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
