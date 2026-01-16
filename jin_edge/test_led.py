"""Test LED controller animations."""

import asyncio
import logging
import sys

from led.controller import LEDController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def test_animations():
    """Test all LED animations."""
    controller = LEDController()
    
    try:
        # Initialize
        logger.info("Initializing LED controller...")
        await controller.initialize()
        await asyncio.sleep(1)
        
        # Test wake word detected (blue pulse)
        logger.info("Testing wake word detected (blue pulse)...")
        await controller.wakeword_detected()
        await asyncio.sleep(5)
        
        # Test listening (spinning blue)
        logger.info("Testing listening (spinning blue)...")
        await controller.listening()
        await asyncio.sleep(5)
        
        # Test thinking (dim blue)
        logger.info("Testing thinking (dim blue)...")
        await controller.thinking()
        await asyncio.sleep(5)
        
        # Test speaking (brighter blue)
        logger.info("Testing speaking (brighter blue)...")
        await controller.speaking()
        await asyncio.sleep(5)
        
        # Turn off
        logger.info("Turning off LEDs...")
        await controller.off()
        await asyncio.sleep(1)
        
        logger.info("All tests completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        await controller.cleanup()


async def test_individual_animation(animation_name: str, duration: int = 10):
    """Test a specific animation."""
    controller = LEDController()
    
    try:
        logger.info(f"Initializing LED controller for {animation_name} test...")
        await controller.initialize()
        await asyncio.sleep(1)
        
        # Map animation name to method
        animations = {
            "wakeword": controller.wakeword_detected,
            "listening": controller.listening,
            "thinking": controller.thinking,
            "speaking": controller.speaking,
        }
        
        if animation_name not in animations:
            logger.error(f"Unknown animation: {animation_name}")
            logger.info(f"Available animations: {list(animations.keys())}")
            return
        
        logger.info(f"Running {animation_name} animation for {duration} seconds...")
        await animations[animation_name]()
        await asyncio.sleep(duration)
        
        logger.info("Turning off LEDs...")
        await controller.off()
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up...")
        await controller.cleanup()


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Test specific animation
        animation = sys.argv[1].lower()
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        asyncio.run(test_individual_animation(animation, duration))
    else:
        # Test all animations
        asyncio.run(test_animations())


if __name__ == "__main__":
    main()
