import logging
import unittest

from app.logger import logger_conf


class LoggerConfTests(unittest.TestCase):
    def test_logger_configuration(self):
        self.assertEqual(logger_conf.logger.name, "Netbox-Zabbix")
        self.assertEqual(logger_conf.logger.level, logging.DEBUG)
        self.assertTrue(
            any(isinstance(h, logging.StreamHandler) for h in logger_conf.logger.handlers)
        )


if __name__ == "__main__":
    unittest.main()
