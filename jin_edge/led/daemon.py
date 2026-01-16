#!/usr/bin/env python3
"""
LED Daemon - Privileged service for NeoPixel control.

Runs as root to handle /dev/mem access for WS2812 LEDs.
Listens on Unix socket for state commands from non-root application.

States: idle, listening, thinking, speaking, off

Audio-safe configuration:
- Uses DMA channel 5 (non-conflicting with audio)
- Maximum 20 FPS animation rate
- Default OFF state on startup
"""

import os
import socket
import signal
import sys
import time
import threading
import json
from pathlib import Path

# Add parent directory to path to import env_vars
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import env_vars

try:
    import board
    import neopixel
    from rpi_ws281x import ws, PixelStrip
    DIRECT_WS281X_AVAILABLE = True
except ImportError as e:
    try:
        import board
        import neopixel
        DIRECT_WS281X_AVAILABLE = False
        ws = None  # type: ignore
        PixelStrip = None  # type: ignore
    except ImportError:
        print("ERROR: Required packages not found. Install: adafruit-circuitpython-neopixel rpi-ws281x")
        sys.exit(1)
    print(f"WARNING: rpi_ws281x not available directly, DMA channel cannot be customized: {e}")

# LED Configuration Constants
DEFAULT_LED_COUNT = 10  # Number of LEDs in the strip
DEFAULT_BRIGHTNESS = 0.6  # Global brightness (0.0 to 1.0)
DEFAULT_GPIO_PIN = 18  # GPIO pin for data line
DMA_CHANNEL = 5  # Non-default DMA channel for audio safety
MIN_FRAME_TIME = 0.05  # 20 FPS maximum (50ms minimum between frames)


class LEDDaemon:
    """Privileged LED control daemon."""

    SOCKET_PATH = "/tmp/jin_led.sock"
    
    # LED states
    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_THINKING = "thinking"
    STATE_SPEAKING = "speaking"
    STATE_OFF = "off"
    
    def __init__(self, config_path=None):
        """Initialize daemon."""
        self.config = self._load_config(config_path)
        self.pixels = None
        self._use_direct_ws281x = False
        self.current_state = self.STATE_OFF
        self.running = False
        self.animation_thread = None
        self.sock = None
        
        # Auto-off timer
        self.auto_off_timeout = env_vars.LED_AUTO_OFF_TIMEOUT
        self._auto_off_task = None
        self._auto_off_lock = threading.Lock()
        
    def _load_config(self, config_path):
        """Load configuration from JSON file and environment variables."""
        # Start with defaults from env_vars.LED_CONFIG
        defaults = {
            "gpio_pin": env_vars.LED_CONFIG.get("gpio_pin", DEFAULT_GPIO_PIN),
            "num_pixels": env_vars.LED_CONFIG.get("num_pixels", DEFAULT_LED_COUNT),
            "brightness": env_vars.LED_CONFIG.get("brightness", DEFAULT_BRIGHTNESS),
        }
        
        # Override individual LED_* environment variables if present
        led_count = os.getenv("LED_COUNT")
        if led_count:
            defaults["num_pixels"] = int(led_count)
        
        led_brightness = os.getenv("LED_BRIGHTNESS")
        if led_brightness:
            defaults["brightness"] = float(led_brightness)
        
        led_gpio = os.getenv("LED_GPIO_PIN")
        if led_gpio:
            defaults["gpio_pin"] = int(led_gpio)
        
        # Override with config file if provided
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    user_config = json.load(f)
                defaults.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load config from {config_path}: {e}")
        
        return defaults
    
    def _get_board_pin(self, gpio_num):
        """Convert GPIO number to board pin."""
        pin_map = {
            18: board.D18,
            12: board.D12,
            21: board.D21,
            10: board.D10,
        }
        if gpio_num not in pin_map:
            raise ValueError(f"Unsupported GPIO pin: {gpio_num}")
        return pin_map[gpio_num]
    
    def initialize_leds(self):
        """Initialize NeoPixel strip with audio-safe DMA channel."""
        try:
            if DIRECT_WS281X_AVAILABLE:
                # Use rpi_ws281x directly to set DMA channel
                from rpi_ws281x import ws, PixelStrip
                
                gpio_pin = self.config["gpio_pin"]
                self.pixels = PixelStrip(
                    num=self.config["num_pixels"],
                    pin=gpio_pin,
                    freq_hz=800000,
                    dma=DMA_CHANNEL,  # DMA channel 5 for audio safety
                    invert=False,
                    brightness=int(self.config["brightness"] * 255),
                    channel=0,
                    strip_type=ws.WS2811_STRIP_GRB
                )
                self.pixels.begin()
                self._use_direct_ws281x = True
                print(f"LEDs initialized: {self.config['num_pixels']} pixels on GPIO {gpio_pin} (direct rpi_ws281x)")
            else:
                # Fallback to adafruit-circuitpython-neopixel
                gpio_pin = self.config["gpio_pin"]
                pin = self._get_board_pin(gpio_pin)
                self.pixels = neopixel.NeoPixel(
                    pin,
                    self.config["num_pixels"],
                    brightness=self.config["brightness"],
                    auto_write=False,
                    pixel_order=neopixel.GRB
                )
                self._use_direct_ws281x = False
                print(f"LEDs initialized: {self.config['num_pixels']} pixels on GPIO {gpio_pin} (neopixel)")
                print("WARNING: Using default DMA channel - audio conflicts may occur")
            
            # Start in OFF state
            self._clear_leds()
            
            print(f"Brightness: {self.config['brightness']}, DMA: {DMA_CHANNEL}, Max FPS: 20")
        except Exception as e:
            print(f"ERROR: Failed to initialize LEDs: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def setup_socket(self):
        """Setup Unix socket for IPC."""
        # Remove old socket if exists
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)
        
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.SOCKET_PATH)
        os.chmod(self.SOCKET_PATH, 0o666)  # Allow non-root access
        self.sock.listen(1)
        print(f"Listening on {self.SOCKET_PATH}")
    
    def _set_pixel(self, index, color):
        """Set a single pixel color (abstraction layer)."""
        if not self.pixels:
            return
        
        if self._use_direct_ws281x:
            # rpi_ws281x uses Color(red, green, blue)
            from rpi_ws281x import Color
            self.pixels.setPixelColor(index, Color(color[1], color[0], color[2]))  # type: ignore
        else:
            # neopixel uses tuple
            self.pixels[index] = color  # type: ignore
    
    def _fill_pixels(self, color):
        """Fill all pixels with a color (abstraction layer)."""
        if not self.pixels:
            return
        
        if self._use_direct_ws281x:
            from rpi_ws281x import Color
            # GRB order: color is (R, G, B), but strip expects GRB
            pixel_color = Color(color[1], color[0], color[2])  # GRB to RGB
            for i in range(self.pixels.numPixels()):  # type: ignore
                self.pixels.setPixelColor(i, pixel_color)  # type: ignore
        else:
            self.pixels.fill(color)  # type: ignore
    
    def _show_pixels(self):
        """Update the LED strip (abstraction layer)."""
        if not self.pixels:
            return
        
        if self._use_direct_ws281x:
            self.pixels.show()
        else:
            self.pixels.show()
    
    def _interruptible_sleep(self, duration):
        """Sleep in small chunks to allow quick interruption.
        
        Args:
            duration: Total sleep duration in seconds
            
        Returns:
            bool: True if sleep completed, False if interrupted
        """
        CHUNK_SIZE = 0.01  # 10ms chunks for responsiveness
        chunks = int(duration / CHUNK_SIZE)
        remainder = duration % CHUNK_SIZE
        
        for _ in range(chunks):
            if not self.running:
                return False
            time.sleep(CHUNK_SIZE)
        
        if remainder > 0 and self.running:
            time.sleep(remainder)
        
        return self.running
    
    def set_state(self, state):
        """Change LED state."""
        if state not in [self.STATE_IDLE, self.STATE_LISTENING, self.STATE_THINKING, 
                         self.STATE_SPEAKING, self.STATE_OFF]:
            print(f"Warning: Unknown state '{state}'")
            return False
        
        if state == self.current_state:
            return True
        
        self.current_state = state
        print(f"State changed: {state}")
        
        # Reset auto-off timer for non-OFF states
        if state != self.STATE_OFF:
            self._reset_auto_off_timer()
        else:
            self._cancel_auto_off_timer()
        
        # Stop current animation thread if running
        if self.animation_thread and self.animation_thread.is_alive():
            self.running = False
            self.animation_thread.join(timeout=1.0)
        
        # Start new animation
        self.running = True
        if state == self.STATE_IDLE:
            self.animation_thread = threading.Thread(target=self._animate_idle, daemon=True)
            self.animation_thread.start()
        elif state == self.STATE_LISTENING:
            self.animation_thread = threading.Thread(target=self._animate_listening, daemon=True)
            self.animation_thread.start()
        elif state == self.STATE_THINKING:
            self.animation_thread = threading.Thread(target=self._animate_thinking, daemon=True)
            self.animation_thread.start()
        elif state == self.STATE_SPEAKING:
            self.animation_thread = threading.Thread(target=self._animate_speaking, daemon=True)
            self.animation_thread.start()
        elif state == self.STATE_OFF:
            self._clear_leds()
        
        return True
    
    def _clear_leds(self):
        """Turn off all LEDs."""
        if self.pixels:
            self._fill_pixels((0, 0, 0))
            self._show_pixels()
    
    def _reset_auto_off_timer(self):
        """Reset the auto-off timer."""
        with self._auto_off_lock:
            # Cancel existing timer
            if self._auto_off_task:
                self._auto_off_task.cancel()
            
            # Start new timer
            self._auto_off_task = threading.Timer(
                self.auto_off_timeout,
                self._auto_off_callback
            )
            self._auto_off_task.daemon = True
            self._auto_off_task.start()
    
    def _cancel_auto_off_timer(self):
        """Cancel the auto-off timer."""
        with self._auto_off_lock:
            if self._auto_off_task:
                self._auto_off_task.cancel()
                self._auto_off_task = None
    
    def _auto_off_callback(self):
        """Auto-off timer callback."""
        print(f"Auto-off timer expired ({self.auto_off_timeout}s), turning off LEDs")
        self.set_state(self.STATE_OFF)
    
    def _animate_idle(self):
        """Idle state - dim blue breathing."""
        if not self.pixels:
            return
            
        min_brightness = 20
        max_brightness = 60
        step = 2
        delay = MIN_FRAME_TIME  # 20 FPS max
        
        while self.running and self.current_state == self.STATE_IDLE:
            # Breathe in
            for brightness in range(min_brightness, max_brightness, step):
                if not self.running or self.current_state != self.STATE_IDLE:
                    return
                self._fill_pixels((0, 0, brightness))
                self._show_pixels()
                if not self._interruptible_sleep(delay):
                    return
                if self.current_state != self.STATE_IDLE:
                    return
            
            # Breathe out
            for brightness in range(max_brightness, min_brightness, -step):
                if not self.running or self.current_state != self.STATE_IDLE:
                    return
                self._fill_pixels((0, 0, brightness))
                self._show_pixels()
                if not self._interruptible_sleep(delay):
                    return
                if self.current_state != self.STATE_IDLE:
                    return
    
    def _animate_listening(self):
        """Listening state - spinning blue."""
        if not self.pixels:
            return
            
        blue = (0, 0, 200)
        trail_length = 3
        position = 0
        delay = MIN_FRAME_TIME  # 20 FPS max
        
        while self.running and self.current_state == self.STATE_LISTENING:
            if not self.running or self.current_state != self.STATE_LISTENING:
                return
            
            self._fill_pixels((0, 0, 0))
            
            for i in range(trail_length):
                idx = (position - i) % self.config["num_pixels"]
                brightness = 1.0 - (i / trail_length)
                color = tuple(int(c * brightness) for c in blue)
                self._set_pixel(idx, color)
            
            self._show_pixels()
            position = (position + 1) % self.config["num_pixels"]
            
            if not self._interruptible_sleep(delay):
                return
            if self.current_state != self.STATE_LISTENING:
                return
    
    def _animate_thinking(self):
        """Thinking state - medium blue breathing."""
        if not self.pixels:
            return
            
        min_brightness = 30
        max_brightness = 80
        step = 2
        delay = MIN_FRAME_TIME  # 20 FPS max
        
        while self.running and self.current_state == self.STATE_THINKING:
            # Breathe in
            for brightness in range(min_brightness, max_brightness, step):
                if not self.running or self.current_state != self.STATE_THINKING:
                    return
                self._fill_pixels((0, 0, brightness))
                self._show_pixels()
                if not self._interruptible_sleep(delay):
                    return
                if self.current_state != self.STATE_THINKING:
                    return
            
            # Breathe out
            for brightness in range(max_brightness, min_brightness, -step):
                if not self.running or self.current_state != self.STATE_THINKING:
                    return
                self._fill_pixels((0, 0, brightness))
                self._show_pixels()
                if not self._interruptible_sleep(delay):
                    return
                if self.current_state != self.STATE_THINKING:
                    return
    
    def _animate_speaking(self):
        """Speaking state - bright blue breathing."""
        if not self.pixels:
            return
            
        min_brightness = 150
        max_brightness = 255
        step = 3
        delay = MIN_FRAME_TIME  # 20 FPS max
        
        while self.running and self.current_state == self.STATE_SPEAKING:
            # Breathe in
            for brightness in range(min_brightness, max_brightness, step):
                if not self.running or self.current_state != self.STATE_SPEAKING:
                    return
                self._fill_pixels((0, 0, brightness))
                self._show_pixels()
                if not self._interruptible_sleep(delay):
                    return
                if self.current_state != self.STATE_SPEAKING:
                    return
            
            # Breathe out
            for brightness in range(max_brightness, min_brightness, -step):
                if not self.running or self.current_state != self.STATE_SPEAKING:
                    return
                self._fill_pixels((0, 0, brightness))
                self._show_pixels()
                if not self._interruptible_sleep(delay):
                    return
                if self.current_state != self.STATE_SPEAKING:
                    return
    
    def handle_client(self, conn):
        """Handle client connection."""
        try:
            data = conn.recv(1024).decode().strip()
            if data:
                success = self.set_state(data)
                response = "OK" if success else "ERROR"
                conn.sendall(response.encode())
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            conn.close()
    
    def run(self):
        """Main daemon loop with non-blocking socket operations."""
        print("LED Daemon starting...")
        
        # Check if running as root
        if os.geteuid() != 0:
            print("ERROR: This daemon must run as root for /dev/mem access")
            sys.exit(1)
        
        self.initialize_leds()
        self.setup_socket()
        
        # Set socket timeout for non-blocking operation
        if self.sock:
            self.sock.settimeout(0.01)  # 10ms timeout for quick response
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        print("LED Daemon ready (non-blocking mode)")
        
        try:
            while True:
                if not self.sock:
                    break
                
                try:
                    # Non-blocking accept with short timeout
                    conn, _ = self.sock.accept()
                    self.handle_client(conn)
                except socket.timeout:
                    # No connection, continue loop
                    pass
                except Exception as e:
                    if self.running:
                        print(f"Socket error: {e}")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Cleanup resources."""
        print("Cleaning up...")
        self.running = False
        
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join(timeout=1.0)
        
        self._clear_leds()
        
        if self.pixels:
            if self._use_direct_ws281x:
                # PixelStrip doesn't have deinit, just clear it
                pass
            else:
                self.pixels.deinit()  # type: ignore
        
        if self.sock:
            self.sock.close()
        
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)
        
        print("Daemon stopped")


def main():
    """Entry point."""
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    daemon = LEDDaemon(config_path)
    daemon.run()


if __name__ == "__main__":
    main()
