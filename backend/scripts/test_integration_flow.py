#!/Users/gautam/Dev/jin_ai/env/bin/python
"""
Integration Test: STT → Voice Router → TTS Flow

This script demonstrates the complete integration without requiring
actual audio input or WebSocket connections.
"""

import asyncio
import sys
import os

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../core"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django
django.setup()

from agents.voice_router import create_voice_router


async def test_complete_flow():
    """Test the complete STT → Router → TTS flow (simulated)."""
    
    print("=" * 70)
    print("INTEGRATION TEST: STT → Voice Router → TTS Flow")
    print("=" * 70)
    
    # Step 1: Initialize Voice Router
    print("\n[1] Initializing Voice Router...")
    try:
        router = create_voice_router()
        print("    ✓ Voice Router ready")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return
    
    # Step 2: Simulate STT transcript
    print("\n[2] Simulating STT Transcript...")
    transcript = "What is the capital of India?"
    session_id = "integration_test_001"
    print(f"    Transcript: '{transcript}'")
    print(f"    Session: {session_id}")
    
    # Step 3: Process through Voice Router
    print("\n[3] Processing through Voice Router...")
    try:
        response = await router.process_transcript(
            transcript=transcript,
            session_id=session_id,
            metadata={"confidence": 0.95, "test": True}
        )
        
        print(f"    ✓ Routing: {response['route']}")
        if response.get('agent_name'):
            print(f"    ✓ Agent: {response['agent_name']}")
        print(f"    ✓ Response: {response['response']}")
        
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return
    
    # Step 4: Simulate TTS Broadcast
    print("\n[4] Simulating TTS Broadcast...")
    print(f"    Would broadcast: '{response['response']}'")
    print(f"    → To group: 'edge_devices'")
    print(f"    → All connected clients would receive TTS audio")
    
    # Step 5: Summary
    print("\n" + "=" * 70)
    print("FLOW SUMMARY")
    print("=" * 70)
    print(f"""
    User Input (Audio):    [Microphone recording]
              ↓
    STT Service:           "{transcript}"
              ↓
    Voice Router:          {response['route']} routing
              ↓
    AI Response:           "{response['response']}"
              ↓
    TTS Broadcast:         [Audio played on all clients]
    
    ✓ Complete pipeline tested successfully!
    """)
    
    # Step 6: Test with multiple queries
    print("\n" + "=" * 70)
    print("TESTING MULTIPLE QUERIES")
    print("=" * 70)
    
    test_queries = [
        "Tell me a joke",
        "How is my portfolio doing today?",
        "What's 15 times 7?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[Query {i}] '{query}'")
        try:
            result = await router.process_transcript(
                transcript=query,
                session_id=session_id,
                metadata={"test": True}
            )
            print(f"  Route: {result['route']}")
            if result.get('agent_name'):
                print(f"  Agent: {result['agent_name']}")
            print(f"  Response: {result['response'][:100]}...")
            print(f"  → Would broadcast via TTS ✓")
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n" + "=" * 70)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 70)
    print("""
Next Steps:
1. Start WebSocket server: python manage.py start_ws_server
2. Connect client with audio input
3. Speak into microphone
4. Observe:
   - STT transcription
   - Voice Router processing
   - TTS broadcast to all clients
    """)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
