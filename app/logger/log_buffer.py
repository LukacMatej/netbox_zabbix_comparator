"""In-memory ring buffer of formatted log lines, backing the web log viewer.

Kept separate from stdout logging so the web UI can show recent history
without needing a log file or a Docker volume.
"""
import logging
import threading
from collections import deque


class LogRingBuffer:
    """Thread-safe fixed-size buffer of formatted log lines."""

    def __init__(self, maxlen: int = 1000) -> None:
        self._buffer: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, line: str) -> None:
        with self._lock:
            self._buffer.append(line)

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self._buffer)


log_buffer = LogRingBuffer(maxlen=1000)


class RingBufferHandler(logging.Handler):
    """Logging handler that appends formatted records to `log_buffer`."""

    def emit(self, record: logging.LogRecord) -> None:
        log_buffer.append(self.format(record))
