"""
Audio device selection and configuration helper.
"""

import sounddevice as sd
from typing import Dict, List, Optional


def list_output_devices() -> List[Dict]:
    """
    List all available audio output devices.

    Returns:
        List of device info dictionaries with keys:
        - index: Device index
        - name: Device name
        - channels: Max output channels
        - sample_rate: Default sample rate
    """
    devices = sd.query_devices()
    output_devices = []

    for idx, device in enumerate(devices):
        device_dict = dict(device)  # Convert to dict for type safety
        if device_dict.get("max_output_channels", 0) > 0:
            output_devices.append(
                {
                    "index": idx,
                    "name": device_dict["name"],
                    "channels": device_dict["max_output_channels"],
                    "sample_rate": int(device_dict["default_samplerate"]),
                }
            )

    return output_devices


def list_input_devices() -> List[Dict]:
    """
    List all available audio input devices.

    Returns:
        List of device info dictionaries with keys:
        - index: Device index
        - name: Device name
        - channels: Max input channels
        - sample_rate: Default sample rate
    """
    devices = sd.query_devices()
    input_devices = []

    for idx, device in enumerate(devices):
        device_dict = dict(device)  # Convert to dict for type safety
        if device_dict.get("max_input_channels", 0) > 0:
            input_devices.append(
                {
                    "index": idx,
                    "name": device_dict["name"],
                    "channels": device_dict["max_input_channels"],
                    "sample_rate": int(device_dict["default_samplerate"]),
                }
            )

    return input_devices


def get_default_device() -> Dict:
    """
    Get the default audio output device configuration.

    Returns:
        Device configuration dict with:
        - device: Device index or None for system default
        - name: Device name
        - channels: Max output channels
        - sample_rate: Default sample rate
    """
    try:
        default_device = dict(sd.query_devices(kind="output"))  # Convert to dict
        return {
            "device": None,  # None uses system default
            "name": default_device["name"],
            "channels": default_device["max_output_channels"],
            "sample_rate": int(default_device["default_samplerate"]),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get default output device: {e}")


def get_default_input_device() -> Dict:
    """
    Get the default audio input device configuration.

    Returns:
        Device configuration dict with:
        - device: Device index or None for system default
        - name: Device name
        - channels: Max input channels
        - sample_rate: Default sample rate
    """
    try:
        default_device = dict(sd.query_devices(kind="input"))  # Convert to dict
        return {
            "device": None,  # None uses system default
            "name": default_device["name"],
            "channels": default_device["max_input_channels"],
            "sample_rate": int(default_device["default_samplerate"]),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get default input device: {e}")


def select_device(index: Optional[int] = None) -> Dict:
    """
    Select an audio output device by index or get default.

    Args:
        index: Device index (from list_output_devices), or None for default

    Returns:
        Device configuration dict suitable for AudioPlayer:
        - device: Device index or None
        - name: Device name
        - channels: Max output channels
        - sample_rate: Default sample rate

    Raises:
        ValueError: If device index is invalid
        RuntimeError: If no output devices available
    """
    if index is None:
        return get_default_device()

    # Validate index
    devices = list_output_devices()
    if not devices:
        raise RuntimeError("No audio output devices available")

    for device in devices:
        if device["index"] == index:
            return {
                "device": index,
                "name": device["name"],
                "channels": device["channels"],
                "sample_rate": device["sample_rate"],
            }

    raise ValueError(
        f"Invalid device index: {index}. Available: {[d['index'] for d in devices]}"
    )


def find_usb_mic() -> Optional[Dict]:
    """
    Automatically detect a USB microphone.

    Looks for common USB audio interface patterns in device names.
    Useful for Raspberry Pi where USB mics are commonly used.

    Returns:
        Device dict if USB mic found, None otherwise
    """
    input_devices = list_input_devices()

    # Common USB audio device name patterns
    usb_patterns = [
        "usb",
        "hw:",  # ALSA hardware device
        "plughw:",  # ALSA plug device
        "card",  # Generic card reference
    ]

    for device in input_devices:
        name_lower = device["name"].lower()
        for pattern in usb_patterns:
            if pattern in name_lower:
                return device

    return None


def select_input_device(index: Optional[int] = None) -> Dict:
    """
    Select an audio input device by index or get default.

    Args:
        index: Device index (from list_input_devices), or None for default

    Returns:
        Device configuration dict suitable for MicStream:
        - device: Device index or None
        - name: Device name
        - channels: Max input channels
        - sample_rate: Default sample rate

    Raises:
        ValueError: If device index is invalid
        RuntimeError: If no input devices available
    """
    if index is None:
        return get_default_input_device()

    # Validate index
    devices = list_input_devices()
    if not devices:
        raise RuntimeError("No audio input devices available")

    for device in devices:
        if device["index"] == index:
            return {
                "device": index,
                "name": device["name"],
                "channels": device["channels"],
                "sample_rate": device["sample_rate"],
            }

    raise ValueError(
        f"Invalid device index: {index}. Available: {[d['index'] for d in devices]}"
    )


def print_devices():
    """Print all available output devices in a readable format."""
    devices = list_output_devices()

    if not devices:
        print("No audio output devices found.")
        return

    print("Available audio output devices:")
    print("-" * 60)
    for device in devices:
        print(f"[{device['index']}] {device['name']}")
        print(
            f"    Channels: {device['channels']}, Sample Rate: {device['sample_rate']} Hz"
        )
    print("-" * 60)

    default = get_default_device()
    print(f"Default device: {default['name']}")


def print_input_devices():
    """Print all available input devices in a readable format."""
    devices = list_input_devices()

    if not devices:
        print("No audio input devices found.")
        return

    print("Available audio input devices:")
    print("-" * 60)
    for device in devices:
        print(f"[{device['index']}] {device['name']}")
        print(
            f"    Channels: {device['channels']}, Sample Rate: {device['sample_rate']} Hz"
        )
    print("-" * 60)

    try:
        default = get_default_input_device()
        print(f"Default device: {default['name']}")
    except:
        pass

    usb_mic = find_usb_mic()
    if usb_mic:
        print(f"USB microphone detected: {usb_mic['name']}")
