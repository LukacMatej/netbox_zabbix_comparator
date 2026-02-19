"""
Logger configuration module for Netbox-Zabbix application.
This module sets up a logger instance with a standard format that includes
timestamps, logger names, log levels, and messages. The logger outputs to
the console stream and is configured to capture DEBUG level and above.
Attributes:
    log_format (logging.Formatter): Formatter that defines the log message
        format as 'timestamp - logger_name - level - message'.
    lgout (logging.StreamHandler): Stream handler that outputs log records
        to the console.
    logger (logging.Logger): The main logger instance for the Netbox-Zabbix
        application, configured with DEBUG level logging.
"""
import logging

log_format = logging.Formatter('%(asctime)s - %(name)s - '
                               '%(levelname)s - %(message)s')
lgout = logging.StreamHandler()
lgout.setFormatter(log_format)
logger: logging.Logger = logging.getLogger("Netbox-Zabbix")
logger.addHandler(lgout)
logger.setLevel(logging.DEBUG)
