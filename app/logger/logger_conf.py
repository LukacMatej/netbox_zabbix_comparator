"""
Logger configuration module for Netbox-Zabbix application.

Logs go to stdout/stderr (e.g. `docker logs`) and are also kept in an
in-memory ring buffer (see `app.logger.log_buffer`) so the web UI's
"View Logs" page can display recent history.
"""
import logging

from app.logger.log_buffer import RingBufferHandler

log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
lgout = logging.StreamHandler()
lgout.setFormatter(log_format)

ring_handler = RingBufferHandler()
ring_handler.setFormatter(log_format)

logger: logging.Logger = logging.getLogger("Netbox-Zabbix")
logger.addHandler(lgout)
logger.addHandler(ring_handler)
logger.setLevel(logging.DEBUG)
