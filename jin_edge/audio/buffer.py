"""
Lightweight audio buffer for PCM playback.
Thread-safe and asyncio-safe with fixed max size.
Supports chunk-based queueing for jitter-free playback.
"""

import asyncio
from collections import deque
from typing import Optional


class AudioBuffer:
    """
    Fixed-size audio buffer for streaming PCM chunks.

    Designed for 20-100ms audio chunks with low memory overhead.
    Maintains chunk boundaries for efficient playback.
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
        self._data_available = asyncio.Event()

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
            self._data_available.set()
            return True

    async def pop_chunk(self) -> Optional[bytes]:
        """
        Pop one complete chunk from buffer.

        Returns:
            Audio chunk bytes, or None if buffer empty
        """
        async with self._lock:
            if not self._buffer:
                self._data_available.clear()
                return None

            chunk = self._buffer.popleft()
            self._current_size -= len(chunk)
            
            if not self._buffer:
                self._data_available.clear()
            
            return chunk

    async def wait_for_data(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until data is available in buffer.

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if data available, False if timeout
        """
        try:
            await asyncio.wait_for(self._data_available.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def pop(self, chunk_size: Optional[int] = None) -> bytes:
        """
        Pop audio data from buffer (legacy method for compatibility).

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
                self._data_available.clear()
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

            if not self._buffer:
                self._data_available.clear()
                
            return result

    async def peek_chunk_count(self) -> int:
        """Get number of chunks in buffer."""
        async with self._lock:
            return len(self._buffer)

    async def clear(self) -> None:
        """Clear all buffered audio data."""
        async with self._lock:
            self._buffer.clear()
            self._current_size = 0
            self._data_available.clear()

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
