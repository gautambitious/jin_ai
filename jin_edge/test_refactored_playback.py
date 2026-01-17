"""
Test script for refactored audio playback system.
Validates click-free playback with fade-in/fade-out.
"""

import asyncio
import numpy as np
import logging
from audio.player import AudioPlayer, PlaybackState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_tone(frequency: int, duration_ms: int, sample_rate: int = 16000) -> bytes:
    """Generate a sine wave tone."""
    duration_sec = duration_ms / 1000.0
    num_samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, dtype=np.float32)
    
    # Generate sine wave
    amplitude = 8000  # Safe amplitude for int16
    tone = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # Convert to int16
    return tone.astype(np.int16).tobytes()


async def test_session_playback():
    """Test session-based playback with multiple chunks."""
    logger.info("\n=== Test 1: Session-based playback ===")
    
    player = AudioPlayer(
        sample_rate=16000,
        channels=1,
        buffering_chunks=2,
        fade_samples=100,
    )
    
    try:
        await player.start()
        logger.info("✓ Player started")
        
        # Begin session
        await player.begin_session()
        logger.info("✓ Session started")
        assert player.is_session_active, "Session should be active"
        assert player.state == PlaybackState.IDLE, "Should start in IDLE"
        
        # Feed multiple chunks (20ms each)
        chunk_20ms = generate_tone(440, 20)  # A4 note
        
        for i in range(10):  # 200ms total
            success = await player.feed(chunk_20ms)
            assert success, f"Failed to feed chunk {i}"
            await asyncio.sleep(0.01)  # Small delay to simulate network
        
        logger.info("✓ Fed 10 chunks (200ms)")
        
        # Wait for buffering to complete and playback to start
        await asyncio.sleep(0.1)
        logger.info(f"✓ State: {player.state}")
        
        # End session
        await player.end_session()
        logger.info("✓ Session ended")
        
        # Wait for playback to complete
        await asyncio.sleep(0.5)
        assert player.state == PlaybackState.IDLE, "Should return to IDLE"
        
        logger.info("✅ Test 1 passed\n")
        
    finally:
        await player.stop()


async def test_continuous_playback():
    """Test continuous playback across multiple chunks (no clicks)."""
    logger.info("\n=== Test 2: Continuous playback (no clicks) ===")
    
    player = AudioPlayer(
        sample_rate=16000,
        channels=1,
        buffering_chunks=2,
        fade_samples=100,
    )
    
    try:
        await player.start()
        await player.begin_session()
        
        # Feed chunks continuously to simulate TTS streaming
        chunk_20ms = generate_tone(440, 20)
        
        for i in range(50):  # 1 second of audio
            success = await player.feed(chunk_20ms)
            assert success, f"Failed to feed chunk {i}"
            await asyncio.sleep(0.015)  # Slightly slower than real-time
        
        logger.info("✓ Fed 50 chunks (1 second) continuously")
        
        # End session and wait for drain
        await player.end_session()
        await asyncio.sleep(0.5)
        
        logger.info("✅ Test 2 passed (listen for clicks)\n")
        
    finally:
        await player.stop()


async def test_interrupt():
    """Test interruption during playback."""
    logger.info("\n=== Test 3: Interrupt during playback ===")
    
    player = AudioPlayer(
        sample_rate=16000,
        channels=1,
        buffering_chunks=2,
        fade_samples=100,
    )
    
    try:
        await player.start()
        await player.begin_session()
        
        # Feed initial chunks
        chunk_20ms = generate_tone(440, 20)
        for i in range(5):
            await player.feed(chunk_20ms)
            await asyncio.sleep(0.01)
        
        logger.info("✓ Playback started")
        
        # Interrupt
        await player.interrupt()
        logger.info("✓ Interrupted")
        
        assert not player.is_session_active, "Session should be inactive"
        assert player.state == PlaybackState.IDLE, "Should be IDLE"
        
        logger.info("✅ Test 3 passed\n")
        
    finally:
        await player.stop()


async def test_multiple_sessions():
    """Test multiple sequential sessions."""
    logger.info("\n=== Test 4: Multiple sessions ===")
    
    player = AudioPlayer(
        sample_rate=16000,
        channels=1,
        buffering_chunks=2,
        fade_samples=100,
    )
    
    try:
        await player.start()
        
        for session_num in range(3):
            logger.info(f"Session {session_num + 1}...")
            
            await player.begin_session()
            
            # Different frequency for each session
            frequency = 440 + (session_num * 100)
            chunk_20ms = generate_tone(frequency, 20)
            
            for i in range(10):
                await player.feed(chunk_20ms)
                await asyncio.sleep(0.01)
            
            await player.end_session()
            await asyncio.sleep(0.3)  # Wait between sessions
        
        logger.info("✅ Test 4 passed (3 sessions)\n")
        
    finally:
        await player.stop()


async def test_jitter_handling():
    """Test jitter handling with irregular chunk timing."""
    logger.info("\n=== Test 5: Jitter handling ===")
    
    player = AudioPlayer(
        sample_rate=16000,
        channels=1,
        buffering_chunks=3,  # More buffering for jitter
        fade_samples=100,
    )
    
    try:
        await player.start()
        await player.begin_session()
        
        chunk_20ms = generate_tone(440, 20)
        
        # Irregular timing to simulate network jitter
        delays = [0.01, 0.05, 0.01, 0.08, 0.02, 0.01, 0.06, 0.01] * 3
        
        for i, delay in enumerate(delays):
            await player.feed(chunk_20ms)
            await asyncio.sleep(delay)
        
        logger.info("✓ Fed chunks with jitter")
        
        await player.end_session()
        await asyncio.sleep(0.5)
        
        logger.info("✅ Test 5 passed (listen for smooth playback)\n")
        
    finally:
        await player.stop()


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Testing Refactored Audio Playback System")
    logger.info("=" * 60)
    
    try:
        await test_session_playback()
        await test_continuous_playback()
        await test_interrupt()
        await test_multiple_sessions()
        await test_jitter_handling()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ All tests passed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
