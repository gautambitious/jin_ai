"""Agents package with automatic registration."""

from .base_agent import BaseCustomAgent
from .test_agent import TestAgent

# List of all agent classes to be registered
ALL_AGENTS = [
    TestAgent,
]

__all__ = ["BaseCustomAgent", "TestAgent", "ALL_AGENTS"]
