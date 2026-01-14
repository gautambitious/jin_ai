"""Tools registry system for managing and discovering agent tools."""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""

    name: str
    description: str
    category: str
    tool_instance: BaseTool
    is_async: bool = False
    tags: List[str] = field(default_factory=list)


class ToolsRegistry:
    """Central registry for managing all available tools."""

    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(
        self,
        tool: BaseTool,
        category: str,
        is_async: bool = False,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: The LangChain tool instance
            category: Category for organizing tools
            is_async: Whether the tool uses async execution (Celery)
            tags: Additional tags for searching/filtering
        """
        metadata = ToolMetadata(
            name=tool.name,
            description=tool.description or "",
            category=category,
            tool_instance=tool,
            is_async=is_async,
            tags=tags or [],
        )

        self._tools[tool.name] = metadata

        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        metadata = self._tools.get(name)
        return metadata.tool_instance if metadata else None

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Get all tools in a specific category."""
        tool_names = self._categories.get(category, [])
        return [self._tools[name].tool_instance for name in tool_names]

    def get_tools_by_tags(self, tags: List[str]) -> List[BaseTool]:
        """Get all tools that match any of the given tags."""
        matching_tools = []
        for metadata in self._tools.values():
            if any(tag in metadata.tags for tag in tags):
                matching_tools.append(metadata.tool_instance)
        return matching_tools

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return [metadata.tool_instance for metadata in self._tools.values()]

    def get_async_tools(self) -> List[BaseTool]:
        """Get all tools marked as async (using Celery)."""
        return [
            metadata.tool_instance
            for metadata in self._tools.values()
            if metadata.is_async
        ]

    def list_categories(self) -> List[str]:
        """List all available categories."""
        return list(self._categories.keys())

    def search_tools(self, query: str) -> List[BaseTool]:
        """Search tools by name or description."""
        query = query.lower()
        matching_tools = []

        for metadata in self._tools.values():
            if (
                query in metadata.name.lower()
                or query in metadata.description.lower()
                or any(query in tag.lower() for tag in metadata.tags)
            ):
                matching_tools.append(metadata.tool_instance)

        return matching_tools

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a tool."""
        metadata = self._tools.get(name)
        if not metadata:
            return None

        return {
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category,
            "is_async": metadata.is_async,
            "tags": metadata.tags,
        }

    def unregister(self, name: str) -> bool:
        """Unregister a tool from the registry."""
        if name not in self._tools:
            return False

        metadata = self._tools[name]
        del self._tools[name]

        if metadata.category in self._categories:
            self._categories[metadata.category].remove(name)
            if not self._categories[metadata.category]:
                del self._categories[metadata.category]

        return True


# Global tools registry instance
tools_registry = ToolsRegistry()
