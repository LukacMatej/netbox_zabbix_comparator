import requests
import os
import re
from app.logger import logger_conf as log
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.synchonization_output_model import SyncOutput as sync_output_model

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

def apply_differences(differences: device_difference_model, sync_output: sync_output_model):
    """Applies the differences between Netbox and Zabbix devices.
    Args:
        differences (device_difference_model): The differences between the Netbox and Zabbix devices.
        sync_output (sync_output_model): The synchronization output model to log the results.
    """
    nb_device: device_model = differences.nb_device
    zb_device: device_model = differences.zb_device
    different_fields: list[str] = differences.differences[0]  # tuple: (different_fields, same_fields)

    # Map field names in different_fields to actual attribute names
    # If the field is in the format 'field (x != y), ...', extract the field name
    def extract_field_name(field: str):
        if '(' in field:
            return field.split('(')[0].strip()
        return field.strip()

    # Prepare Zabbix API update call
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    
    hostid = None
    # Try to get hostid from zabbix by name
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

    updated_fields = {}
    for field in different_fields:
        field_name = extract_field_name(field)
        # Update the Zabbix field with Netbox data if the field exists in both
        if hasattr(nb_device, field_name) and hasattr(zb_device, field_name):
            nb_value = getattr(nb_device, field_name)
            # Handle updates for fields inside interfaces and addresses lists
            if hasattr(nb_device, "interfaces") and hasattr(zb_device, "interfaces"):
                # Check if the field is inside any interface
                for nb_iface, zb_iface in zip(nb_device.interfaces, zb_device.interfaces):
                    if hasattr(nb_iface, field_name) and hasattr(zb_iface, field_name):
                        nb_iface_value = getattr(nb_iface, field_name)
                        setattr(zb_iface, field_name, nb_iface_value)
                        updated_fields.setdefault("interfaces", nb_device.interfaces)
                        log.logger.info(f"Updating Zabbix interface field '{field_name}' with Netbox value: {nb_iface_value}")
                    # Check if the field is inside any address within interfaces
                    if hasattr(nb_iface, "addresses") and hasattr(zb_iface, "addresses"):
                        for nb_addr, zb_addr in zip(nb_iface.addresses, zb_iface.addresses):
                            if hasattr(nb_addr, field_name) and hasattr(zb_addr, field_name):
                                nb_addr_value = getattr(nb_addr, field_name)
                                setattr(zb_addr, field_name, nb_addr_value)
                                updated_fields.setdefault("addresses", [])
                                updated_fields["addresses"].append(nb_iface.addresses)
                                log.logger.info(f"Updating Zabbix address field '{field_name}' in interface '{nb_iface}' with Netbox value: {nb_addr_value}")
            
            if not (field_name in [f for iface in getattr(nb_device, "interfaces", []) for f in vars(iface)] or
                    field_name in [f for addr in getattr(nb_device, "addresses", []) for f in vars(addr)]):
                updated_fields[field_name] = nb_value
                log.logger.info(f"Updating Zabbix field '{field_name}' with Netbox value: {nb_value}")
                
    # Build update params
    params = {"hostid": hostid}
    # Map updated fields to Zabbix API fields
    if "name" in updated_fields:
        params["host"] = updated_fields["name"]
    if "description" in updated_fields:
        params["description"] = updated_fields["description"]
    if "status" in updated_fields:
        params["status"] = 0 if updated_fields["status"] == "Active" else 1
    if "templates" in updated_fields:
        # Convert template names to IDs
        templateids = [find_template_ids(t) for t in updated_fields["templates"] if t]
        params["templates"] = [{"templateid": tid} for tid in templateids if tid != -1]
    if "hostgroup" in updated_fields:
        groupid = find_zabbix_hostgroup_id(updated_fields["hostgroup"])
        if groupid != -1:
            params["groups"] = [{"groupid": groupid}]
    if "interfaces" in updated_fields:
        from app.device.models.device_model import dict_interfaces_zb
        params["interfaces"] = dict_interfaces_zb(updated_fields["interfaces"])

    # Log updated fields to sync_output
    sync_output.add_difference_output(f"Updated fields for {zb_device.name}: {list(updated_fields.keys())}")

    # Send update to Zabbix
    update_payload = {
        "jsonrpc": "2.0",
        "method": "host.update",
        "params": params,
        "id": 1
    }
    response = requests.post(zabbix_ip+"api_jsonrpc.php", headers=headers, json=update_payload)
    if response.status_code == 200:
        sync_output.add_difference_output(f"Device {zb_device.name} updated successfully in Zabbix.")
        log.logger.info(f"Device {zb_device.name} updated successfully in Zabbix.")
    else:
        sync_output.add_difference_output(f"Failed to update device {zb_device.name} in Zabbix: {response.text}")
        log.logger.error(f"Failed to update device {zb_device.name} in Zabbix: {response.text}")
            

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
    hostgroupid = find_zabbix_hostgroup_id(device.hostgroup)
    if hostgroupid == -1:
        sync_output.add_zabbix_output(f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device {device.name}.")
        log.logger.error(f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device in Netbox.")
        return
    templateids = [find_template_ids(template) for template in device.templates if template]
    if -1 in templateids:
        sync_output.add_zabbix_output(f"No valid templates found for device {device.name}, cannot create in Zabbix.")
        log.logger.error(f"No valid templates found for device {device.name}, cannot create in Netbox.")
        return
    data_zabbix = device.create_data_zabbix(hostgroupId=hostgroupid, templateids=templateids)
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
