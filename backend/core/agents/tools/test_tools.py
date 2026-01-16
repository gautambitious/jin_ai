"""Test tools implementation."""

from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from .base_tool import BaseCustomTool


class TestToolInput(BaseModel):
    """Input for test tool."""

    message: str = Field(description="Message to process")


class TestTool(BaseCustomTool):
    """A test tool for demonstration purposes."""

    name: str = "test_tool"
    description: str = (
        "A simple test tool that echoes back the input message with additional info."
    )
    args_schema: Optional[Type[BaseModel]] = TestToolInput

    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Execute test tool logic.

        Args:
            **kwargs: Contains 'message' - Message to process

        Returns:
            Dictionary with processed result
        """
        message = kwargs.get("message", "")
        return {
            "input": message,
            "output": f"Processed: {message}",
            "status": "success",
            "tool": "test_tool",
        }
