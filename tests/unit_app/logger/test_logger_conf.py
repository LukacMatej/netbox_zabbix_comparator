"""Unit tests for logger configuration module."""

import logging
import unittest

from app.logger import logger_conf


class LoggerConfTests(unittest.TestCase):
    """Tests for logger identity, level, and handler registration."""

    def test_logger_configuration(self):
        """Logger should be configured with expected name, level and stream handler."""
        self.assertEqual(logger_conf.logger.name, "Netbox-Zabbix")
        self.assertEqual(logger_conf.logger.level, logging.DEBUG)
        self.assertTrue(
            any(isinstance(h, logging.StreamHandler) for h in logger_conf.logger.handlers)
        )


if __name__ == "__main__":
    unittest.main()
