"""Supervisor agent using LangGraph for orchestrating multiple agents."""

from typing import TypedDict, Annotated, Sequence, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    FunctionMessage,
)
from langgraph.graph import StateGraph, END
import operator
import functools
from .agents_registry import agents_registry


class AgentState(TypedDict):
    """State shared between all agents in the graph."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    final_response: str


class SupervisorAgent:
    """
    Supervisor agent that routes tasks to specialized agents using LangGraph.
    """

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.llm = ChatOpenAI(temperature=0, model=model, api_key=api_key)
        self.graph = None
        self.agents_map = {}

    def add_agent(self, name: str, agent_executor, description: str):
        """Add a specialized agent to the supervisor."""
        self.agents_map[name] = {"executor": agent_executor, "description": description}

    def _create_supervisor_prompt(self):
        """Create the prompt for the supervisor."""
        agent_descriptions = "\n".join(
            [
                f"- {name}: {info['description']}"
                for name, info in self.agents_map.items()
            ]
        )

        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"""You are a supervisor agent managing a team of specialized agents.
            Your job is to route tasks to the most appropriate agent based on the request.
            
            Available agents:
            {agent_descriptions}
            
            Analyze the user's request and decide which agent should handle it.
            If the task is complete, respond with 'FINISH'.
            
            Response format:
            - To delegate to an agent: Respond with just the agent name (e.g., 'research_agent')
            - To finish: Respond with 'FINISH'
            """,
                ),
                MessagesPlaceholder(variable_name="messages"),
                (
                    "human",
                    "Who should handle this task? Respond with the agent name or 'FINISH'.",
                ),
            ]
        )

    def supervisor_node(self, state: AgentState):
        """Supervisor node that decides which agent to call next."""
        prompt = self._create_supervisor_prompt()
        chain = prompt | self.llm

        result = chain.invoke({"messages": state["messages"]})

        # Extract the agent name from the response
        next_agent = result.content.strip().lower()

        # Validate the agent name
        valid_agents = list(self.agents_map.keys()) + ["finish"]
        if next_agent not in valid_agents:
            # Default to first agent if invalid
            next_agent = (
                list(self.agents_map.keys())[0] if self.agents_map else "finish"
            )

        return {"next": next_agent, "messages": [result]}

    def create_agent_node(self, agent_name: str):
        """Create a node for a specific agent."""

        def agent_node(state: AgentState):
            agent_info = self.agents_map[agent_name]
            executor = agent_info["executor"]

            # Get the last message
            last_message = state["messages"][-1]

            # Extract the user's query
            if isinstance(last_message, HumanMessage):
                query = last_message.content
            else:
                # Find the last human message
                for msg in reversed(state["messages"]):
                    if isinstance(msg, HumanMessage):
                        query = msg.content
                        break
                else:
                    query = "Process the previous request"

            # Execute the agent
            result = executor.invoke({"input": query})

            # Create response message
            response = AIMessage(
                content=result.get("output", str(result)), name=agent_name
            )

            return {
                "messages": [response],
                "final_response": result.get("output", str(result)),
            }

        return agent_node

    def router(self, state: AgentState) -> str:
        """Route to the next node based on supervisor's decision."""
        next_agent = state.get("next", "finish")

        if next_agent == "finish":
            return "finish"

        return next_agent

    def build_graph(self):
        """Build the LangGraph workflow."""
        # Create the graph
        workflow = StateGraph(AgentState)

        # Add the supervisor node
        workflow.add_node("supervisor", self.supervisor_node)

        # Add agent nodes
        for agent_name in self.agents_map.keys():
            workflow.add_node(agent_name, self.create_agent_node(agent_name))

        # Add edges from agents back to supervisor
        for agent_name in self.agents_map.keys():
            workflow.add_edge(agent_name, "supervisor")

        # Add conditional edges from supervisor to agents
        workflow.add_conditional_edges(
            "supervisor",
            self.router,
            {name: name for name in self.agents_map.keys()} | {"finish": END},
        )

        # Set entry point
        workflow.set_entry_point("supervisor")

        # Compile the graph
        self.graph = workflow.compile()

        return self.graph

    def run(self, user_input: str, max_iterations: int = 5) -> str:
        """
        Run the supervisor agent with the given input.

        Args:
            user_input: The user's request
            max_iterations: Maximum number of agent calls to prevent infinite loops

        Returns:
            Final response from the agents
        """
        if not self.graph:
            self.build_graph()

        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "next": "",
            "final_response": "",
        }

        # Run the graph
        result = self.graph.invoke(initial_state)

        # Return the final response
        return result.get("final_response", "No response generated")

    async def arun(self, user_input: str, max_iterations: int = 5) -> str:
        """Async version of run."""
        if not self.graph:
            self.build_graph()

        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "next": "",
            "final_response": "",
        }

        result = await self.graph.ainvoke(initial_state)
        return result.get("final_response", "No response generated")


def create_supervisor_with_agents(
    api_key: str, model: str = "gpt-4"
) -> SupervisorAgent:
    """
    Create a supervisor agent with all registered agents.

    Args:
        api_key: OpenAI API key
        model: Model to use for the supervisor

    Returns:
        Configured SupervisorAgent instance
    """
    supervisor = SupervisorAgent(api_key=api_key, model=model)

    # Get all registered agents
    all_agent_info = agents_registry.list_all_agent_info()

    for agent_info in all_agent_info:
        agent_executor = agents_registry.get_agent(agent_info["name"])
        if agent_executor:
            supervisor.add_agent(
                name=agent_info["name"],
                agent_executor=agent_executor,
                description=agent_info["description"],
            )

    supervisor.build_graph()
    return supervisor
