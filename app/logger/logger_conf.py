"""
Logger configuration module for Netbox-Zabbix application.
...
"""
import asyncio
import logging
from collections import deque

log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
lgout = logging.StreamHandler()
lgout.setFormatter(log_format)


class LogBroadcaster(logging.Handler):
    """
    In-memory log handler that keeps a rolling buffer of recent log lines
    and broadcasts new lines to any subscribed asyncio queues, enabling
    real-time log streaming (similar to `docker logs -f`) without writing
    to disk.
    """

    def __init__(self, maxlen: int = 1000):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=maxlen)
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Must be called once from the running event loop at startup."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        self.buffer.append(line)
        if self._loop is None:
            return
        # emit() can be called from any thread; hand off to the event loop safely
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, line)


broadcaster = LogBroadcaster()
broadcaster.setFormatter(log_format)

logger: logging.Logger = logging.getLogger("Netbox-Zabbix")
logger.addHandler(lgout)
logger.addHandler(broadcaster)
logger.setLevel(logging.DEBUG)
