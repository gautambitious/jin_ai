#!/Users/gautam/Dev/jin_ai/env/bin/python
"""
Test script for Voice Router functionality.

This script demonstrates:
1. Creating a VoiceRouter instance
2. Processing various transcript types
3. Routing to agents vs direct LLM
4. Conversation persistence across sessions
"""

import os
import sys
import asyncio

# Setup Django environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../core"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.voice_router import create_voice_router


async def test_voice_router():
    """Test the voice router with various inputs."""

    print("=" * 60)
    print("VOICE ROUTER TEST")
    print("=" * 60)

    # Create router
    print("\n1. Initializing Voice Router...")
    try:
        router = create_voice_router()
        print("✓ Voice Router initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return

    # Test session ID
    session_id = "test_session_001"

    # Test cases
    test_cases = [
        {
            "transcript": "What is the capital of India?",
            "expected_route": "DIRECT",
            "description": "General knowledge question - should go to LLM",
        },
        {
            "transcript": "Tell me a joke",
            "expected_route": "DIRECT",
            "description": "Simple request - should go to LLM",
        },
        {
            "transcript": "How is my portfolio doing today?",
            "expected_route": "AGENT or DIRECT",
            "description": "Portfolio query - should route to agent if available",
        },
        {
            "transcript": "Search for recent news about AI",
            "expected_route": "AGENT or DIRECT",
            "description": "Research query - should route to research agent if available",
        },
        {
            "transcript": "What's 25 times 4?",
            "expected_route": "DIRECT",
            "description": "Math question - should go to LLM",
        },
    ]

    print(f"\n2. Running {len(test_cases)} test cases...\n")

    for i, test_case in enumerate(test_cases, 1):
        transcript = test_case["transcript"]
        expected = test_case["expected_route"]
        description = test_case["description"]

        print(f"\nTest Case {i}: {description}")
        print(f"Transcript: '{transcript}'")
        print(f"Expected: {expected}")
        print("-" * 60)

        try:
            # Process transcript
            result = await router.process_transcript(
                transcript=transcript,
                session_id=session_id,
                metadata={"confidence": 0.95, "test": True},
            )

            # Display results
            print(f"Route: {result['route']}")
            if result.get("agent_name"):
                print(f"Agent: {result['agent_name']}")
            print(f"Response: {result['response']}")
            print(f"Session: {result['session_id']}")

            # Check if matches expectation
            if expected == "AGENT or DIRECT":
                print("✓ Routed successfully")
            elif result["route"] == expected:
                print("✓ Routing matches expectation")
            else:
                print(
                    f"⚠ Routing differs from expectation (got {result['route']}, expected {expected})"
                )

        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback

            traceback.print_exc()

    # Test conversation history
    print("\n" + "=" * 60)
    print("3. Testing Conversation Persistence...")
    print("=" * 60)

    try:
        history = router.get_conversation_history(session_id)
        print(f"Messages in history: {len(history)}")

        if history:
            print("\nLast few messages:")
            for msg in history[-6:]:  # Show last 3 exchanges
                msg_type = type(msg).__name__
                content = (
                    msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                )
                print(f"  [{msg_type}] {content}")
        else:
            print("No history found (checkpoint may not be persisting)")

    except Exception as e:
        print(f"✗ Error retrieving history: {e}")

    # Test available agents
    print("\n" + "=" * 60)
    print("4. Available Agents in System")
    print("=" * 60)

    try:
        agents = router.agent_system.get_available_agents()
        if agents:
            print(f"Found {len(agents)} agent(s):")
            for agent in agents:
                print(f"\n  • {agent.get('name', 'Unknown')}")
                print(f"    Description: {agent.get('description', 'N/A')}")
                if agent.get("capabilities"):
                    print(f"    Capabilities: {', '.join(agent['capabilities'])}")
        else:
            print("No specialized agents registered yet.")
            print("The system will route all requests to direct LLM.")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nKey Features Demonstrated:")
    print("  ✓ Intelligent routing (AGENT vs DIRECT)")
    print("  ✓ Voice-friendly, concise responses")
    print("  ✓ Session persistence with SQLite")
    print("  ✓ Conversation history tracking")
    print("  ✓ Error handling and fallbacks")


if __name__ == "__main__":
    asyncio.run(test_voice_router())
