"""Agents registry system for managing and discovering agents."""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
# AgentExecutor type - using Any for compatibility with various langchain versions
from typing import Any as AgentExecutor
from langchain.tools import BaseTool


@dataclass
class AgentMetadata:
    """Metadata for a registered agent."""

    name: str
    description: str
    specialization: str
    agent_executor: AgentExecutor
    tools: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class AgentsRegistry:
    """Central registry for managing all available agents."""

    def __init__(self):
        self._agents: Dict[str, AgentMetadata] = {}
        self._specializations: Dict[str, List[str]] = {}

    def register(
        self,
        name: str,
        description: str,
        specialization: str,
        agent_executor: AgentExecutor,
        tools: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        Register an agent in the registry.

        Args:
            name: Unique name for the agent
            description: What the agent does
            specialization: Area of expertise (e.g., "web_search", "data_analysis")
            agent_executor: The LangChain AgentExecutor instance
            tools: List of tool names this agent uses
            capabilities: What the agent can do
            tags: Additional tags for searching/filtering
        """
        metadata = AgentMetadata(
            name=name,
            description=description,
            specialization=specialization,
            agent_executor=agent_executor,
            tools=tools or [],
            capabilities=capabilities or [],
            tags=tags or [],
        )

        self._agents[name] = metadata

        if specialization not in self._specializations:
            self._specializations[specialization] = []
        self._specializations[specialization].append(name)

    def get_agent(self, name: str) -> Optional[AgentExecutor]:
        """Get an agent executor by name."""
        metadata = self._agents.get(name)
        return metadata.agent_executor if metadata else None

    def get_agents_by_specialization(self, specialization: str) -> List[AgentExecutor]:
        """Get all agents with a specific specialization."""
        agent_names = self._specializations.get(specialization, [])
        return [self._agents[name].agent_executor for name in agent_names]

    def get_agents_by_capability(self, capability: str) -> List[AgentExecutor]:
        """Get all agents that have a specific capability."""
        matching_agents = []
        for metadata in self._agents.values():
            if capability.lower() in [c.lower() for c in metadata.capabilities]:
                matching_agents.append(metadata.agent_executor)
        return matching_agents

    def get_all_agents(self) -> List[AgentExecutor]:
        """Get all registered agents."""
        return [metadata.agent_executor for metadata in self._agents.values()]

    def list_specializations(self) -> List[str]:
        """List all available specializations."""
        return list(self._specializations.keys())

    def search_agents(self, query: str) -> List[AgentExecutor]:
        """Search agents by name, description, or capabilities."""
        query = query.lower()
        matching_agents = []

        for metadata in self._agents.values():
            if (
                query in metadata.name.lower()
                or query in metadata.description.lower()
                or any(query in cap.lower() for cap in metadata.capabilities)
                or any(query in tag.lower() for tag in metadata.tags)
            ):
                matching_agents.append(metadata.agent_executor)

        return matching_agents

    def get_agent_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an agent."""
        metadata = self._agents.get(name)
        if not metadata:
            return None

        return {
            "name": metadata.name,
            "description": metadata.description,
            "specialization": metadata.specialization,
            "tools": metadata.tools,
            "capabilities": metadata.capabilities,
            "tags": metadata.tags,
        }

    def list_all_agent_info(self) -> List[Dict[str, Any]]:
        """Get information about all registered agents."""
        return [
            {
                "name": metadata.name,
                "description": metadata.description,
                "specialization": metadata.specialization,
                "tools": metadata.tools,
                "capabilities": metadata.capabilities,
            }
            for metadata in self._agents.values()
        ]

    def get_agents_with_tool(self, tool_name: str) -> List[AgentExecutor]:
        """Get all agents that use a specific tool."""
        matching_agents = []
        for metadata in self._agents.values():
            if tool_name in metadata.tools:
                matching_agents.append(metadata.agent_executor)
        return matching_agents

    def unregister(self, name: str) -> bool:
        """Unregister an agent from the registry."""
        if name not in self._agents:
            return False

        metadata = self._agents[name]
        del self._agents[name]

        if metadata.specialization in self._specializations:
            self._specializations[metadata.specialization].remove(name)
            if not self._specializations[metadata.specialization]:
                del self._specializations[metadata.specialization]

        return True


# Global agents registry instance
agents_registry = AgentsRegistry()
