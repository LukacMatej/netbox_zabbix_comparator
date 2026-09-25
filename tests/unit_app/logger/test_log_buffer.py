"""Unit tests for the in-memory log ring buffer."""

import logging
import unittest

from app.logger.log_buffer import LogRingBuffer, RingBufferHandler, log_buffer


class LogRingBufferTests(unittest.TestCase):
    """Tests for LogRingBuffer's fixed-size retention."""

    def test_snapshot_returns_appended_lines_in_order(self):
        buffer = LogRingBuffer(maxlen=1000)
        buffer.append("first")
        buffer.append("second")
        self.assertEqual(buffer.snapshot(), ["first", "second"])

    def test_buffer_keeps_only_most_recent_maxlen_lines(self):
        buffer = LogRingBuffer(maxlen=1000)
        for i in range(1500):
            buffer.append(f"line-{i}")
        snapshot = buffer.snapshot()
        self.assertEqual(len(snapshot), 1000)
        self.assertEqual(snapshot[0], "line-500")
        self.assertEqual(snapshot[-1], "line-1499")


class RingBufferHandlerTests(unittest.TestCase):
    """Tests for RingBufferHandler formatting and appending records."""

    def test_emit_formats_and_appends_record(self):
        # RingBufferHandler.emit() always appends to the module-level
        # log_buffer singleton, so exercise that shared buffer directly.
        handler = RingBufferHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        before = len(log_buffer.snapshot())
        handler.emit(record)
        after = log_buffer.snapshot()
        self.assertEqual(len(after), before + 1)
        self.assertEqual(after[-1], "INFO:hello world")


if __name__ == "__main__":
    unittest.main()
