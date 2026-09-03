"""
Logger configuration module for Netbox-Zabbix application.

Logs go to stdout/stderr only (e.g. `docker logs`); there is no in-app log
viewer or streaming endpoint, since synchronization/comparison errors are
already surfaced directly in the UI output for the action that produced them.
"""
import logging

log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
lgout = logging.StreamHandler()
lgout.setFormatter(log_format)

logger: logging.Logger = logging.getLogger("Netbox-Zabbix")
logger.addHandler(lgout)
logger.setLevel(logging.DEBUG)
