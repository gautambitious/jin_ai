"""Base agent class with common logic."""

from typing import Dict, Any, List, Optional
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.runnables import Runnable
from abc import ABC, abstractmethod


class BaseCustomAgent(ABC):
    """
    Base class for all custom agents.

    Subclasses only need to:
    1. Define PROMPT_TEMPLATE as a class variable
    2. Implement get_tools() to return the list of tools
    """

    PROMPT_TEMPLATE: str = ""  # Override in subclasses

    def __init__(self, llm: ChatOpenAI, tools: List[BaseTool] = None):
        """
        Initialize the agent.

        Args:
            llm: Language model instance
            tools: Optional list of tools (if None, get_tools() will be called)
        """
        self.llm = llm
        self.tools = tools if tools is not None else self.get_tools()
        self.prompt = self.get_prompt()
        self.executor = self._create_executor() if self.tools else None

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """
        Define tools for this agent.

        Override this method in subclasses to specify which tools the agent uses.

        Returns:
            List of BaseTool instances
        """
        raise NotImplementedError("Subclasses must implement get_tools()")

    def get_prompt(self) -> ChatPromptTemplate:
        """
        Create the prompt template for this agent.

        Uses the PROMPT_TEMPLATE class variable.
        Subclasses can override if custom prompt structure is needed.

        Returns:
            ChatPromptTemplate instance
        """
        if not self.PROMPT_TEMPLATE:
            raise ValueError(f"{self.__class__.__name__} must define PROMPT_TEMPLATE")

        return ChatPromptTemplate.from_messages(
            [
                ("system", self.PROMPT_TEMPLATE),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

    def _create_executor(self) -> Runnable:
        """
        Create the agent executor.

        Subclasses should NOT override this.

        Returns:
            Runnable agent instance
        """
        # Convert prompt to system message if needed
        system_message = self.PROMPT_TEMPLATE
        
        # Use create_agent with new signature
        agent = create_agent(
            self.llm,
            self.tools,
            system_prompt=system_message
        )
        return agent

    def execute(self, user_input: str) -> Dict[str, Any]:
        """
        Execute the agent with user input.

        Args:
            user_input: User's query or command

        Returns:
            Agent's response dictionary
        """
        if not self.executor:
            return {"error": "No tools available for this agent", "output": "No tools configured"}

        try:
            result = self.executor.invoke({"input": user_input})
            return result if isinstance(result, dict) else {"output": str(result)}
        except Exception as e:
            return {"error": str(e), "output": f"Error: {str(e)}"}

    def get_executor(self) -> Optional[Runnable]:
        """
        Get the agent executor for registry.

        Returns:
            Runnable agent instance
        """
        return self.executor

    @classmethod
    def get_name(cls) -> str:
        """
        Get the agent's name for registration.

        Returns:
            Agent name (class name in snake_case)
        """
        # Convert CamelCase to snake_case
        name = cls.__name__
        return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip(
            "_"
        )

    @classmethod
    def get_description(cls) -> str:
        """
        Get the agent's description from docstring.

        Returns:
            Agent description
        """
        return cls.__doc__.strip() if cls.__doc__ else f"{cls.__name__} agent"
