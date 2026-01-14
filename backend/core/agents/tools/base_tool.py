"""Base tool class with common logic."""

from typing import Optional, Dict, Any
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from abc import abstractmethod
import json


class BaseCustomTool(BaseTool):
    """
    Base class for all custom tools.

    Subclasses only need to implement the call() method with their specific logic.
    """

    def call(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool's main logic.

        Override this method in subclasses to implement tool-specific logic.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Dictionary with results
        """
        raise NotImplementedError("Subclasses must implement call() method")

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None, **kwargs
    ) -> str:
        """
        Execute the tool (called by LangChain).

        This method handles the execution and formatting.
        Subclasses should NOT override this.
        """
        try:
            output = self.call(**kwargs)
            return json.dumps(output)
        except Exception as e:
            error_output = {"error": str(e), "status": "error", "tool": self.name}
            return json.dumps(error_output)

    async def _arun(self, **kwargs) -> str:
        """
        Async version of _run.

        Subclasses should NOT override this.
        """
        return self._run(**kwargs)
