import requests
import os
import re
from app.logger import logger_conf as log
import app.device.service.device_service as device_service
from app.device.models.device_model import Device as device_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.address_model import Address as address_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.difference_model import DeviceDifference as device_difference_model


def find_template_ids(template_name: str) -> int:
    """Finds the Zabbix template ID based on the provided template name.
    Args:
        template_name (str): The name of the template to find.
    Returns:
        int: The ID of the template if found, otherwise -1.
    """
    log.logger.info(f"Finding Zabbix template ID for {template_name}.")
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json={
        "jsonrpc": "2.0",
        "method": "template.get",
        "params": {
            "filter": {"host": [template_name]}
        },
        "auth": None,  # This should be set when calling the API
        "id": 1
    })
    
    if response.status_code == 200:
        data = response.json()
        if data["result"]:
            template_id = data["result"][0]["templateid"]
            log.logger.info(f"Found Zabbix template ID: {template_id} for {template_name}.")
            return int(template_id)
    
    log.logger.error(f"Failed to find Zabbix template ID for {template_name}: {response.text}")
    return -1

def find_zabbix_hostgroup_id(hostgroup_name: str) -> int:
    """Finds the Zabbix hostgroup ID based on the provided hostgroup name.
    Args:
        hostgroup_name (str): The name of the hostgroup to find.
    Returns:
        int: The ID of the hostgroup if found, otherwise -1.
    """
    log.logger.info(f"Finding Zabbix hostgroup ID for {hostgroup_name}.")
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json={
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "filter": {"name": [hostgroup_name]}
        },
        "id": 1
    })
    log.logger.info(f"Response from Zabbix for hostgroup get: {response.text}, status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data["result"]:
            group_id = data["result"][0]["groupid"]
            log.logger.info(f"Found Zabbix hostgroup ID: {group_id} for {hostgroup_name}.")
            return int(group_id)
    
    log.logger.info(f"Failed to find Zabbix hostgroup ID for {hostgroup_name}: {response.text}")
    log.logger.info(f"Creating hostgroup {hostgroup_name} in Zabbix.")
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json={
        "jsonrpc": "2.0",
        "method": "hostgroup.create",
        "params": {
            "name": hostgroup_name
        },
        "id": 1
    })
    log.logger.info(f"Response from Zabbix for creating hostgroup: {response.text}, status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "result" in data and "groupids" in data["result"]:
            group_id = data["result"]["groupids"][0]
            log.logger.info(f"Hostgroup {hostgroup_name} created successfully with ID: {group_id}.")
            return int(group_id)
        else:
            log.logger.error(f"Failed to create hostgroup {hostgroup_name}: {data}")
    return -1

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
    response = requests.post(netbox_ip+"api/dcim/devices/", headers=headers, data=device.create_data_netbox())
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
    hostgroupid = find_zabbix_hostgroup_id(device.hostgroup)
    if hostgroupid == -1:
        log.logger.error(f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device in Netbox.")
        return
    templateids = [find_template_ids(template) for template in device.templates if template]
    if -1 in templateids:
        log.logger.error(f"No valid templates found for device {device.name}, cannot create in Netbox.")
        return
    data_zabbix = device.create_data_zabbix(hostgroupId=hostgroupid, templateids=templateids)
    data_zabbix = re.sub("'", '"', str(data_zabbix))
    log.logger.info(f"Data to be sent to Zabbix: {data_zabbix}")
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json=data_zabbix)
    
    if response.status_code == 201:
        log.logger.info(f"Device {device.name} created successfully in Zabbix.")
    else:
        log.logger.error(f"Failed to create device {device.name} in Zabbix: {response.text}")

def sync_netbox_zabbix_devices(differences:list[device_difference_model], netbox_devices: list[device_model], zabbix_devices: list[device_model]):
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
    
    # for zabbix_device in zabbix_devices:
    #     if not any(netbox_device.name == zabbix_device.name for netbox_device in netbox_devices):
    #         log.logger.info(f"Device {zabbix_device.name} found in Zabbix but not in Netbox, creating in Netbox.")
    #         create_netbox_device(zabbix_device)
    
    log.logger.info("Synchronization of Netbox and Zabbix devices completed.")