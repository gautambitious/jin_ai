#!/bin/bash
# Installation script for Jin LED daemon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/jin-led.service"
SYSTEMD_DIR="/etc/systemd/system"
DAEMON_SCRIPT="$SCRIPT_DIR/daemon.py"

echo "=== Jin LED Daemon Installation ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Check if daemon script exists
if [ ! -f "$DAEMON_SCRIPT" ]; then
    echo "ERROR: daemon.py not found at $DAEMON_SCRIPT"
    exit 1
fi

# Make daemon executable
echo "Making daemon executable..."
chmod +x "$DAEMON_SCRIPT"

# Copy service file to systemd
echo "Installing systemd service..."
cp "$SERVICE_FILE" "$SYSTEMD_DIR/jin-led.service"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable service
echo "Enabling jin-led service..."
systemctl enable jin-led.service

# Start service
echo "Starting jin-led service..."
systemctl start jin-led.service

# Check status
echo ""
echo "=== Service Status ==="
systemctl status jin-led.service --no-pager

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start jin-led"
echo "  Stop:    sudo systemctl stop jin-led"
echo "  Restart: sudo systemctl restart jin-led"
echo "  Status:  sudo systemctl status jin-led"
echo "  Logs:    sudo journalctl -u jin-led -f"
echo ""
