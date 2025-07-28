import requests
import os
import re
from app.logger import logger_conf as log
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.synchonization_output_model import SyncOutput as sync_output_model
from app.device.service import device_service

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

def apply_differences(differences: device_difference_model, sync_output: sync_output_model):
    """Applies the differences between Netbox and Zabbix devices.
    Args:
        differences (device_difference_model): The differences between the Netbox and Zabbix devices.
        sync_output (sync_output_model): The synchronization output model to log the results.
    """
    nb_device: device_model = differences.nb_device
    zb_device: device_model = differences.zb_device
    different_fields: list[str] = differences.differences[0]  # tuple: (different_fields, same_fields)

    def extract_field_name(field: str):
        if '(' in field:
            return field.split('(')[0].strip()
        return field.strip()

    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    
    hostid = None
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json={
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"filter": {"host": [zb_device.name]}},
        "id": 1
    })
    if response.status_code == 200:
        data = response.json()
        if data["result"]:
            hostid = data["result"][0]["hostid"]
    if not hostid:
        sync_output.add_difference_output(f"Failed to find Zabbix hostid for {zb_device.name}, cannot update device.")
        log.logger.error(f"Failed to find Zabbix hostid for {zb_device.name}, cannot update device.")
        return
    log.logger.info("Zabbix Device before update "+device_service.print_device(zb_device))
    updated_fields = {}
    interface_keys = ["port_type"]
    address_keys = ["address", "dns_name"]
    # Check which fields are different and prepare update params
    for field in different_fields:
        field_name = extract_field_name(field)
        if hasattr(nb_device, field_name) and hasattr(zb_device, field_name):
            nb_value = getattr(nb_device, field_name)
            zb_value = getattr(zb_device, field_name)
            if nb_value != zb_value:
                updated_fields[field_name] = nb_value
                setattr(zb_device, field_name, nb_value)
                log.logger.info(f"Field {field_name} is different: Netbox value: {nb_value}, Zabbix value: {zb_value}")
        elif field_name in interface_keys:
            # Handle interface fields
            nb_interfaces: list[interface_model] = nb_device.interfaces
            zb_interfaces: list[interface_model] = zb_device.interfaces
            for nb_interface, zb_interface in zip(nb_interfaces, zb_interfaces):
                if isinstance(nb_interface, interface_model) and isinstance(zb_interface, interface_model):
                    for key in interface_keys:
                        if hasattr(nb_interface, key) and hasattr(zb_interface, key):
                            nb_value = getattr(nb_interface, key)
                            zb_value = getattr(zb_interface, key)
                            if nb_value != zb_value:
                                updated_fields[f"{key} {nb_interface.name}"] = nb_value
                                setattr(zb_interface, key, nb_value)
                                log.logger.info(f"Interface field {key} is different: Netbox value: {nb_value}, Zabbix value: {zb_value}")
        elif field_name in address_keys:
            for nb_addresses, zb_addresses in zip(nb_device.interfaces, zb_device.interfaces):
                if not nb_addresses or not zb_addresses:
                    continue
                for nb_address, zb_address in zip(nb_addresses.addresses, zb_addresses.addresses):
                    if isinstance(nb_address, address_model) and isinstance(zb_address, address_model):
                        for key in address_keys:
                            if hasattr(nb_address, key) and hasattr(zb_address, key):
                                nb_value = getattr(nb_address, key)
                                zb_value = getattr(zb_address, key)
                                if nb_value != zb_value:
                                    updated_fields[f"{key} {nb_address.address}"] = nb_value
                                    setattr(zb_address, key, nb_value)
                                    log.logger.info(f"Address field {key} is different: Netbox value: {nb_value}, Zabbix value: {zb_value}")
    sync_output.add_difference_output(f"Updated fields for {zb_device.name}: {list(updated_fields.keys())}")
    log.logger.info("Zabbix Device before update "+device_service.print_device(zb_device))
    hostgroupids = []
    for hostgroup in zb_device.hostgroup:
        hostgroupids.append(hostgroup['groupid']) if isinstance(hostgroup, dict) else hostgroupids.append(hostgroup)
    update_data_zabbix = zb_device.update_data_zabbix(
        hostid=hostid,
        interface_id=device_service.find_hostinterface_id(hostid),
        hostgroupIds=hostgroupids,
        templateids=[find_template_ids(template) for template in zb_device.templates if template]
    )
    log.logger.info(update_data_zabbix)
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json=update_data_zabbix)
    if response.status_code == 200:
        sync_output.add_difference_output(f"Device {zb_device.name} updated successfully in Zabbix.")
        log.logger.info(f"Device {zb_device.name} updated successfully in Zabbix with response status {response.status_code}.")
    else:
        sync_output.add_difference_output(f"Failed to update device {zb_device.name} in Zabbix: {response.text}")
        log.logger.error(f"Failed to update device {zb_device.name} in Zabbix: {response.text} with response status {response.status_code}.")

def create_netbox_device(device: device_model, sync_output: sync_output_model):
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
        "Accept": "application/json"
    }
    data_netbox = device.create_data_netbox()
    response = requests.post(netbox_ip+"api/dcim/devices/", headers=headers, json=data_netbox)
    if response.status_code == 201:
        sync_output.add_netbox_output(f"Device {device.name} created successfully in Netbox.")
        log.logger.info(f"Device {device.name} created successfully in Netbox.")
    else:
        sync_output.add_netbox_output(f"Failed to create device {device.name} in Netbox: {response.text}")
        log.logger.error(f"Failed to create device {device.name} in Netbox: {response.text} | Request Body: {response.request.body} | Data: {data_netbox}")

def create_zabbix_device(device: device_model,sync_output: sync_output_model):
    """Creates a device in Zabbix based on the provided device model.
    Args:
        device (device_model): The device model to create in Zabbix.
    """
    log.logger.info(f"Creating device {device.name} in Zabbix.")
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    hostgroupids = []
    for hostgroup in device.hostgroup:
        hostgroupids.append(hostgroup['groupid']) if isinstance(hostgroup, dict) else hostgroupids.append(hostgroup)
    if not hostgroupids:
        sync_output.add_zabbix_output(f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device {device.name}.")
        log.logger.error(f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device in Netbox.")
        return
    templateids = [find_template_ids(template) for template in device.templates if template]
    if -1 in templateids:
        sync_output.add_zabbix_output(f"No valid templates found for device {device.name}, cannot create in Zabbix.")
        log.logger.error(f"No valid templates found for device {device.name}, cannot create in Netbox.")
        return
    data_zabbix = device.create_data_zabbix(hostgroupIds=hostgroupids, templateids=templateids)
    log.logger.info(f"Data to be sent to Zabbix: {data_zabbix}")
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json=data_zabbix)
    if response.status_code == 200:
        sync_output.add_zabbix_output(f"Device {device.name} created successfully in Zabbix.")
        log.logger.info(f"Device {device.name} created successfully in Zabbix.")
    else:
        sync_output.add_zabbix_output(f"Failed to create device {device.name} in Zabbix: {response.text}")
        log.logger.error(f"Failed to create device {device.name} in Zabbix: {response.text}")

def sync_netbox_zabbix_devices(differences:list[device_difference_model], netbox_devices: list[device_model], zabbix_devices: list[device_model]) -> sync_output_model:
    """Syncs Netbox and Zabbix devices that don't have matching devices in the other system.
    Args:
        netbox_devices (list[device_model]): List of devices from Netbox.
        zabbix_devices (list[device_model]): List of devices from Zabbix.
    """
    sync_output = sync_output_model()
    log.logger.info("Starting synchronization of Netbox and Zabbix devices.")
    for netbox_device in netbox_devices:
        if not any(zabbix_device.name == netbox_device.name for zabbix_device in zabbix_devices):
            log.logger.info(f"Device {netbox_device.name} found in Netbox but not in Zabbix, creating in Zabbix.")
            create_zabbix_device(netbox_device,sync_output)
    
    # for zabbix_device in zabbix_devices:
    #     if not any(netbox_device.name == zabbix_device.name for netbox_device in netbox_devices):
    #         log.logger.info(f"Device {zabbix_device.name} found in Zabbix but not in Netbox, creating in Netbox.")
    #         create_netbox_device(zabbix_device,sync_output)
    
    for difference in differences:
        log.logger.info(f"Applying differences for device {difference.nb_device.name} and {difference.zb_device.name}.")
        apply_differences(difference, sync_output)
    
    log.logger.info("Synchronization of Netbox and Zabbix devices completed.")
    return sync_output
