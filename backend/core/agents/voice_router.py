"""
Voice Router Service

This module handles intelligent routing of voice transcripts to appropriate agents
or direct LLM responses. It's optimized for voice interactions with short,
conversational responses.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, Sequence
import operator
import os
import sqlite3

from .agents_registry import agents_registry
from .orchestrator import AgentSystem
from env_vars import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)


# Master prompt for agent matching
AGENT_ROUTING_PROMPT = """You are a voice assistant router. Your job is to analyze user requests and determine the best way to handle them.

Available agents and their capabilities:
{agent_descriptions}

Instructions:
1. If the request clearly matches an agent's capabilities, respond with: AGENT:<agent_name>
2. If no agent matches or it's a general question, respond with: DIRECT
3. Keep in mind this is a VOICE interface - users expect quick, conversational responses

Examples:
- "How is my portfolio doing today?" -> AGENT:portfolio_agent (if portfolio agent exists)
- "What's the capital of India?" -> DIRECT
- "Tell me a joke" -> DIRECT
- "Search for recent news about Tesla" -> AGENT:research_agent (if research agent exists)

User request: {user_input}

Response (AGENT:<name> or DIRECT):"""


# Voice-optimized response prompt
VOICE_RESPONSE_PROMPT = """You are a helpful voice assistant. The user is speaking to you, so keep responses:
- SHORT and CONCISE (1-3 sentences max)
- CONVERSATIONAL and natural
- NO formatting, bullet points, or markdown
- Speak as if you're having a verbal conversation

If you need to provide multiple items, say them naturally like: "I found three things: first, second, and third."

User: {user_input}

Assistant Response:"""


class VoiceState(TypedDict):
    """State for voice routing graph with LangGraph persistence."""

    messages: Annotated[Sequence[Any], operator.add]
    user_input: str
    route_decision: str  # "AGENT:<name>" or "DIRECT"
    agent_name: Optional[str]
    final_response: str
    session_id: str
    metadata: Dict[str, Any]


class VoiceRouter:
    """
    Intelligent router for voice transcripts with LangGraph persistence.

    This service:
    1. Analyzes voice transcripts
    2. Routes to appropriate agents or direct LLM
    3. Ensures voice-friendly, concise responses
    4. Maintains conversation persistence using SQLite
    """

    def __init__(
        self,
        agent_system: Optional[AgentSystem] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        checkpoint_db_path: Optional[str] = None,
    ):
        """
        Initialize voice router.

        Args:
            agent_system: Initialized AgentSystem instance
            api_key: OpenAI API key
            model: Model name (default from env)
            checkpoint_db_path: Path to SQLite checkpoint database for persistence
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or OPENAI_MODEL
        self.llm = ChatOpenAI(temperature=0.7, model=self.model, api_key=self.api_key)

        # Initialize agent system if not provided
        self.agent_system = agent_system
        if not self.agent_system:
            from .orchestrator import initialize_agent_system

            self.agent_system = initialize_agent_system(
                openai_api_key=self.api_key, model=self.model
            )

        # Setup persistence
        self.checkpoint_db_path = (
            checkpoint_db_path or "/tmp/voice_router_checkpoints.db"
        )
        self.checkpointer = MemorySaver()  # Using MemorySaver for in-memory persistence

        # Build the graph
        self.graph = self._build_graph()

        logger.info(f"VoiceRouter initialized with model: {self.model}")
        logger.info(f"Persistence enabled with MemorySaver")

    def _get_agent_descriptions(self) -> str:
        """Get formatted descriptions of all available agents."""
        agents_info = self.agent_system.get_available_agents()

        if not agents_info:
            return "No specialized agents available currently."

        descriptions = []
        for agent in agents_info:
            name = agent.get("name", "unknown")
            desc = agent.get("description", "No description")
            capabilities = agent.get("capabilities", [])

            cap_str = ", ".join(capabilities) if capabilities else "general tasks"
            descriptions.append(f"- {name}: {desc} (Capabilities: {cap_str})")

        return "\n".join(descriptions)

    def _route_request(self, state: VoiceState) -> VoiceState:
        """
        Analyze user input and decide routing (AGENT or DIRECT).
        """
        user_input = state["user_input"]

        # Get agent descriptions
        agent_descriptions = self._get_agent_descriptions()

        # Create routing prompt
        prompt = ChatPromptTemplate.from_template(AGENT_ROUTING_PROMPT)

        try:
            # Get routing decision from LLM
            response = self.llm.invoke(
                prompt.format(
                    agent_descriptions=agent_descriptions, user_input=user_input
                )
            )

            decision = response.content.strip()
            logger.info(f"Routing decision for '{user_input}': {decision}")

            # Parse decision
            if decision.startswith("AGENT:"):
                agent_name = decision.split(":", 1)[1].strip()
                state["route_decision"] = "AGENT"
                state["agent_name"] = agent_name
            else:
                state["route_decision"] = "DIRECT"
                state["agent_name"] = None

            state["messages"].append(SystemMessage(content=f"Routing: {decision}"))

        except Exception as e:
            logger.error(f"Error in routing decision: {e}", exc_info=True)
            # Default to direct response on error
            state["route_decision"] = "DIRECT"
            state["agent_name"] = None

        return state

    def _handle_agent_request(self, state: VoiceState) -> VoiceState:
        """
        Route to specialized agent.
        """
        agent_name = state["agent_name"]
        user_input = state["user_input"]

        logger.info(f"Routing to agent: {agent_name}")

        try:
            # Execute with the selected agent
            response = self.agent_system.execute(agent_name, user_input)

            # Make response voice-friendly (shorten if needed)
            response = self._make_voice_friendly(response)

            state["final_response"] = response
            state["messages"].append(AIMessage(content=response))

            logger.info(f"Agent {agent_name} response: {response[:100]}...")

        except Exception as e:
            logger.error(f"Error executing agent {agent_name}: {e}", exc_info=True)
            # Fallback to direct LLM response
            state["route_decision"] = "DIRECT"
            return self._handle_direct_request(state)

        return state

    def _handle_direct_request(self, state: VoiceState) -> VoiceState:
        """
        Handle request directly with LLM (no agent).
        """
        user_input = state["user_input"]

        logger.info(f"Handling direct LLM request: {user_input}")

        try:
            # Create voice-optimized prompt
            prompt = ChatPromptTemplate.from_template(VOICE_RESPONSE_PROMPT)

            # Get LLM response
            response = self.llm.invoke(prompt.format(user_input=user_input))

            response_text = response.content.strip()

            # Ensure voice-friendly
            response_text = self._make_voice_friendly(response_text)

            state["final_response"] = response_text
            state["messages"].append(AIMessage(content=response_text))

            logger.info(f"Direct LLM response: {response_text[:100]}...")

        except Exception as e:
            logger.error(f"Error in direct LLM response: {e}", exc_info=True)
            state["final_response"] = (
                "I'm sorry, I encountered an error. Could you try asking that again?"
            )

        return state

    def _make_voice_friendly(self, text: str, max_sentences: int = 3) -> str:
        """
        Make text more voice-friendly by shortening and simplifying.

        Args:
            text: Original text
            max_sentences: Maximum number of sentences

        Returns:
            Voice-friendly version
        """
        # Remove markdown formatting
        text = text.replace("**", "").replace("*", "").replace("#", "")
        text = text.replace("```", "").replace("`", "")

        # Split into sentences
        import re

        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Limit to max_sentences
        if len(sentences) > max_sentences:
            text = ". ".join(sentences[:max_sentences]) + "."

        # Remove bullet points and convert to natural speech
        lines = text.split("\n")
        natural_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("•"):
                line = line[1:].strip()
            if line:
                natural_lines.append(line)

        text = " ".join(natural_lines)

        # Ensure not too long (approximate word limit for voice)
        words = text.split()
        if len(words) > 50:  # ~15-20 seconds of speech
            text = " ".join(words[:50]) + "..."

        return text

    def _decide_next_node(self, state: VoiceState) -> str:
        """
        Decide which node to execute next based on routing decision.
        """
        if state["route_decision"] == "AGENT":
            return "agent_handler"
        else:
            return "direct_handler"

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with persistence.
        """
        # Create workflow
        workflow = StateGraph(VoiceState)

        # Add nodes
        workflow.add_node("router", self._route_request)
        workflow.add_node("agent_handler", self._handle_agent_request)
        workflow.add_node("direct_handler", self._handle_direct_request)

        # Set entry point
        workflow.set_entry_point("router")

        # Add conditional edges from router
        workflow.add_conditional_edges(
            "router",
            self._decide_next_node,
            {"agent_handler": "agent_handler", "direct_handler": "direct_handler"},
        )

        # Both handlers end the workflow
        workflow.add_edge("agent_handler", END)
        workflow.add_edge("direct_handler", END)

        # Compile with checkpointer for persistence
        return workflow.compile(checkpointer=self.checkpointer)

    async def process_transcript(
        self,
        transcript: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a voice transcript and return a response.

        Args:
            transcript: The transcribed text from STT
            session_id: Unique session identifier for persistence
            metadata: Optional metadata (confidence, duration, etc.)

        Returns:
            Dict with:
                - response: Voice-friendly response text
                - route: How it was handled ("AGENT" or "DIRECT")
                - agent_name: Name of agent used (if applicable)
                - session_id: Session ID for tracking
        """
        logger.info(f"Processing transcript for session {session_id}: {transcript}")

        # Prepare initial state
        initial_state = {
            "messages": [HumanMessage(content=transcript)],
            "user_input": transcript,
            "route_decision": "",
            "agent_name": None,
            "final_response": "",
            "session_id": session_id,
            "metadata": metadata or {},
        }

        try:
            # Execute graph with persistence
            config = {"configurable": {"thread_id": session_id}}
            result = await self.graph.ainvoke(initial_state, config=config)

            response_data = {
                "response": result.get(
                    "final_response", "I didn't catch that. Could you say it again?"
                ),
                "route": result.get("route_decision", "UNKNOWN"),
                "agent_name": result.get("agent_name"),
                "session_id": session_id,
                "timestamp": metadata.get("timestamp") if metadata else None,
            }

            logger.info(f"Response generated: {response_data['response'][:100]}...")
            return response_data

        except Exception as e:
            logger.error(f"Error processing transcript: {e}", exc_info=True)
            return {
                "response": "I'm sorry, I had trouble processing that. Could you try again?",
                "route": "ERROR",
                "agent_name": None,
                "session_id": session_id,
                "error": str(e),
            }

    def get_conversation_history(self, session_id: str) -> list:
        """
        Retrieve conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of messages in the conversation
        """
        try:
            config = {"configurable": {"thread_id": session_id}}
            state = self.checkpointer.get(config)

            if state and "messages" in state:
                return state["messages"]

            return []

        except Exception as e:
            logger.error(f"Error retrieving history: {e}", exc_info=True)
            return []


# Convenience function for quick initialization
def create_voice_router(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    checkpoint_db_path: Optional[str] = None,
) -> VoiceRouter:
    """
    Create and initialize a VoiceRouter instance.

    Args:
        api_key: OpenAI API key (uses env if not provided)
        model: Model name (uses env if not provided)
        checkpoint_db_path: Custom checkpoint database path

    Returns:
        Initialized VoiceRouter instance
    """
    return VoiceRouter(
        api_key=api_key, model=model, checkpoint_db_path=checkpoint_db_path
    )
