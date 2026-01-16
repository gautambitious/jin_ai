"""LED Daemon Client - Non-privileged communication with LED daemon."""

import socket
import logging

logger = logging.getLogger(__name__)


class LEDClient:
    """Client for communicating with LED daemon via Unix socket."""

    SOCKET_PATH = "/tmp/jin_led.sock"
    TIMEOUT = 1.0

    # States
    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_THINKING = "thinking"
    STATE_SPEAKING = "speaking"
    STATE_OFF = "off"

    def __init__(self):
        """Initialize client."""
        self._last_state = None

    def _send_command(self, command: str) -> bool:
        """Send command to daemon."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.TIMEOUT)
            sock.connect(self.SOCKET_PATH)
            sock.sendall(command.encode())
            response = sock.recv(1024).decode().strip()
            sock.close()
            
            if response == "OK":
                return True
            else:
                logger.warning(f"LED daemon returned: {response}")
                return False
                
        except FileNotFoundError:
            logger.error(f"LED daemon socket not found at {self.SOCKET_PATH}. Is the daemon running?")
            return False
        except ConnectionRefusedError:
            logger.error("LED daemon refused connection. Is it running?")
            return False
        except socket.timeout:
            logger.error("LED daemon timeout")
            return False
        except Exception as e:
            logger.error(f"Error communicating with LED daemon: {e}")
            return False

    def set_state(self, state: str) -> bool:
        """Set LED state."""
        if state == self._last_state:
            return True
        
        success = self._send_command(state)
        if success:
            self._last_state = state
            logger.debug(f"LED state set to: {state}")
        return success

    def idle(self) -> bool:
        """Set idle state."""
        return self.set_state(self.STATE_IDLE)

    def listening(self) -> bool:
        """Set listening state."""
        return self.set_state(self.STATE_LISTENING)

    def thinking(self) -> bool:
        """Set thinking state."""
        return self.set_state(self.STATE_THINKING)

    def speaking(self) -> bool:
        """Set speaking state."""
        return self.set_state(self.STATE_SPEAKING)

    def off(self) -> bool:
        """Turn off LEDs."""
        return self.set_state(self.STATE_OFF)
