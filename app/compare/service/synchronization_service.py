import requests
import os
from app.logger import logger_conf as log
import app.device.service.device_service as device_service
from app.device.models.device_model import Device as device_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.address_model import Address as address_model
from app.device.models.interface_model import Interface as interface_model

def create_netbox_device(device: device_model):
    """Creates a device in Netbox based on the provided device model.
    Args:
        device (device_model): The device model to create in Netbox.
    """
    log.logger.info(f"Creating device {device.name} in Netbox.")
    netbox_ip = os.environ.get("NETBOX_IP")
    netbox_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {netbox_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(netbox_ip+"api/dcim/devices/", data=device.create_data_netbox())
    if response.status_code == 201:
        log.logger.info(f"Device {device.name} created successfully in Netbox.")
    else:
        log.logger.error(f"Failed to create device {device.name} in Netbox: {response.text}")

def create_zabbix_device(device: device_model):
    """Creates a device in Zabbix based on the provided device model.
    Args:
        device (device_model): The device model to create in Zabbix.
    """
    log.logger.info(f"Creating device {device.name} in Zabbix.")
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization  ": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response = requests.post(zabbix_ip+"zabbix/api_jsonrpc.php", headers=headers, data=device.create_data_zabbix())
    if response.status_code == 201:
        log.logger.info(f"Device {device.name} created successfully in Zabbix.")
    else:
        log.logger.error(f"Failed to create device {device.name} in Zabbix: {response.text}")

def sync_netbox_zabbix_devices(netbox_devices: list[device_model], zabbix_devices: list[device_model]):
    """Syncs Netbox and Zabbix devices that don't have matching devices in the other system.
    Args:
        netbox_devices (list[device_model]): List of devices from Netbox.
        zabbix_devices (list[device_model]): List of devices from Zabbix.
    """
    log.logger.info("Starting synchronization of Netbox and Zabbix devices.")
    for netbox_device in netbox_devices:
        if not any(zabbix_device.name == netbox_device.name for zabbix_device in zabbix_devices):
            log.logger.info(f"Device {netbox_device.name} found in Netbox but not in Zabbix, creating in Zabbix.")
            create_zabbix_device(netbox_device)
    
    for zabbix_device in zabbix_devices:
        if not any(netbox_device.name == zabbix_device.name for netbox_device in netbox_devices):
            log.logger.info(f"Device {zabbix_device.name} found in Zabbix but not in Netbox, creating in Netbox.")
            create_netbox_device(zabbix_device)
    
    log.logger.info("Synchronization of Netbox and Zabbix devices completed.")