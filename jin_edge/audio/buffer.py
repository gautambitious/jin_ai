"""
Lightweight audio buffer for PCM playback.
Thread-safe and asyncio-safe with fixed max size.
"""

import asyncio
from collections import deque
from typing import Optional


class AudioBuffer:
    """
    Fixed-size audio buffer for streaming PCM chunks.

    Designed for 20-100ms audio chunks with low memory overhead.
    """

    def __init__(self, max_size: int = 1024 * 1024):  # 1MB default
        """
        Initialize audio buffer.

        Args:
            max_size: Maximum buffer size in bytes (default 1MB)
        """
        self._buffer = deque()
        self._max_size = max_size
        self._current_size = 0
        self._lock = asyncio.Lock()

    async def push(self, data: bytes) -> bool:
        """
        Push audio data to buffer.

        Args:
            data: PCM audio bytes to add

        Returns:
            True if pushed successfully, False if buffer full
        """
        if not data:
            return True

        async with self._lock:
            if self._current_size + len(data) > self._max_size:
                return False

            self._buffer.append(data)
            self._current_size += len(data)
            return True

    async def pop(self, chunk_size: Optional[int] = None) -> bytes:
        """
        Pop audio data from buffer.

        Args:
            chunk_size: Number of bytes to retrieve (None = all available)

        Returns:
            Audio data bytes (may be less than requested if buffer has less)
        """
        async with self._lock:
            if not self._buffer:
                return b""

            if chunk_size is None:
                # Return all data
                result = b"".join(self._buffer)
                self._buffer.clear()
                self._current_size = 0
                return result

            # Collect chunks until we have enough data
            result = b""
            while self._buffer and len(result) < chunk_size:
                chunk = self._buffer.popleft()
                self._current_size -= len(chunk)

                if len(result) + len(chunk) <= chunk_size:
                    result += chunk
                else:
                    # Split chunk if it exceeds requested size
                    needed = chunk_size - len(result)
                    result += chunk[:needed]
                    # Put remainder back
                    self._buffer.appendleft(chunk[needed:])
                    self._current_size += len(chunk[needed:])
                    break

            return result

    async def clear(self) -> None:
        """Clear all buffered audio data."""
        async with self._lock:
            self._buffer.clear()
            self._current_size = 0

    async def size(self) -> int:
        """Get current buffer size in bytes."""
        async with self._lock:
            return self._current_size

    async def is_empty(self) -> bool:
        """Check if buffer is empty."""
        async with self._lock:
            return len(self._buffer) == 0

    async def available_space(self) -> int:
        """Get available space in bytes."""
        async with self._lock:
            return self._max_size - self._current_size
