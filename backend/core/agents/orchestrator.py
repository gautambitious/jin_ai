"""Main orchestration module to initialize and run the agent system."""

from typing import Optional
from .tools_registry import tools_registry
from .agents_registry import agents_registry
from .tools import ALL_TOOLS
from .agents import ALL_AGENTS
from langchain_openai import ChatOpenAI
from ..env_vars import OPENAI_API_KEY, OPENAI_MODEL


class AgentSystem:
    """
    Main class to initialize and manage the entire agent system.
    """

    def __init__(
        self, openai_api_key: Optional[str] = None, model: Optional[str] = None
    ):
        """
        Initialize the agent system.

        Args:
            openai_api_key: OpenAI API key (reads from env if not provided)
            model: Model to use for agents (reads from env if not provided)
        """
        self.api_key = openai_api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY env variable or pass it to constructor."
            )

        self.model = model or OPENAI_MODEL
        self.llm = ChatOpenAI(temperature=0, model=self.model, api_key=self.api_key)

        # Initialize the system
        self._register_tools()
        self._register_agents()

    def _register_tools(self):
        """Register all available tools in the registry."""
        for tool_class in ALL_TOOLS:
            tool_instance = tool_class()

            # Determine category from tool name or class
            category = getattr(tool_class, "category", "general")
            is_async = getattr(tool_class, "is_async", True)
            tags = getattr(tool_class, "tags", [])

            tools_registry.register(
                tool=tool_instance, category=category, is_async=is_async, tags=tags
            )

    def _register_agents(self):
        """Create and register all specialized agents."""
        for agent_class in ALL_AGENTS:
            # Create agent instance
            agent_instance = agent_class(llm=self.llm)

            # Get agent metadata
            agent_name = agent_class.get_name()
            agent_description = agent_class.get_description()

            # Get tool names from the agent
            tool_names = [tool.name for tool in agent_instance.tools]

            # Determine specialization from agent name
            specialization = getattr(agent_class, "specialization", "general")
            capabilities = getattr(agent_class, "capabilities", [])
            tags = getattr(agent_class, "tags", [])

            agents_registry.register(
                name=agent_name,
                description=agent_description,
                specialization=specialization,
                agent_executor=agent_instance.get_executor(),
                tools=tool_names,
                capabilities=capabilities,
                tags=tags,
            )

    def execute(self, agent_name: str, command: str) -> str:
        """
        Execute a command using a specific agent.

        Args:
            agent_name: Name of the agent to use
            command: Text command from the user

        Returns:
            Response from the agent
        """
        agent_executor = agents_registry.get_agent(agent_name)
        if not agent_executor:
            raise ValueError(f"Agent '{agent_name}' not found")

        result = agent_executor.invoke({"input": command})
        return result.get("output", str(result))

    def get_available_tools(self):
        """Get list of all available tools."""
        return tools_registry.get_all_tools()

    def get_available_agents(self):
        """Get list of all available agents."""
        return agents_registry.list_all_agent_info()

    def get_tool_info(self, tool_name: str):
        """Get information about a specific tool."""
        return tools_registry.get_tool_info(tool_name)

    def get_agent_info(self, agent_name: str):
        """Get information about a specific agent."""
        return agents_registry.get_agent_info(agent_name)

    def search_tools(self, query: str):
        """Search for tools by name or description."""
        return tools_registry.search_tools(query)

    def search_agents(self, query: str):
        """Search for agents by name or capabilities."""
        return agents_registry.search_agents(query)


def initialize_agent_system(
    openai_api_key: Optional[str] = None, model: Optional[str] = None
) -> AgentSystem:
    """
    Convenience function to initialize the agent system.

    Args:
        openai_api_key: OpenAI API key (reads from OPENAI_API_KEY env if not provided)
        model: Model to use (reads from OPENAI_MODEL env if not provided, defaults to gpt-4)

    Returns:
        Initialized AgentSystem instance
    """
    return AgentSystem(openai_api_key=openai_api_key, model=model)
