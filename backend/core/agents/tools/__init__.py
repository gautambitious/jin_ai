"""Tools package with automatic registration."""

from .base_tool import BaseCustomTool
from .test_tools import TestTool

# List of all tool classes to be registered
ALL_TOOLS = [
    TestTool,
]

__all__ = ["BaseCustomTool", "TestTool", "ALL_TOOLS"]
