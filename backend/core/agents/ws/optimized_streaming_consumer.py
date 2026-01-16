"""
Optimized Streaming Audio Consumer

Integrates streaming STT, LLM, and TTS for minimal latency voice interactions.

Pipeline optimization (ULTRA-STREAMING MODE):
1. Stream audio to Deepgram (no buffering)
2. Process interim transcripts for early intent detection
3. Start LLM on speech_final or strong intent
4. Stream LLM tokens in ~5-word chunks to TTS (no sentence wait!)
5. Start audio playback immediately on first chunk
6. Continue streaming chunks while LLM generates
7. Support interruption on new input

Target latency: <2 seconds end-to-end
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any
from channels.generic.websocket import AsyncWebsocketConsumer

from agents.services.streaming_stt_service import StreamingSTTService
from agents.services.streaming_tts_service import StreamingTTSService
from agents.services.streaming_voice_router import StreamingVoiceRouter
from agents.ws.audio_streamer import AudioStreamer
from agents.ws.audio_chunker import chunk_audio
from agents.constants import AudioFormat

logger = logging.getLogger(__name__)


class OptimizedStreamingConsumer(AsyncWebsocketConsumer):
    """
    High-performance streaming consumer for voice interactions.

    Ultra-Streaming Optimizations:
    - No audio buffering - streams directly to STT
    - Interim transcript processing for early intent detection
    - Parallel LLM and TTS pipeline
    - Word-group streaming (5 words) - no sentence wait!
    - Immediate audio playback on first chunk
    - Interruption support
    
    Configuration:
    - self.min_words_for_streaming: Tune chunk size (default: 5 words)
      Lower = more responsive, more API calls
      Higher = fewer API calls, slight delay
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Services
        self.stt_service: Optional[StreamingSTTService] = None
        self.tts_service: Optional[StreamingTTSService] = None
        self.voice_router: Optional[StreamingVoiceRouter] = None

        # Session state
        self.session_id: str = ""
        self.is_receiving_audio: bool = False
        self.is_playing_audio: bool = False
        self.should_interrupt: bool = False

        # Transcript accumulation
        self.current_transcript: str = ""
        self.last_interim_transcript: str = ""
        self.intent_detected: bool = False
        self.detected_route: Optional[str] = None

        # Timing metrics
        self.audio_start_time: Optional[float] = None
        self.transcript_start_time: Optional[float] = None
        self.response_start_time: Optional[float] = None

        # Audio streaming
        self.audio_streamer: Optional[AudioStreamer] = None
        
        # Ultra-streaming configuration
        # Lower = more responsive but more TTS API calls
        # Higher = fewer API calls but slight delay
        self.min_words_for_streaming = 5  # Stream every 5 words (configurable)

    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id", "default")
        await self.accept()

        # Initialize services
        try:
            self.tts_service = StreamingTTSService()
            self.voice_router = StreamingVoiceRouter()

            logger.info(f"[{self.session_id}] Optimized streaming consumer connected")

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "connected",
                        "session_id": self.session_id,
                        "message": "Streaming pipeline ready",
                        "optimizations": [
                            "streaming_stt",
                            "interim_results",
                            "early_intent_detection",
                            "llm_streaming",
                            "sentence_tts",
                            "interruption_support",
                        ],
                    }
                )
            )

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Failed to initialize: {e}", exc_info=True
            )
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"[{self.session_id}] Disconnected: code={close_code}")

        # Cleanup services
        if self.stt_service:
            try:
                await self.stt_service.close_stream()
            except:
                pass

        self.stt_service = None
        self.tts_service = None
        self.voice_router = None

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages"""
        try:
            if text_data:
                await self._handle_control_message(text_data)
            elif bytes_data:
                await self._handle_audio_chunk(bytes_data)

        except Exception as e:
            logger.error(f"[{self.session_id}] Error in receive: {e}", exc_info=True)
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def _handle_control_message(self, text_data: str):
        """Handle JSON control messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "start_audio_input":
                await self._start_audio_input(data.get("config", {}))

            elif message_type == "stop_audio_input":
                await self._stop_audio_input()

            elif message_type == "interrupt":
                await self._handle_interrupt()

            else:
                logger.warning(
                    f"[{self.session_id}] Unknown message type: {message_type}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"[{self.session_id}] Invalid JSON: {e}")

    async def _start_audio_input(self, config: Dict[str, Any]):
        """Start streaming STT session"""
        try:
            if self.is_receiving_audio:
                logger.warning(f"[{self.session_id}] Audio input already active")
                return

            # Check if currently playing audio - if so, interrupt it
            if self.is_playing_audio:
                logger.info(f"[{self.session_id}] Interrupting current playback")
                await self._handle_interrupt()

            # Extract config
            language = config.get("language", "en-US")
            sample_rate = config.get("sample_rate", 16000)
            encoding = config.get("encoding", "linear16")
            channels = config.get("channels", 1)

            # Reset state for new utterance
            self.current_transcript = ""
            self.last_interim_transcript = ""
            self.intent_detected = False
            self.detected_route = None
            self.audio_start_time = time.time()

            if self.voice_router:
                self.voice_router.reset_intent_detection()

            # Create STT service
            self.stt_service = StreamingSTTService()

            # Start streaming transcription
            success = await self.stt_service.start_stream(
                on_transcript=self._on_transcript,
                on_error=self._on_stt_error,
                language=language,
                encoding=encoding,
                sample_rate=sample_rate,
                channels=channels,
                interim_results=True,  # Enable interim results for low latency
                smart_format=True,
                punctuate=True,
                vad_events=True,
                endpointing=300,  # 300ms silence triggers utterance end
            )

            if success:
                self.is_receiving_audio = True
                logger.info(
                    f"[{self.session_id}] Streaming STT started: {sample_rate}Hz, {encoding}"
                )

                await self.send(
                    text_data=json.dumps(
                        {"type": "audio_input_started", "config": config}
                    )
                )
            else:
                raise Exception("Failed to start STT stream")

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error starting audio input: {e}", exc_info=True
            )
            self.is_receiving_audio = False
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": f"Failed to start audio input: {str(e)}",
                    }
                )
            )

    async def _handle_audio_chunk(self, audio_data: bytes):
        """Stream audio chunk directly to STT (no buffering)"""
        if not self.is_receiving_audio or not self.stt_service:
            return

        try:
            # Send directly to Deepgram - no buffering!
            await self.stt_service.send_audio(audio_data)
            logger.debug(f"[{self.session_id}] Streamed {len(audio_data)} bytes to STT")

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error streaming audio: {e}", exc_info=True
            )

    def _on_transcript(self, text: str, metadata: Dict[str, Any]):
        """
        Handle transcript from STT (runs in callback, need to schedule async)

        This processes both interim and final transcripts for minimal latency.
        """
        # Schedule async processing
        asyncio.create_task(self._process_transcript(text, metadata))

    async def _process_transcript(self, text: str, metadata: Dict[str, Any]):
        """Process transcript with early intent detection"""
        try:
            is_final = metadata.get("is_final", False)
            speech_final = metadata.get("speech_final", False)
            confidence = metadata.get("confidence", 0.0)

            # Track timing
            if not self.transcript_start_time:
                self.transcript_start_time = time.time()
                latency_ms = (
                    (self.transcript_start_time - self.audio_start_time) * 1000
                    if self.audio_start_time
                    else 0
                )
                logger.info(
                    f"[{self.session_id}] First transcript: {latency_ms:.0f}ms from audio start"
                )

            # Send transcript to client
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "transcript",
                        "text": text,
                        "is_final": is_final,
                        "speech_final": speech_final,
                        "confidence": confidence,
                        "metadata": metadata,
                    }
                )
            )

            # Update transcript state
            if is_final:
                self.current_transcript = text
                logger.info(f"[{self.session_id}] Final transcript: '{text}'")
            else:
                self.last_interim_transcript = text
                logger.debug(f"[{self.session_id}] Interim: '{text}'")

            # Early intent detection on interim transcripts
            if not self.intent_detected and not is_final and self.voice_router:
                intent_result = await self.voice_router.process_partial_transcript(
                    partial_transcript=text, is_final=False
                )

                if intent_result and intent_result.get("intent_detected"):
                    self.intent_detected = True
                    self.detected_route = intent_result.get("route")

                    logger.info(
                        f"[{self.session_id}] Intent detected early: {self.detected_route}"
                    )

                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "intent_detected",
                                "route": self.detected_route,
                                "transcript": text,
                            }
                        )
                    )

            # Trigger response on speech_final or final with high confidence
            if (speech_final or (is_final and confidence > 0.7)) and text.strip():
                # Close STT stream immediately
                await self._stop_audio_input()

                # Start response generation
                await self._generate_response(text)

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error processing transcript: {e}", exc_info=True
            )

    async def _generate_response(self, transcript: str):
        """Generate and stream response"""
        try:
            self.response_start_time = time.time()

            # Calculate latency so far
            if self.audio_start_time:
                latency_ms = (self.response_start_time - self.audio_start_time) * 1000
                logger.info(
                    f"[{self.session_id}] Starting response generation: {latency_ms:.0f}ms from audio start"
                )

            # Stream response from voice router with ULTRA-LOW-LATENCY mode
            full_response = ""
            current_buffer = ""
            word_count = 0
            min_words_for_tts = self.min_words_for_streaming  # Configurable threshold
            first_audio_sent = False

            async for chunk in self.voice_router.stream_response(
                transcript=transcript,
                session_id=self.session_id,
                route_hint=self.detected_route,
            ):
                chunk_type = chunk.get("type")
                content = chunk.get("content", "")

                if chunk_type == "route":
                    # Route decision
                    route = chunk.get("route")
                    logger.info(f"[{self.session_id}] Routed to: {route}")

                    await self.send(
                        text_data=json.dumps({"type": "route_decision", "route": route})
                    )

                elif chunk_type == "token":
                    # Streaming token from LLM
                    full_response += content
                    current_buffer += content

                    # Count words (space-separated)
                    if content.strip():
                        word_count += len(content.strip().split())

                    # ULTRA-STREAMING: Send to TTS every N words OR on punctuation
                    should_stream = False
                    
                    # Check if we have enough words
                    if word_count >= min_words_for_tts:
                        should_stream = True
                        word_count = 0  # Reset counter
                    
                    # Or check for natural pauses (sentence/clause boundaries)
                    elif any(char in content for char in {".", "!", "?", ",", ";", ":", "\n"}):
                        should_stream = True
                        word_count = 0

                    if should_stream and current_buffer.strip():
                        chunk_text = current_buffer.strip()
                        logger.info(
                            f"[{self.session_id}] Streaming chunk ({len(chunk_text.split())} words): '{chunk_text[:50]}...'"
                        )

                        # Stream TTS immediately - don't wait for sentence end!
                        await self._stream_text_chunk(
                            chunk_text, is_first=not first_audio_sent
                        )
                        first_audio_sent = True
                        current_buffer = ""

                elif chunk_type == "complete":
                    # Complete response (from agent or LLM finished)
                    full_response = content

                    # If there's any remaining buffered text, stream it
                    if current_buffer.strip():
                        await self._stream_text_chunk(
                            current_buffer.strip(), is_first=not first_audio_sent
                        )
                        first_audio_sent = True
                    elif not first_audio_sent:
                        # No streaming happened, generate TTS for full response
                        await self._stream_text_chunk(full_response, is_first=True)

                    # Send completion
                    await self.send(
                        text_data=json.dumps(
                            {"type": "response_complete", "text": full_response}
                        )
                    )

                    # Calculate total latency
                    if self.audio_start_time:
                        total_latency = (time.time() - self.audio_start_time) * 1000
                        logger.info(
                            f"[{self.session_id}] Total pipeline latency: {total_latency:.0f}ms"
                        )

                elif chunk_type == "error":
                    logger.error(f"[{self.session_id}] Error in response: {content}")
                    await self.send(
                        text_data=json.dumps({"type": "error", "message": content})
                    )

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error generating response: {e}", exc_info=True
            )
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": f"Failed to generate response: {str(e)}",
                    }
                )
            )

    async def _stream_text_chunk(self, text: str, is_first: bool = False):
        """Generate and stream TTS for any text chunk (word group, phrase, or sentence)"""
        try:
            if not sentence or not sentence.strip():
                return

            if is_first:
                first_audio_time = time.time()
                if self.audio_start_time:
                    latency_ms = (first_audio_time - self.audio_start_time) * 1000
                    logger.info(
                        f"[{self.session_id}] First audio: {latency_ms:.0f}ms from user audio start (target: <2000ms)"
                    )

            logger.info(f"[{self.session_id}] Generating TTS for: '{text[:50]}...'")

            self.is_playing_audio = True

            # Initialize audio streamer if needed
            if not self.audio_streamer:
                self.audio_streamer = AudioStreamer(
                    websocket=self,
                    stream_id=f"tts_{self.session_id}",
                    sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE,
                    channels=1,
                )

            # Stream TTS audio chunks
            async for audio_chunk, metadata in self.tts_service.generate_streaming(
                text=text,
                encoding="linear16",
                sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE,
            ):
                # Check for interruption
                if self.should_interrupt:
                    logger.info(f"[{self.session_id}] TTS interrupted")
                    break

                # Chunk and stream audio
                for chunked_audio in chunk_audio(
                    audio_chunk,
                    sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE,
                    chunk_duration_ms=20,
                ):
                    if self.should_interrupt:
                        break

                    await self.audio_streamer.send_audio_chunk(chunked_audio)

            self.is_playing_audio = False

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error streaming sentence audio: {e}",
                exc_info=True,
            )
            self.is_playing_audio = False

    async def _stop_audio_input(self):
        """Stop STT streaming"""
        if not self.is_receiving_audio:
            return

        try:
            self.is_receiving_audio = False

            if self.stt_service:
                await self.stt_service.close_stream()
                self.stt_service = None

            logger.info(f"[{self.session_id}] STT stream closed")

            await self.send(text_data=json.dumps({"type": "audio_input_stopped"}))

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error stopping audio input: {e}", exc_info=True
            )

    async def _handle_interrupt(self):
        """Handle interruption - stop current audio playback"""
        try:
            logger.info(f"[{self.session_id}] Interrupt requested")

            self.should_interrupt = True
            self.is_playing_audio = False

            await self.send(
                text_data=json.dumps(
                    {"type": "interrupted", "message": "Audio playback interrupted"}
                )
            )

            # Reset interrupt flag after brief delay
            await asyncio.sleep(0.1)
            self.should_interrupt = False

        except Exception as e:
            logger.error(
                f"[{self.session_id}] Error handling interrupt: {e}", exc_info=True
            )

    def _on_stt_error(self, error_message: str):
        """Handle STT error (runs in callback)"""
        asyncio.create_task(self._handle_stt_error(error_message))

    async def _handle_stt_error(self, error_message: str):
        """Handle STT error async"""
        logger.error(f"[{self.session_id}] STT error: {error_message}")
        await self.send(
            text_data=json.dumps({"type": "stt_error", "message": error_message})
        )
