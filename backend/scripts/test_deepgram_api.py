#!/usr/bin/env python
"""Test Deepgram API key and connection."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from env_vars import DEEPGRAM_API_KEY, DEEPGRAM_STT_MODEL
from deepgram import DeepgramClient
import time

def test_api_key():
    """Test if Deepgram API key is valid."""
    print("=" * 60)
    print("Deepgram API Key Validation")
    print("=" * 60)
    
    if not DEEPGRAM_API_KEY:
        print("❌ ERROR: DEEPGRAM_API_KEY is not set in .env file")
        return False
    
    print(f"✓ API key found: {'*' * 8}{DEEPGRAM_API_KEY[-4:]}")
    print(f"✓ API key length: {len(DEEPGRAM_API_KEY)} characters")
    print(f"✓ Model: {DEEPGRAM_STT_MODEL}")
    
    return True

def test_websocket_connection():
    """Test WebSocket connection to Deepgram."""
    print("\n" + "=" * 60)
    print("Testing Deepgram WebSocket Connection")
    print("=" * 60)
    
    try:
        client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        print("✓ DeepgramClient created")
        
        # Try to create a live connection
        print(f"\nAttempting connection with model: {DEEPGRAM_STT_MODEL}")
        print("Audio params: 16000Hz, linear16, 1 channel")
        
        with client.listen.v1.connect(
            model=DEEPGRAM_STT_MODEL,
            language="en-US",
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            interim_results=True,
            smart_format=True,
            punctuate=True,
        ) as connection:
            print("✓ Connection context entered")
            
            # Set up error tracking
            error_occurred = False
            error_message = None
            
            def on_error(*args, **kwargs):
                nonlocal error_occurred, error_message
                error_occurred = True
                error_message = str(kwargs.get('error', args[0] if args else 'Unknown'))
                print(f"\n❌ ERROR received: {error_message}")
            
            def on_open(*args, **kwargs):
                print("✓ WebSocket opened")
            
            def on_close(*args, **kwargs):
                print("✓ WebSocket closed")
            
            connection.on("error", on_error)
            connection.on("open", on_open)
            connection.on("close", on_close)
            
            # Start listening
            connection.start_listening()
            print("✓ start_listening() called")
            
            # Send keepalive immediately to prevent timeout
            try:
                from deepgram.listen.v1.types import ListenV1KeepAlive
                connection.send_keep_alive(ListenV1KeepAlive(type="KeepAlive"))
                print("✓ Sent keepalive message")
            except Exception as ka_err:
                print(f"⚠️  Could not send keepalive: {ka_err}")
            
            # Wait for connection to establish or error
            print("\nWaiting for connection status...")
            time.sleep(1)
            
            if error_occurred:
                print(f"\n❌ CONNECTION FAILED")
                print(f"Error: {error_message}")
                print("\nPossible causes:")
                print("  1. Invalid API key - check at https://console.deepgram.com")
                print("  2. Model not available for your account")
                print("  3. Account billing or credit issues")
                print("  4. Network/firewall blocking connection")
                return False
            
            # Check if websocket is open
            if hasattr(connection, '_websocket'):
                ws = connection._websocket
                if hasattr(ws, 'closed'):
                    if ws.closed:
                        print(f"\n❌ WebSocket is closed")
                        if hasattr(ws, 'close_code'):
                            print(f"Close code: {ws.close_code}")
                        if hasattr(ws, 'close_reason'):
                            print(f"Close reason: {ws.close_reason}")
                        return False
                    else:
                        print("✅ WebSocket is OPEN and ready!")
                        return True
            
            print("✅ Connection appears successful!")
            return True
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n🔍 Deepgram API Test Suite\n")
    
    if not test_api_key():
        print("\n❌ API key test failed. Fix .env file and try again.")
        return 1
    
    if not test_websocket_connection():
        print("\n❌ WebSocket connection test failed.")
        print("\nTroubleshooting steps:")
        print("  1. Verify API key at https://console.deepgram.com/project//keys")
        print("  2. Check account status and billing at https://console.deepgram.com")
        print("  3. Ensure model 'nova-3' is available for your account")
        print("  4. Try a different model (e.g., 'nova-2')")
        return 1
    
    print("\n✅ All tests passed! Deepgram connection is working.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
