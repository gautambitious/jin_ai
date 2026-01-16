"""
Streaming Voice Router Service

Optimized for low-latency voice interactions with:
- Early intent detection from partial transcripts
- LLM streaming with prompt caching
- Parallel processing pipeline
"""

import logging
from typing import Dict, Any, Optional, AsyncGenerator
import re

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

from agents.agents_registry import agents_registry
from agents.orchestrator import AgentSystem
from env_vars import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)


# Cached system prompts (kept in memory to avoid re-sending)
ROUTING_SYSTEM_PROMPT = """You are a voice assistant router. Analyze user requests and determine the best way to handle them.

Available agents and their capabilities:
{agent_descriptions}

Respond with either:
- AGENT:<agent_name> if the request matches an agent
- DIRECT if it's a general question

This is a VOICE interface - users expect quick responses."""


VOICE_SYSTEM_PROMPT = """You are a helpful voice assistant. Keep responses:
- SHORT (1-3 sentences max)
- CONVERSATIONAL and natural
- NO formatting or markdown
- Speak naturally as in verbal conversation"""


class StreamingVoiceRouter:
    """
    Optimized voice router with streaming and early intent detection.

    Features:
    - Detects intent from partial transcripts
    - Streams LLM responses token-by-token
    - Caches system prompts
    - Minimizes latency at every step
    """

    def __init__(
        self,
        agent_system: Optional[AgentSystem] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize streaming voice router.

        Args:
            agent_system: Initialized AgentSystem instance
            api_key: OpenAI API key
            model: Model name
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or OPENAI_MODEL

        # Initialize LLM with streaming enabled
        self.llm = ChatOpenAI(
            temperature=0.7,
            model=self.model,
            api_key=self.api_key,
            streaming=True,  # Enable streaming
        )

        # Initialize agent system
        self.agent_system = agent_system
        if not self.agent_system:
            from agents.orchestrator import initialize_agent_system

            self.agent_system = initialize_agent_system(
                openai_api_key=self.api_key, model=self.model
            )

        # Cached prompts
        self._routing_prompt_cache = None
        self._voice_prompt_cache = None

        # Intent detection state
        self._partial_transcript = ""
        self._intent_detected = False
        self._detected_route = None

        logger.info(f"StreamingVoiceRouter initialized with model: {self.model}")

    def _get_agent_descriptions(self) -> str:
        """Get formatted descriptions of available agents."""
        agents_info = self.agent_system.get_available_agents()

        if not agents_info:
            return "No specialized agents available."

        descriptions = []
        for agent in agents_info:
            name = agent.get("name", "unknown")
            desc = agent.get("description", "No description")
            capabilities = agent.get("capabilities", [])
            cap_str = ", ".join(capabilities) if capabilities else "general tasks"
            descriptions.append(f"- {name}: {desc} (Capabilities: {cap_str})")

        return "\n".join(descriptions)

    def _detect_intent_early(self, partial_transcript: str) -> Optional[str]:
        """
        Detect intent from partial transcript to start processing early.

        Uses simple pattern matching for common intents to avoid LLM call.
        Falls back to LLM for complex routing.

        Args:
            partial_transcript: Incomplete transcript so far

        Returns:
            Intent route or None if not enough information
        """
        text_lower = partial_transcript.lower().strip()

        # Need at least a few words to detect intent
        word_count = len(text_lower.split())
        if word_count < 3:
            return None

        # Pattern-based intent detection for common cases
        patterns = {
            r"\b(what|tell|explain|how)\b.*\b(weather|temperature|forecast)\b": "weather",
            r"\b(search|find|look up|google)\b": "search",
            r"\b(portfolio|stocks|investment|trading)\b": "portfolio",
            r"\b(news|latest|headlines)\b": "news",
            r"\b(calendar|schedule|meeting|appointment)\b": "calendar",
            r"\b(email|message|send)\b": "email",
        }

        for pattern, intent_type in patterns.items():
            if re.search(pattern, text_lower):
                logger.info(
                    f"Early intent detected: {intent_type} from '{partial_transcript}'"
                )
                return intent_type

        # If we have enough words but no pattern match, might be a direct question
        if word_count >= 5:
            # Questions often start with these words
            question_starters = [
                "what",
                "who",
                "where",
                "when",
                "why",
                "how",
                "is",
                "are",
                "can",
                "do",
                "does",
            ]
            first_word = text_lower.split()[0]
            if first_word in question_starters:
                logger.info(f"Detected as direct question from '{partial_transcript}'")
                return "DIRECT"

        return None

    async def process_partial_transcript(
        self, partial_transcript: str, is_final: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Process partial transcript for early intent detection.

        Does not trigger full response generation until final transcript,
        but can prepare routing and start agent initialization.

        Args:
            partial_transcript: Current transcript (may be incomplete)
            is_final: Whether this is the final transcript

        Returns:
            Dict with intent info if detected, None otherwise
        """
        self._partial_transcript = partial_transcript

        # Try to detect intent early
        if not self._intent_detected:
            detected_route = self._detect_intent_early(partial_transcript)

            if detected_route:
                self._intent_detected = True
                self._detected_route = detected_route

                logger.info(f"Intent detected early: {detected_route}")

                return {
                    "intent_detected": True,
                    "route": detected_route,
                    "transcript": partial_transcript,
                    "is_final": is_final,
                }

        return None

    async def stream_response(
        self,
        transcript: str,
        session_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        route_hint: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream response for final transcript.

        Yields response chunks as they're generated, allowing
        downstream processing (TTS) to start immediately.

        Args:
            transcript: Final transcript text
            session_id: Session identifier
            metadata: Additional metadata
            route_hint: Pre-detected route from partial transcript processing

        Yields:
            Dicts with response chunks and metadata:
            {
                "type": "route" | "token" | "complete",
                "content": str,
                "route": str,
                "metadata": dict
            }
        """
        try:
            metadata = metadata or {}

            # Determine routing
            if route_hint and route_hint != "DIRECT":
                # Use pre-detected route
                route_decision = "AGENT"
                agent_name = route_hint
                logger.info(f"Using pre-detected route: {agent_name}")
            else:
                # Quick routing decision
                route_decision, agent_name = await self._quick_route(transcript)

            # Yield routing decision immediately
            yield {
                "type": "route",
                "content": "",
                "route": agent_name if route_decision == "AGENT" else "DIRECT",
                "metadata": {"routing_decision": route_decision},
            }

            # Handle agent routing
            if route_decision == "AGENT" and agent_name:
                try:
                    # Execute agent (agents typically don't stream, so get full response)
                    response = self.agent_system.execute(agent_name, transcript)
                    response = self._make_voice_friendly(response)

                    # Yield complete agent response
                    yield {
                        "type": "complete",
                        "content": response,
                        "route": agent_name,
                        "metadata": {"agent_name": agent_name},
                    }

                except Exception as e:
                    logger.error(f"Agent execution failed: {e}", exc_info=True)
                    # Fallback to direct LLM
                    async for chunk in self._stream_direct_response(transcript):
                        yield chunk
            else:
                # Stream direct LLM response
                async for chunk in self._stream_direct_response(transcript):
                    yield chunk

        except Exception as e:
            logger.error(f"Error in stream_response: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": "I encountered an error processing your request.",
                "route": "ERROR",
                "metadata": {"error": str(e)},
            }

    async def _quick_route(self, transcript: str) -> tuple[str, Optional[str]]:
        """
        Quick routing decision using cached prompt.

        Returns:
            Tuple of (route_decision, agent_name)
        """
        try:
            # Use cached routing prompt
            agent_descriptions = self._get_agent_descriptions()

            prompt = (
                ROUTING_SYSTEM_PROMPT.format(agent_descriptions=agent_descriptions)
                + f"\n\nUser request: {transcript}\n\nResponse:"
            )

            # Quick LLM call for routing (non-streaming)
            response = await self.llm.ainvoke(prompt)
            decision = response.content.strip()

            logger.info(f"Routing decision: {decision}")

            if decision.startswith("AGENT:"):
                agent_name = decision.split(":", 1)[1].strip()
                return "AGENT", agent_name
            else:
                return "DIRECT", None

        except Exception as e:
            logger.error(f"Routing failed: {e}", exc_info=True)
            return "DIRECT", None

    async def _stream_direct_response(
        self, transcript: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream direct LLM response token by token.

        Args:
            transcript: User transcript

        Yields:
            Response chunks
        """
        try:
            # Use cached system prompt
            prompt = VOICE_SYSTEM_PROMPT + f"\n\nUser: {transcript}\n\nAssistant:"

            # Stream response from LLM
            full_response = ""
            async for chunk in self.llm.astream(prompt):
                if chunk.content:
                    full_response += chunk.content

                    yield {
                        "type": "token",
                        "content": chunk.content,
                        "route": "DIRECT",
                        "metadata": {},
                    }

            # Yield completion marker
            yield {
                "type": "complete",
                "content": full_response,
                "route": "DIRECT",
                "metadata": {},
            }

        except Exception as e:
            logger.error(f"Streaming response failed: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": "I'm having trouble responding right now.",
                "route": "ERROR",
                "metadata": {"error": str(e)},
            }

    def _make_voice_friendly(self, text: str, max_sentences: int = 3) -> str:
        """Make text voice-friendly by shortening and removing formatting."""
        # Remove markdown
        text = text.replace("**", "").replace("*", "").replace("#", "")
        text = text.replace("```", "").replace("`", "")

        # Split into sentences
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Limit sentences
        if len(sentences) > max_sentences:
            text = ". ".join(sentences[:max_sentences]) + "."

        # Remove bullet points
        lines = text.split("\n")
        natural_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("•"):
                line = line[1:].strip()
            if line:
                natural_lines.append(line)

        text = " ".join(natural_lines)

        # Limit word count
        words = text.split()
        if len(words) > 50:
            text = " ".join(words[:50]) + "..."

        return text

    def reset_intent_detection(self):
        """Reset intent detection state for new utterance."""
        self._partial_transcript = ""
        self._intent_detected = False
        self._detected_route = None
