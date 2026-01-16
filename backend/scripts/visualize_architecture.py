#!/Users/gautam/Dev/jin_ai/env/bin/python
"""
Voice Router System - Architecture Visualization

Run this script to see a visual representation of the system flow.
"""


def print_architecture():
    """Print ASCII art architecture diagram."""

    print("\n" + "=" * 80)
    print("VOICE ROUTER SYSTEM ARCHITECTURE")
    print("=" * 80 + "\n")

    print(
        """
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         CLIENT APPLICATION                          │
    │                     (Mobile App / Web Browser)                      │
    └───────────────────────────┬─────────────────────────────────────────┘
                                │
                                │ WebSocket Connection
                                │ ws://server/ws/stt/session_id/
                                ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    STT WEBSOCKET CONSUMER                           │
    │                    (stt_consumer.py)                                │
    │                                                                     │
    │  ┌────────────────┐                                                │
    │  │ Receive Audio  │  ◄── Binary audio chunks from client          │
    │  └────────┬───────┘                                                │
    │           │                                                         │
    │           ▼                                                         │
    │  ┌────────────────┐                                                │
    │  │  Deepgram STT  │  ── Transcribe audio to text                  │
    │  └────────┬───────┘                                                │
    │           │                                                         │
    │           ▼                                                         │
    │  ┌────────────────┐                                                │
    │  │  Get Final     │  ── Wait for is_final=true                    │
    │  │  Transcript    │                                                │
    │  └────────┬───────┘                                                │
    │           │                                                         │
    │           │ Transcript: "What is the capital of India?"            │
    │           ▼                                                         │
    │  ┌────────────────────────────────────┐                           │
    │  │      Call Voice Router             │                           │
    │  │  router.process_transcript()       │                           │
    │  └────────────┬───────────────────────┘                           │
    └───────────────┼───────────────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        VOICE ROUTER                                 │
    │                    (voice_router.py)                                │
    │                   [LangGraph Workflow]                              │
    │                                                                     │
    │  ┌─────────────────────────────────────────────────────┐           │
    │  │  STEP 1: Route Decision (LLM-based)                 │           │
    │  │  ┌─────────────────────────────────────┐            │           │
    │  │  │ Analyze:                             │            │           │
    │  │  │  • User transcript                   │            │           │
    │  │  │  • Available agents & capabilities   │            │           │
    │  │  │  • Conversation history              │            │           │
    │  │  └─────────────────────────────────────┘            │           │
    │  │                    │                                 │           │
    │  │                    ▼                                 │           │
    │  │         ┌──────────────────────┐                    │           │
    │  │         │  Routing Decision     │                    │           │
    │  │         └──────────┬────────────┘                    │           │
    │  │                    │                                 │           │
    │  └────────────────────┼─────────────────────────────────┘           │
    │                       │                                             │
    │         ┌─────────────┴─────────────┐                              │
    │         │                           │                              │
    │         ▼                           ▼                              │
    │  ┌────────────────┐        ┌────────────────┐                     │
    │  │ AGENT ROUTE    │        │ DIRECT ROUTE   │                     │
    │  │ (Specialized)  │        │ (General LLM)  │                     │
    │  └────────┬───────┘        └────────┬───────┘                     │
    │           │                         │                              │
    │           ▼                         ▼                              │
    │  ┌─────────────────────────────────────────┐                      │
    │  │  STEP 2: Execute                        │                      │
    │  │  ┌──────────────┐   ┌─────────────────┐│                      │
    │  │  │ Call Agent   │   │ Call OpenAI LLM ││                      │
    │  │  │ with Tools   │   │ with Prompt     ││                      │
    │  │  └──────────────┘   └─────────────────┘│                      │
    │  └─────────────────────────────────────────┘                      │
    │           │                         │                              │
    │           └──────────┬──────────────┘                              │
    │                      ▼                                             │
    │  ┌─────────────────────────────────────────┐                      │
    │  │  STEP 3: Voice Optimization             │                      │
    │  │  • Remove markdown                       │                      │
    │  │  • Limit to 3 sentences                  │                      │
    │  │  • Natural speech patterns               │                      │
    │  │  • Max 50 words                          │                      │
    │  └─────────────────────────────────────────┘                      │
    │                      │                                             │
    │                      ▼                                             │
    │  ┌─────────────────────────────────────────┐                      │
    │  │  STEP 4: Persist to SQLite              │                      │
    │  │  • Save messages                         │                      │
    │  │  • Update conversation state             │                      │
    │  │  • Return response                       │                      │
    │  └─────────────────────────────────────────┘                      │
    └────────────────────────┬────────────────────────────────────────────┘
                             │
                             │ Response: {
                             │   "response": "New Delhi is the capital.",
                             │   "route": "DIRECT",
                             │   "agent_name": null
                             │ }
                             ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                  BACK TO STT CONSUMER                               │
    │  • Receives response from Voice Router                              │
    │  • Sends to client via WebSocket                                    │
    │  • Client plays response with TTS                                   │
    └─────────────────────────────────────────────────────────────────────┘
    """
    )

    print("\n" + "=" * 80)
    print("ROUTING DECISION LOGIC")
    print("=" * 80 + "\n")

    print(
        """
    ┌────────────────────────────────────────────────────────┐
    │              User Transcript Input                     │
    └────────────────────┬───────────────────────────────────┘
                         │
                         ▼
            ┌─────────────────────────┐
            │  Check Available Agents │
            └────────────┬────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Any Agent Matches?  │
              └──────────┬───────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
           YES                       NO
            │                         │
            ▼                         ▼
    ┌────────────────┐       ┌────────────────┐
    │ AGENT Route    │       │ DIRECT Route   │
    │                │       │                │
    │ Examples:      │       │ Examples:      │
    │ • Portfolio    │       │ • General Q&A  │
    │ • Research     │       │ • Simple math  │
    │ • Travel       │       │ • Jokes        │
    │ • Shopping     │       │ • Facts        │
    └────────────────┘       └────────────────┘
    """
    )

    print("\n" + "=" * 80)
    print("DATA FLOW EXAMPLE")
    print("=" * 80 + "\n")

    print(
        """
    Query: "What is the capital of India?"
    
    [1] Client Records Audio
         ↓
    [2] Sends via WebSocket → binary chunks
         ↓
    [3] STT Consumer → Deepgram API
         ↓
    [4] Transcript: "What is the capital of India?"
         ↓
    [5] Voice Router Analysis
         • Check agents: None match general knowledge
         • Decision: DIRECT to LLM
         ↓
    [6] OpenAI LLM Call
         • Prompt: "You are a voice assistant. Answer briefly..."
         • Response: "The capital of India is New Delhi, which has 
                      been the capital since 1947. It's located in 
                      northern India."
         ↓
    [7] Voice Optimization
         • Original: 3 sentences, 25 words ✓
         • Remove markdown: None found ✓
         • Natural speech: Already conversational ✓
         • Final: "The capital of India is New Delhi."
         ↓
    [8] Persist to SQLite
         • Session: session_123
         • Messages: [HumanMessage, AIMessage]
         ↓
    [9] Return to Client
         • type: "agent_response"
         • response: "The capital of India is New Delhi."
         • route: "DIRECT"
         ↓
    [10] Client TTS Speaks: "The capital of India is New Delhi."
    
    Total Time: ~3-5 seconds
    """
    )

    print("\n" + "=" * 80)
    print("PERSISTENCE STRUCTURE")
    print("=" * 80 + "\n")

    print(
        """
    SQLite Database: /tmp/voice_router_checkpoints.db
    
    ┌───────────────────────────────────────────────────────────┐
    │  Thread ID: session_123                                   │
    ├───────────────────────────────────────────────────────────┤
    │                                                           │
    │  Message 1: [HumanMessage]                                │
    │    "What is the capital of India?"                        │
    │                                                           │
    │  Message 2: [SystemMessage]                               │
    │    "Routing: DIRECT"                                      │
    │                                                           │
    │  Message 3: [AIMessage]                                   │
    │    "The capital of India is New Delhi."                   │
    │                                                           │
    │  Message 4: [HumanMessage]                                │
    │    "What about its population?"                           │
    │                                                           │
    │  Message 5: [SystemMessage]                               │
    │    "Routing: DIRECT"                                      │
    │                                                           │
    │  Message 6: [AIMessage]                                   │
    │    "New Delhi has about 33 million people."               │
    │                                                           │
    └───────────────────────────────────────────────────────────┘
    
    Benefits:
    • Resume conversations after disconnect
    • Context-aware follow-up questions
    • Audit trail for debugging
    • Multi-turn dialogue support
    """
    )


def print_code_locations():
    """Print file locations and key functions."""

    print("\n" + "=" * 80)
    print("KEY CODE LOCATIONS")
    print("=" * 80 + "\n")

    files = [
        {
            "path": "core/agents/voice_router.py",
            "purpose": "Core routing logic",
            "key_functions": [
                "VoiceRouter.process_transcript()",
                "_route_request()",
                "_handle_agent_request()",
                "_handle_direct_request()",
                "_make_voice_friendly()",
            ],
        },
        {
            "path": "core/agents/ws/stt_consumer.py",
            "purpose": "WebSocket integration",
            "key_functions": [
                "on_transcript() callback",
                "router.process_transcript() call",
                "agent_response message send",
            ],
        },
        {
            "path": "core/agents/orchestrator.py",
            "purpose": "Agent execution",
            "key_functions": ["execute(voice_mode=True)", "_make_voice_friendly()"],
        },
        {
            "path": "scripts/test_voice_router.py",
            "purpose": "Testing & validation",
            "key_functions": ["test_voice_router()", "Test cases for routing"],
        },
    ]

    for file_info in files:
        print(f"📁 {file_info['path']}")
        print(f"   Purpose: {file_info['purpose']}")
        print("   Key Functions:")
        for func in file_info["key_functions"]:
            print(f"     • {func}")
        print()


def print_message_flow():
    """Print WebSocket message flow."""

    print("\n" + "=" * 80)
    print("WEBSOCKET MESSAGE FLOW")
    print("=" * 80 + "\n")

    print(
        """
    CLIENT → SERVER
    ───────────────
    
    1. Connect
       ws://localhost:8001/ws/stt/session_123/
    
    2. Start Transcription
       {
         "type": "start",
         "config": {
           "language": "en-US",
           "encoding": "linear16",
           "sample_rate": 24000
         }
       }
    
    3. Send Audio Chunks
       [Binary data] [Binary data] [Binary data] ...
    
    4. Stop (optional)
       {
         "type": "stop"
       }
    
    
    SERVER → CLIENT
    ───────────────
    
    1. Connection Confirmed
       {
         "type": "connected",
         "session_id": "session_123",
         "message": "Ready to receive audio"
       }
    
    2. Started Confirmation
       {
         "type": "started",
         "config": {...}
       }
    
    3. Interim Transcripts
       {
         "type": "transcript",
         "text": "What is the",
         "is_final": false,
         "confidence": 0.85
       }
    
    4. Final Transcript
       {
         "type": "transcript",
         "text": "What is the capital of India?",
         "is_final": true,
         "confidence": 0.95
       }
    
    5. Agent/LLM Response (NEW!)
       {
         "type": "agent_response",
         "response": "The capital of India is New Delhi.",
         "route": "DIRECT",
         "agent_name": null,
         "original_transcript": "What is the capital of India?",
         "session_id": "session_123"
       }
    
    6. Error (if any)
       {
         "type": "error",
         "message": "Error description"
       }
    """
    )


if __name__ == "__main__":
    print_architecture()
    print_code_locations()
    print_message_flow()

    print("\n" + "=" * 80)
    print("Run the test:")
    print("  python scripts/test_voice_router.py")
    print("=" * 80 + "\n")
