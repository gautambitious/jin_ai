# Jin LED Daemon

Privileged LED control service for Raspberry Pi NeoPixel/WS2812 strips.

## Architecture

- **Daemon** ([daemon.py](daemon.py)) - Runs as root, controls LEDs directly
- **Client** ([client.py](client.py)) - Non-privileged IPC communication
- **Controller** ([controller.py](controller.py)) - Async wrapper for main app
- **Communication** - Unix socket at `/tmp/jin_led.sock`

## States

- `idle` - Dim blue breathing (20-60 brightness)
- `listening` - Spinning blue with trail
- `thinking` - Dim blue breathing (30-80 brightness)
- `speaking` - Bright blue breathing (150-255 brightness)
- `off` - All LEDs off

## Installation

1. Install as systemd service:
```bash
cd /home/gautam/edge/jin_ai/jin_edge/led
sudo ./install.sh
```

2. Verify it's running:
```bash
sudo systemctl status jin-led
```

## Configuration

Edit daemon.py or create `/etc/jin_led.json`:
```json
{
  "gpio_pin": 18,
  "num_pixels": 10,
  "brightness": 0.3
}
```

## Usage

### From Python (main application)
```python
from led.controller import LEDController

controller = LEDController()
await controller.initialize()
await controller.listening()
await controller.thinking()
await controller.speaking()
await controller.off()
```

### Command Line
```bash
# Test all states
python test_led_client.py

# Set specific state
python test_led_client.py listening
python test_led_client.py thinking
python test_led_client.py off
```

## Management

```bash
# Start daemon
sudo systemctl start jin-led

# Stop daemon
sudo systemctl stop jin-led

# Restart daemon
sudo systemctl restart jin-led

# View logs
sudo journalctl -u jin-led -f

# Disable auto-start
sudo systemctl disable jin-led
```

## Troubleshooting

### Daemon won't start
```bash
# Check logs
sudo journalctl -u jin-led -n 50

# Test daemon manually
sudo /home/gautam/edge/env/bin/python /home/gautam/edge/jin_ai/jin_edge/led/daemon.py
```

### Client can't connect
```bash
# Check if daemon is running
sudo systemctl status jin-led

# Check socket exists
ls -la /tmp/jin_led.sock

# Check socket permissions (should be 666)
stat /tmp/jin_led.sock
```

### Wrong GPIO pin
Edit [jin-led.service](jin-led.service) to pass config:
```ini
ExecStart=/home/gautam/edge/env/bin/python /home/gautam/edge/jin_ai/jin_edge/led/daemon.py /etc/jin_led.json
```

## Why a Daemon?

NeoPixel LEDs require `/dev/mem` access (root) for DMA control, but audio stack must run as non-root user. Solution: separate privileged daemon with IPC.
