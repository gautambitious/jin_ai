#!/usr/bin/env /Users/gautam/Dev/jin_ai/env/bin/python
"""Test Deepgram WebSocket streaming API to understand the correct imports."""

import asyncio
from deepgram import DeepgramClient
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from env_vars import DEEPGRAM_API_KEY


async def main():
    try:
        # Create client (from documentation example)
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        
        print("✅ DeepgramClient created")
        print(f"   Client type: {type(deepgram)}")
        print(f"   Has listen attr: {hasattr(deepgram, 'listen')}")
        
        if hasattr(deepgram, 'listen'):
            listen = deepgram.listen
            print(f"   Listen type: {type(listen)}")
            print(f"   Listen attrs: {[x for x in dir(listen) if not x.startswith('_')]}")
            
            # Check v1
            if hasattr(listen, 'v1'):
                v1 = listen.v1
                print(f"   v1 type: {type(v1)}")
                print(f"   v1 attrs: {[x for x in dir(v1) if not x.startswith('_')]}")
                
                # Try connect (from docs - it's a context manager)
                if hasattr(v1, 'connect'):
                    print(f"   ✅ Has connect method")
                    try:
                        # Use as async context manager (from Python docs)
                        with deepgram.listen.v1.connect(model="nova-3", interim_results=True) as connection:
                            print(f"   Connection type: {type(connection)}")
                            print(f"   Connection attrs: {[x for x in dir(connection) if not x.startswith('_')][:40]}")
                            
                            # Check for methods from docs
                            if hasattr(connection, 'on'):
                                print(f"   ✅ Has 'on' method for event handlers")
                            if hasattr(connection, 'start_listening'):
                                print(f"   ✅ Has 'start_listening' method")
                            if hasattr(connection, 'send_media'):
                                print(f"   ✅ Has 'send_media' method")
                                
                    except Exception as e:
                        print(f"   ⚠️  Connection error: {e}")
                        import traceback
                        traceback.print_exc()
                    
        print("\n✅ Deepgram WebSocket API structure discovered")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
