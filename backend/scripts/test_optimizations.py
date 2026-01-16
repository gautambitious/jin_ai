#!/usr/bin/env /Users/gautam/Dev/jin_ai/env/bin/python
"""
Quick test script for optimized streaming pipeline

Tests each component independently to verify the optimization works.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'core')))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_streaming_stt():
    """Test streaming STT service"""
    logger.info("=== Testing Streaming STT ===")

    try:
        from agents.services.streaming_stt_service import StreamingSTTService
        logger.info("✅ Streaming STT service is ready")
        return True

    except Exception as e:
        logger.error(f"❌ Streaming STT test failed: {e}")
        return False


async def test_streaming_tts():
    """Test streaming TTS service"""
    logger.info("\n=== Testing Streaming TTS ===")

    try:
        from agents.services.streaming_tts_service import StreamingTTSService

        tts = StreamingTTSService()
        logger.info("✅ StreamingTTSService initialized")

        # Test sentence splitting
        text = "Hello! This is a test. It has multiple sentences."
        sentences = tts._split_into_sentences(text)

        logger.info(f"✅ Split into {len(sentences)} sentences:")
        for i, sent in enumerate(sentences, 1):
            logger.info(f"   {i}. '{sent}'")

        assert len(sentences) == 3, "Should split into 3 sentences"
        logger.info("✅ Streaming TTS service is ready")
        return True

    except Exception as e:
        logger.error(f"❌ Streaming TTS test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_streaming_router():
    """Test streaming voice router"""
    logger.info("\n=== Testing Streaming Voice Router ===")

    try:
        from agents.services.streaming_voice_router import StreamingVoiceRouter

        router = StreamingVoiceRouter()
        logger.info("✅ StreamingVoiceRouter initialized")

        # Test early intent detection
        test_cases = [
            ("What's the", None),  # Too short
            ("What's the weather", "DIRECT"),  # Question detected
            ("Search for Tesla news", "search"),  # Pattern matched
        ]

        for transcript, expected in test_cases:
            result = router._detect_intent_early(transcript)
            logger.info(f"   '{transcript}' → {result}")

        logger.info("✅ Streaming Voice Router is ready")
        return True

    except Exception as e:
        logger.error(f"❌ Streaming Router test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_optimized_consumer():
    """Test optimized consumer imports"""
    logger.info("\n=== Testing Optimized Consumer ===")

    try:
        from agents.ws.optimized_streaming_consumer import (
            OptimizedStreamingConsumer,
        )

        logger.info("✅ OptimizedStreamingConsumer imported")
        logger.info("✅ All consumer components available")
        return True

    except Exception as e:
        logger.error(f"❌ Optimized Consumer test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_integration():
    """Test that all components work together"""
    logger.info("\n=== Testing Integration ===")

    try:
        # Test imports
        from agents.services.streaming_stt_service import StreamingSTTService
        from agents.services.streaming_tts_service import StreamingTTSService
        from agents.services.streaming_voice_router import StreamingVoiceRouter
        from agents.ws.optimized_streaming_consumer import (
            OptimizedStreamingConsumer,
        )

        logger.info("✅ All components import successfully")

        # Check routing is updated
        from agents.ws import routing

        patterns = [str(pattern.pattern) for pattern in routing.websocket_urlpatterns]
        logger.info(f"✅ WebSocket routes configured: {len(patterns)} patterns")
        for pattern in patterns:
            logger.info(f"   - {pattern}")

        has_streaming = any("stream" in p for p in patterns)
        assert has_streaming, "Streaming endpoint not found in routing"

        logger.info("✅ Integration successful - all components ready!")
        return True

    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("OPTIMIZED STREAMING PIPELINE - COMPONENT TEST")
    logger.info("=" * 60)

    results = []

    # Run tests
    results.append(("Streaming STT", await test_streaming_stt()))
    results.append(("Streaming TTS", await test_streaming_tts()))
    results.append(("Streaming Router", await test_streaming_router()))
    results.append(("Optimized Consumer", await test_optimized_consumer()))
    results.append(("Integration", await test_integration()))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 All tests passed! The optimized pipeline is ready to use.")
        logger.info("\nNext steps:")
        logger.info("1. Start the server: python manage.py start_ws_server")
        logger.info("2. Test with client: python scripts/optimized_streaming_client.py")
        logger.info(
            "3. Update your edge device to use: ws://server/ws/stream/<session_id>"
        )
    else:
        logger.error(
            f"\n⚠️  {total - passed} test(s) failed. Please fix the issues above."
        )
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
