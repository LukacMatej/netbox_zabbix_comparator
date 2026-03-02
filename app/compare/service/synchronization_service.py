"""
Synchronization service module for managing Netbox and Zabbix device synchronization.
This module provides functionality to synchronize devices between Netbox and Zabbix systems,
including finding hosts, templates, and hostgroups, applying differences between systems,
and creating new devices in either system.
Functions:
    find_hostgroup_id(hostgroup_name: str) -> int:
        Retrieves the Zabbix hostgroup ID for a given hostgroup name.
    find_template_ids(template_name: str) -> int:
        Retrieves the Zabbix template ID for a given template name.
    apply_differences(differences: device_difference_model, sync_output: sync_output_model) -> None:
        Applies field differences between Netbox and Zabbix device instances by updating
        the Zabbix device with Netbox values.
    create_netbox_device(device: device_model, sync_output: sync_output_model) -> None:
        Creates a new device in the Netbox system.
    create_zabbix_device(device: device_model, sync_output: sync_output_model) -> None:
        Creates a new device in the Zabbix system with associated hostgroups and templates.
    find_zabbix_hostgroup_ids(hostgroup_names) -> list[int]:
        Finds or creates Zabbix hostgroup IDs for the given hostgroup names.
        Supports string, list of strings, or list of dictionaries as input.
    sync_netbox_zabbix_devices(differences: list[device_difference_model],
                               netbox_devices: list[device_model],
                               zabbix_devices: list[device_model]) -> sync_output_model:
        Orchestrates the synchronization process between Netbox and Zabbix systems,
        creating missing devices and applying detected differences.

"""

import os
import requests
from app.logger import logger_conf as log
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.synchonization_output_model import SyncOutput as sync_output_model
from app.device.service import device_service

REQUEST_TIMEOUT = 10


def find_hostgroup_id(hostgroup_name: str) -> int:
    """Finds the Zabbix hostgroup ID based on the provided hostgroup name.
    Args:
        hostgroup_name (str): The name of the hostgroup to find.
    Returns:
        int: The ID of the hostgroup if found, otherwise -1.
    """
    log.logger.info("Finding Zabbix hostgroup ID for %s.", hostgroup_name)
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response = requests.post(
        zabbix_ip + "api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json={
            "jsonrpc": "2.0",
            "method": "hostgroup.get",
            "params": {"filter": {"name": [hostgroup_name]}},
            "id": 1,
        },
    )
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            log.logger.error("Error in Zabbix API response: %s", data["error"])
            return -1
        if data["result"]:
            group_id = data["result"][0]["groupid"]
            log.logger.info("Found Zabbix hostgroup ID: %s for %s.", group_id, hostgroup_name)
            return int(group_id)
    log.logger.error("Failed to find Zabbix hostgroup ID for %s: %s", hostgroup_name, response.text)
    return -1


def find_template_ids(template_name: str) -> int:
    """Finds the Zabbix template ID based on the provided template name.
    Args:
        template_name (str): The name of the template to find.
    Returns:
        int: The ID of the template if found, otherwise -1.
    """
    log.logger.info("Finding Zabbix template ID for %s.", template_name)
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response = requests.post(
        zabbix_ip + "api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json={
            "jsonrpc": "2.0",
            "method": "template.get",
            "params": {"filter": {"host": [template_name]}},
            "id": 1,
        },
    )
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            log.logger.error("Error in Zabbix API response: %s", data["error"])
            return -1
        if data["result"]:
            template_id = data["result"][0]["templateid"]
            log.logger.info("Found Zabbix template ID: %s for %s.", template_id, template_name)
            return int(template_id)
    log.logger.error("Failed to find Zabbix template ID for %s: %s", template_name, response.text)
    return -1


def apply_differences(differences: device_difference_model, sync_output: sync_output_model):
    """Applies the differences between Netbox and Zabbix devices.
    Args:
        differences (device_difference_model):
            The differences between the Netbox and Zabbix devices.
        sync_output (sync_output_model): The synchronization output model to log the results.
    """
    nb_device: device_model = differences.nb_device
    zb_device: device_model = differences.zb_device
    different_fields: list[str] = differences.differences[
        0
    ]  # tuple: (different_fields, same_fields)

    def extract_field_name(field: str):
        if "(" in field:
            return field.split("(")[0].strip()
        return field.strip()

    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    hostid = None
    response = requests.post(
        zabbix_ip + "api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json={
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {"filter": {"host": {zb_device.name}}},
            "id": 1,
        },
    )
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            sync_output.add_difference_output(f"Error in Zabbix API response: {data['error']}")
            log.logger.error("Error in Zabbix API response: %s", data["error"])
            return
        if data["result"]:
            hostid = data["result"][0]["hostid"]
    if not hostid:
        sync_output.add_difference_output(
            f"Failed to find Zabbix hostid for {zb_device.name}, cannot update device."
        )
        log.logger.error(
            "Failed to find Zabbix hostid for %s, cannot update device.", zb_device.name
        )
        return
    log.logger.info("Zabbix Device before update %s", device_service.print_device(zb_device))
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
                log.logger.info(
                    "Field %s is different: Netbox value: %s, Zabbix value: %s",
                    field_name,
                    nb_value,
                    zb_value,
                )
        elif field_name in interface_keys:
            # Handle interface fields
            nb_interfaces: list[interface_model] = nb_device.interfaces
            zb_interfaces: list[interface_model] = zb_device.interfaces
            for nb_interface, zb_interface in zip(nb_interfaces, zb_interfaces):
                if isinstance(nb_interface, interface_model) and isinstance(
                    zb_interface, interface_model
                ):
                    for key in interface_keys:
                        if hasattr(nb_interface, key) and hasattr(zb_interface, key):
                            nb_value = getattr(nb_interface, key)
                            zb_value = getattr(zb_interface, key)
                            if nb_value != zb_value:
                                updated_fields[f"{key} {nb_interface.name}"] = nb_value
                                setattr(zb_interface, key, nb_value)
                                log.logger.info(
                                    "Interface field %s is different: "
                                    "Netbox value: %s, Zabbix value: %s",
                                    key,
                                    nb_value,
                                    zb_value,
                                )
        elif field_name in address_keys:
            for nb_addresses, zb_addresses in zip(
                nb_device.interfaces, zb_device.interfaces
            ):
                if not nb_addresses or not zb_addresses:
                    continue
                for nb_address, zb_address in zip(
                    nb_addresses.addresses, zb_addresses.addresses
                ):
                    if isinstance(nb_address, address_model) and isinstance(
                        zb_address, address_model
                    ):
                        for key in address_keys:
                            if hasattr(nb_address, key) and hasattr(zb_address, key):
                                nb_value = getattr(nb_address, key)
                                zb_value = getattr(zb_address, key)
                                if nb_value != zb_value:
                                    updated_fields[f"{key} {nb_address.address}"] = nb_value
                                    setattr(zb_address, key, nb_value)
                                    log.logger.info(
                                        "Address field %s is different: "
                                        "Netbox value: %s, Zabbix value: %s",
                                        key,
                                        nb_value,
                                        zb_value,
                                    )
    sync_output.add_difference_output(
        f"Updated fields for {zb_device.name}: {list(updated_fields.keys())}"
    )
    log.logger.info("Zabbix Device after update %s", device_service.print_device(zb_device))

    # Use the find_zabbix_hostgroup_ids function to get proper hostgroup IDs
    hostgroupids = find_zabbix_hostgroup_ids(zb_device.hostgroup)

    update_data_zabbix = zb_device.update_data_zabbix(
        name=nb_device.name,
        hostid=hostid,
        interface_id=device_service.find_hostinterface_id(hostid),
        hostgroupids=hostgroupids,
        templateids=[find_template_ids(template) for template in zb_device.templates if template],
    )
    log.logger.info(update_data_zabbix)
    response = requests.post(
        zabbix_ip + "api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json=update_data_zabbix,
    )
    response_json = response.json()
    if "error" in response_json:
        sync_output.add_difference_output(
            f"Error in Zabbix API response: {response_json['error']['data']}"
        )
        log.logger.error("Error in Zabbix API response: %s", response_json["error"])
        return
    if response.status_code == 200:
        sync_output.add_difference_output(
            f"Device {zb_device.name} updated successfully in Zabbix."
        )
        log.logger.info(
            "Device %s updated successfully in Zabbix with response status %s.",
            zb_device.name,
            response.status_code,
        )
    else:
        sync_output.add_difference_output(
            f"Failed to update device {zb_device.name} in Zabbix: {response.text}"
        )
        log.logger.error(
            "Failed to update device %s in Zabbix: %s with response status %s.",
            zb_device.name,
            response.text,
            response.status_code,
        )


def create_netbox_device(device: device_model, sync_output: sync_output_model):
    """Creates a device in Netbox based on the provided device model.
    Args:
        device (device_model): The device model to create in Netbox.
    """
    log.logger.info("Creating device %s in Netbox.", device.name)
    netbox_ip = os.environ.get("NETBOX_IP")
    netbox_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {netbox_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data_netbox = device.create_data_netbox()
    response = requests.post(
        netbox_ip + "api/dcim/devices/",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json=data_netbox,
    )
    if response.status_code == 201:
        sync_output.add_netbox_output(f"Device {device.name} created successfully in Netbox.")
        log.logger.info("Device %s created successfully in Netbox.", device.name)
    else:
        sync_output.add_netbox_output(
            f"Failed to create device {device.name} in Netbox: {response.text}"
        )
        log.logger.error(
            "Failed to create device %s in Netbox: %s | Request Body: %s | Data: %s",
            device.name,
            response.text,
            response.request.body,
            data_netbox,
        )


def create_zabbix_device(device: device_model, sync_output: sync_output_model):
    """Creates a device in Zabbix based on the provided device model.
    Args:
        device (device_model): The device model to create in Zabbix.
    """
    log.logger.info("Creating device %s in Zabbix.", device.name)
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    default_hostgroup = os.environ.get("ZABBIX_DEFAULT_HOSTGROUP", "Netbox")
    if not "Netbox" in device.hostgroup:
        device.hostgroup.append(default_hostgroup)
    hostgroupids = find_zabbix_hostgroup_ids(device.hostgroup)
    if not hostgroupids or -1 in hostgroupids:
        sync_output.add_zabbix_output(
            f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device {device.name}."
        )
        log.logger.error(
            "Hostgroup %s not found in Zabbix, cannot create device in Netbox.", device.hostgroup
        )
        return
    templateids = [find_template_ids(template) for template in device.templates if template]
    if -1 in templateids:
        sync_output.add_zabbix_output(
            f"No valid templates found for device {device.name}, cannot create in Zabbix."
        )
        log.logger.error(
            "No valid templates found for device %s, cannot create in Netbox.", device.name
        )
        return
    data_zabbix = device.create_data_zabbix(hostgroupids=hostgroupids, templateids=templateids)
    log.logger.info("Data to be sent to Zabbix: %s", data_zabbix)
    response = requests.post(
        zabbix_ip + "api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json=data_zabbix,
    )
    reponse_json = response.json()
    if "error" in reponse_json:
        sync_output.add_zabbix_output(
            f"Error in Zabbix API response: {reponse_json['error']['data']}"
        )
        log.logger.error("Error in Zabbix API response: %s", reponse_json["error"])
        return
    if response.status_code == 200:
        sync_output.add_zabbix_output(f"Device {device.name} created successfully in Zabbix.")
        log.logger.info("Device %s created successfully in Zabbix.", device.name)
    else:
        sync_output.add_zabbix_output(
            f"Failed to create device {device.name} in Zabbix: {response.text}"
        )
        log.logger.error("Failed to create device %s in Zabbix: %s", device.name, response.text)


def find_zabbix_hostgroup_ids(hostgroup_names) -> list[int]:
    """
    Finds the Zabbix hostgroup IDs for a list of hostgroup names.
    Args:
        hostgroup_names: The names of the hostgroups to find or create. Can be:
                        - str: single hostgroup name
                        - list[str]: list of hostgroup names
                        - list[dict]: list of dictionaries with 'name' key
    Returns:
        list[int]: The IDs of the hostgroups, -1 for any that could not be found or created.
    """
    # If hostgroup_names is a string (not a list), convert to list
    if isinstance(hostgroup_names, str):
        hostgroup_names = [hostgroup_names]
    # Extract names from the list, handling both strings and dictionaries
    names_to_check = []
    for item in hostgroup_names:
        if isinstance(item, str):
            names_to_check.append(item)
        elif isinstance(item, dict) and "name" in item:
            names_to_check.append(item["name"])
        else:
            log.logger.warning("Unexpected hostgroup format: %s", item)
            continue

    group_ids = []
    zabbix_ip = os.environ.get("ZABBIX_IP")
    zabbix_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    for hostgroup_name in names_to_check:
        log.logger.info("Finding Zabbix hostgroup ID for %s.", hostgroup_name)
        response = requests.post(
            zabbix_ip + "api_jsonrpc.php",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            json={
                "jsonrpc": "2.0",
                "method": "hostgroup.get",
                "params": {"filter": {"name": [hostgroup_name]}},
                "id": 1,
            },
        )
        log.logger.info(
            "Response from Zabbix for hostgroup get: %s, status code: %s",
            response.text,
            response.status_code,
        )
        group_id = -1
        reponse_json = response.json()
        if "error" in reponse_json:
            log.logger.error("Error in Zabbix API response: %s", reponse_json["error"])
            group_ids.append(-1)
            continue
        if response.status_code == 200:
            data = response.json()
            if data["result"]:
                group_id = int(data["result"][0]["groupid"])
                log.logger.info("Found Zabbix hostgroup ID: %s for %s.", group_id, hostgroup_name)
            else:
                create_response = requests.post(
                    zabbix_ip + "api_jsonrpc.php",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    json={
                        "jsonrpc": "2.0",
                        "method": "hostgroup.create",
                        "params": {"name": hostgroup_name},
                        "id": 1,
                    },
                )
                create_json = create_response.json()
                if create_response.status_code == 200 and "error" not in create_json:
                    group_id = int(create_json["result"]["groupids"][0])
                    log.logger.info(
                        "Created Zabbix hostgroup ID: %s for %s.",
                        group_id,
                        hostgroup_name,
                    )
        if group_id == -1:
            log.logger.info(
                "Failed to find Zabbix hostgroup ID for %s: %s", hostgroup_name, response.text
            )
        group_ids.append(group_id)
    return group_ids


def sync_netbox_zabbix_devices(
    differences: list[device_difference_model],
    netbox_devices: list[device_model],
    zabbix_devices: list[device_model],
) -> sync_output_model:
    """Syncs Netbox and Zabbix devices that don't have matching devices in the other system.
    Args:
        netbox_devices (list[device_model]): List of devices from Netbox.
        zabbix_devices (list[device_model]): List of devices from Zabbix.
    """
    sync_output = sync_output_model()
    log.logger.info("Starting synchronization of Netbox and Zabbix devices.")
    for netbox_device in netbox_devices:
        if not any(zabbix_device.name == netbox_device.name for zabbix_device in zabbix_devices):
            log.logger.info(
                "Device %s found in Netbox but not in Zabbix, creating in Zabbix.",
                netbox_device.name,
            )
            create_zabbix_device(netbox_device, sync_output)

    # for zabbix_device in zabbix_devices:
    #     if not any(
    #         netbox_device.name == zabbix_device.name
    #         for netbox_device in netbox_devices
    #     ):
    #         log.logger.info(
    #             "Device %s found in Zabbix but not in Netbox, creating in Netbox.",
    #             zabbix_device.name,
    #         )
    #         create_netbox_device(zabbix_device,sync_output)

    for difference in differences:
        log.logger.info(
            "Applying differences for device %s and %s.",
            difference.nb_device.name,
            difference.zb_device.name,
        )
        apply_differences(difference, sync_output)

    log.logger.info("Synchronization of Netbox and Zabbix devices completed.")
    return sync_output
