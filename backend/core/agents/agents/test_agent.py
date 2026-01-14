"""Test agent implementation."""

from typing import List
from langchain_core.tools import BaseTool
from .base_agent import BaseCustomAgent


class TestAgent(BaseCustomAgent):
    """A test agent for demonstration purposes."""

    PROMPT_TEMPLATE = """You are a helpful AI assistant.
You have access to various tools to help users with their tasks.
Always be clear, concise, and helpful in your responses.

Your goal is to assist users effectively using the tools available to you."""

    def get_tools(self) -> List[BaseTool]:
        """
        Define tools for test agent.

        Returns:
            List of tools available to this agent
        """
        # Import tools here to avoid circular imports
        from agents.tools.test_tools import TestTool

        return [TestTool()]
