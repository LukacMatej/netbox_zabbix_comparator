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
from typing import Any
import requests
from app.logger import logger_conf as log
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.synchonization_output_model import SyncOutput as sync_output_model
from app.device.service import device_service

REQUEST_TIMEOUT = 30


def get_zabbix_host_interfaces(hostid: str) -> list[dict]:
    """Fetches detailed interface information for a Zabbix host.
    Args:
        hostid (str): The Zabbix host ID.
    Returns:
        list[dict]: List of interface details including interfaceid, type, ip, dns, etc.
    """
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return []

    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }

    payload = {
        "jsonrpc": "2.0",
        "method": "hostinterface.get",
        "params": {
            "hostids": hostid,
            "output": ["interfaceid", "type", "ip", "dns", "port", "main"],
        },
        "id": 1,
    }

    try:
        response: requests.Response = requests.post(
            zabbix_ip + "/api_jsonrpc.php",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            json=payload,
        )
        response_json = response.json()

        if "error" in response_json:
            log.logger.error("Error fetching interfaces from Zabbix: %s", response_json["error"])
            return []

        interfaces = response_json.get("result", [])
        log.logger.info("Retrieved %d interface(s) from Zabbix host %s.", len(interfaces), hostid)
        for idx, iface in enumerate(interfaces):
            log.logger.debug("Interface %d: %s", idx, iface)
        return interfaces
    except requests.exceptions.RequestException as e:
        log.logger.error("Exception when fetching interfaces from Zabbix: %s", str(e))
        return []


def add_interface_to_zabbix(hostid: str, interfaces: list[interface_model], sync_output: sync_output_model):
    """Adds new interfaces to a Zabbix host via API.
    Args:
        hostid (str): The Zabbix host ID to add interfaces to.
        interfaces (list[interface_model]): List of interface models to add.
        sync_output (sync_output_model): The synchronization output model to log results.
    """
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return

    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }

    # Get existing interfaces to determine the main interface index
    interface_ids = device_service.find_hostinterface_ids(hostid)
    existing_interface_count = len(interface_ids)

    # Prepare interface data for creation
    interface_params = []
    for index, interface in enumerate(interfaces):
        # The first interface (index 0) should be the main interface if no others exist
        is_main = 1 if existing_interface_count == 0 and index == 0 else 0

        interface_data = {
            "hostid": hostid,
            "type": interface.port_type if interface.port_type in ("1", "2", "3", "4") else "1",
            "main": is_main,
            "useip": 1,
            "ip": (
                str(interface.addresses[0].address).split("/", maxsplit=1)[0]
                if interface.addresses
                else ""
            ),
            "dns": interface.addresses[0].dns_name if interface.addresses else "",
            "port": 161,
        }
        interface_params.append(interface_data)

    payload = {
        "jsonrpc": "2.0",
        "method": "hostinterface.create",
        "params": interface_params,
        "id": 1,
    }

    try:
        log.logger.info("Adding %d interface(s) to Zabbix host %s.", len(interfaces), hostid)
        response: requests.Response = requests.post(
            zabbix_ip + "/api_jsonrpc.php",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            json=payload,
        )
        response_json = response.json()

        if "error" in response_json:
            error_msg = f"Failed to add interfaces to Zabbix host {hostid}: {response_json['error']}"
            sync_output.add_difference_output(error_msg)
            log.logger.error(error_msg)
            return

        if response.status_code == 200:
            interfaceids = response_json.get("result", {}).get("interfaceids", [])
            success_msg = f"Successfully added {len(interfaceids)} interface(s) to Zabbix host {hostid}."
            sync_output.add_difference_output(success_msg)
            log.logger.info(success_msg)
        else:
            error_msg = f"Unexpected status code {response.status_code} when adding interfaces."
            sync_output.add_difference_output(error_msg)
            log.logger.error(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Exception when adding interfaces to Zabbix: {str(e)}"
        sync_output.add_difference_output(error_msg)
        log.logger.error(error_msg)


def remove_interface_from_zabbix(hostid: str, interface_ids: list[int], sync_output: sync_output_model):
    """Removes interfaces from a Zabbix host via API.
    Args:
        hostid (str): The Zabbix host ID (for logging purposes).
        interface_ids (list[int]): List of interface IDs to remove.
        sync_output (sync_output_model): The synchronization output model to log results.
    """
    if not interface_ids:
        log.logger.info("No interfaces to remove from Zabbix host %s.", hostid)
        return

    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return

    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }

    payload = {
        "jsonrpc": "2.0",
        "method": "hostinterface.delete",
        "params": interface_ids,
        "id": 1,
    }

    try:
        log.logger.info("Removing %d interface(s) from Zabbix host %s.", len(interface_ids), hostid)
        response: requests.Response = requests.post(
            zabbix_ip + "/api_jsonrpc.php",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            json=payload,
        )
        response_json = response.json()

        if "error" in response_json:
            error_msg = f"Failed to remove interfaces from Zabbix host {hostid}: {response_json['error']}"
            sync_output.add_difference_output(error_msg)
            log.logger.error(error_msg)
            return

        if response.status_code == 200:
            interfaceids = response_json.get("result", {}).get("interfaceids", [])
            success_msg = f"Successfully removed {len(interfaceids)} interface(s) from Zabbix host {hostid}."
            sync_output.add_difference_output(success_msg)
            log.logger.info(success_msg)
        else:
            error_msg = f"Unexpected status code {response.status_code} when removing interfaces."
            sync_output.add_difference_output(error_msg)
            log.logger.error(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Exception when removing interfaces from Zabbix: {str(e)}"
        sync_output.add_difference_output(error_msg)
        log.logger.error(error_msg)


def find_hostgroup_id(hostgroup_name: str) -> int:
    """Finds the Zabbix hostgroup ID based on the provided hostgroup name.
    Args:
        hostgroup_name (str): The name of the hostgroup to find.
    Returns:
        int: The ID of the hostgroup if found, otherwise -1.
    """
    log.logger.info("Finding Zabbix hostgroup ID for %s.", hostgroup_name)
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return -1
    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response: requests.Response = requests.post(
        zabbix_ip + "/api_jsonrpc.php",
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
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return -1
    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    response: requests.Response = requests.post(
        zabbix_ip + "/api_jsonrpc.php",
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
        data: Any = response.json()
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
    old_templateids: list[str] = zb_device.templates
    different_fields: list[str] = differences.differences[
        0
    ]  # tuple: (different_fields, same_fields)

    def extract_field_name(field: str):
        if "(" in field:
            return field.split("(")[0].strip()
        return field.strip()

    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return
    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    hostid: str | None = None
    response: requests.Response = requests.post(
        zabbix_ip + "/api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json={
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {"filter": {"host": [zb_device.name]}},
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
    updated_fields: dict[str, str] = {}
    interface_keys: list[str] = ["port_type"]
    address_keys: list[str] = ["address", "dns_name"]
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

    # Handle missing and extra interfaces
    interfaces_to_add = []
    interface_ids_to_remove = []

    log.logger.info("Processing interface differences. Different fields: %s", different_fields)

    # Get all Zabbix interfaces once if needed
    zb_interface_details: list[dict] = []
    has_interface_changes = any("missing in Zabbix" in field or "extra in Zabbix" in field for field in different_fields)
    log.logger.info("Has interface changes: %s", has_interface_changes)

    if has_interface_changes:
        zb_interface_details = get_zabbix_host_interfaces(hostid)
        log.logger.info("Retrieved %d interface details from Zabbix", len(zb_interface_details))

    for field in different_fields:
        log.logger.debug("Processing field: %s", field)

        if "missing in Zabbix" in field:
            log.logger.info("Field indicates missing interface: %s", field)
            # Extract port_type from message: "Interface with port_type 'X' missing in Zabbix"
            port_type = field.split("'")[1] if "'" in field else ""
            log.logger.info("Extracted port_type for missing interface: %s", port_type)

            if port_type:
                # Find matching interface in NetBox by port_type
                nb_matching_interfaces = [
                    iface for iface in nb_device.interfaces
                    if getattr(iface, "port_type", "") == port_type
                ]
                log.logger.info("Found %d matching interfaces in NetBox with port_type '%s'", len(nb_matching_interfaces), port_type)

                if nb_matching_interfaces:
                    interfaces_to_add.extend(nb_matching_interfaces)
                    log.logger.info(
                        "Added %d interface(s) with port_type '%s' to add list for device %s.",
                        len(nb_matching_interfaces),
                        port_type,
                        zb_device.name,
                    )
                    sync_output.add_difference_output(
                        f"Interface with port_type '{port_type}' will be added to {zb_device.name} in Zabbix."
                    )

        elif "extra in Zabbix" in field:
            log.logger.info("Field indicates extra interface: %s", field)
            # Extract port_type from message: "Interface with port_type 'X' extra in Zabbix"
            port_type = field.split("'")[1] if "'" in field else ""
            log.logger.info("Extracted port_type for extra interface: %s", port_type)

            if port_type:
                # Collect interfaces to remove by port_type from the device model
                interfaces_to_remove_by_type = [
                    iface for iface in zb_device.interfaces
                    if getattr(iface, "port_type", "") == port_type
                ]
                log.logger.info("Found %d interface(s) in device model with port_type '%s'", len(interfaces_to_remove_by_type), port_type)
                log.logger.debug("Zabbix interfaces in device model: %s",
                    [(getattr(iface, "port_type", ""), [addr.address for addr in iface.addresses if iface.addresses]) for iface in zb_device.interfaces])

                if interfaces_to_remove_by_type:
                    # Match interfaces from device model by IP/DNS to get interface IDs from Zabbix
                    for iface_to_remove in interfaces_to_remove_by_type:
                        iface_ip = (
                            str(iface_to_remove.addresses[0].address).split("/", maxsplit=1)[0]
                            if iface_to_remove.addresses
                            else ""
                        )
                        iface_dns = (
                            iface_to_remove.addresses[0].dns_name
                            if iface_to_remove.addresses
                            else ""
                        )
                        log.logger.info("Looking for interface to remove with IP: %s, DNS: %s, port_type: %s", iface_ip, iface_dns, port_type)

                        # Match by IP or DNS in the Zabbix interface details
                        for zb_iface in zb_interface_details:
                            zb_iface_ip = zb_iface.get("ip", "")
                            zb_iface_dns = zb_iface.get("dns", "")
                            log.logger.debug("Comparing with Zabbix interface - IP: %s, DNS: %s, type: %s", zb_iface_ip, zb_iface_dns, zb_iface.get("type"))

                            if (zb_iface_ip == iface_ip or zb_iface_dns == iface_dns) and zb_iface_ip:
                                interface_ids_to_remove.append(zb_iface["interfaceid"])
                                log.logger.info(
                                    "Found interface ID %s to remove (IP: %s, port_type: '%s')",
                                    zb_iface["interfaceid"],
                                    zb_iface_ip,
                                    port_type,
                                )
                                break
                else:
                    log.logger.warning("No interfaces found in device model with port_type '%s'. Available port_types: %s",
                        port_type,
                        [getattr(iface, "port_type", "N/A") for iface in zb_device.interfaces])

                sync_output.add_difference_output(
                    f"Extra interface with port_type '{port_type}' will be removed from {zb_device.name} in Zabbix."
                )

    log.logger.info("Interfaces to add: %d, Interface IDs to remove: %d", len(interfaces_to_add), len(interface_ids_to_remove))

    # Make API calls to add interfaces to Zabbix
    if interfaces_to_add:
        log.logger.info("Making API call to add %d interface(s)", len(interfaces_to_add))
        add_interface_to_zabbix(hostid, interfaces_to_add, sync_output)

    # Make API calls to remove interfaces from Zabbix
    if interface_ids_to_remove:
        log.logger.info("Making API call to remove %d interface(s)", len(interface_ids_to_remove))
        remove_interface_from_zabbix(hostid, interface_ids_to_remove, sync_output)

    # Prefer updated Zabbix values, but fall back to Netbox if source data is missing.
    hostgroup_source = zb_device.hostgroup if zb_device.hostgroup else nb_device.hostgroup
    hostgroupids = find_zabbix_hostgroup_ids(hostgroup_source)
    template_source = zb_device.templates if zb_device.templates else nb_device.templates

    interface_ids: list[int] = device_service.find_hostinterface_ids(hostid)
    templateids: list[int] = [find_template_ids(template) for template in template_source if template]
    update_data_zabbix = zb_device.update_data_zabbix(
        name=nb_device.name,
        hostid=hostid,
        interface_ids=interface_ids,
        hostgroupids=hostgroupids,
        templateids=templateids,
        include_interfaces=False,
    )

    interface_update_data_zabbix = zb_device.update_interface_data_zabbix(interface_ids)
    log.logger.info(interface_update_data_zabbix)
    interface_response: requests.Response = requests.post(
        zabbix_ip + "/api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json=interface_update_data_zabbix,
    )
    interface_response_json = interface_response.json()
    if "error" not in interface_response_json:
        sync_output.add_difference_output(
            f"Interface for device {zb_device.name} updated successfully in Zabbix."
        )
        log.logger.info(
            "Interface for device %s updated successfully in Zabbix with response status %s.",
            zb_device.name,
            interface_response.status_code,
        )
    else:
        sync_output.add_difference_output(
            f"Failed to update interface for device {zb_device.name} in Zabbix: {interface_response.text}"
        )
        log.logger.error(
            "Failed to update interface for device %s in Zabbix: %s with response status %s.",
            zb_device.name,
            interface_response.text,
            interface_response.status_code,
        )

    log.logger.info(update_data_zabbix)
    response: requests.Response = requests.post(
        zabbix_ip + "/api_jsonrpc.php",
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
    else:
        sync_output.add_difference_output(
            f"Device {zb_device.name} updated successfully in Zabbix."
        )
        log.logger.info(
            "Device %s updated successfully in Zabbix with response status %s.",
            zb_device.name,
            response.status_code,
        )

def create_zabbix_device(device: device_model, sync_output: sync_output_model):
    """Creates a device in Zabbix based on the provided device model.
    Args:
        device (device_model): The device model to create in Zabbix.
    """
    log.logger.info("Creating device %s in Zabbix.", device.name)
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return
    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    if not isinstance(device.hostgroup, list):
        device.hostgroup = [device.hostgroup]
    default_hostgroup: str = os.environ.get("ZABBIX_DEFAULT_HOSTGROUP", "Netbox")
    if not default_hostgroup in device.hostgroup:
        device.hostgroup = device.hostgroup.append(default_hostgroup) or [default_hostgroup]
    hostgroupids: list[int] = find_zabbix_hostgroup_ids(device.hostgroup)
    if not hostgroupids or -1 in hostgroupids:
        sync_output.add_zabbix_output(
            f"Hostgroup {device.hostgroup} not found in Zabbix, cannot create device {device.name}."
        )
        log.logger.error(
            "Hostgroup %s not found in Zabbix, cannot create device in Netbox.", device.hostgroup
        )
        return
    templateids: list[int] = [
        find_template_ids(template) for template in device.templates if template
        ]
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
    response: requests.Response = requests.post(
        zabbix_ip + "/api_jsonrpc.php",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        json=data_zabbix,
    )
    reponse_json: Any = response.json()
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
    default_hostgroup = os.environ.get("ZABBIX_DEFAULT_HOSTGROUP", "Netbox")
    if hostgroup_names is None:
        hostgroup_names = [default_hostgroup]
    # Normalize common input shapes (str, dict, tuple/set) to a list for iteration.
    if isinstance(hostgroup_names, str):
        hostgroup_names = [hostgroup_names]
    elif isinstance(hostgroup_names, dict):
        hostgroup_names = [hostgroup_names]
    elif isinstance(hostgroup_names, (tuple, set)):
        hostgroup_names = list(hostgroup_names)
    elif not isinstance(hostgroup_names, list):
        log.logger.warning(
            "Unexpected hostgroup_names type %s, coercing to single-item list",
            type(hostgroup_names).__name__,
        )
        hostgroup_names = [hostgroup_names]
    # Extract names from the list, handling both strings and dictionaries
    names_to_check = []
    for item in hostgroup_names:
        if isinstance(item, str):
            normalized_item = item.strip()
            if normalized_item:
                names_to_check.append(normalized_item)
        elif isinstance(item, dict) and "name" in item:
            normalized_item = str(item["name"]).strip()
            if normalized_item:
                names_to_check.append(normalized_item)
        else:
            log.logger.warning("Unexpected hostgroup format: %s", item)
            continue

    if not names_to_check:
        log.logger.info(
            "No valid hostgroup provided, falling back to default hostgroup %s.",
            default_hostgroup,
        )
        names_to_check = [default_hostgroup]

    group_ids: list[int] = []
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return [-1] * len(names_to_check)
    headers: dict[str, str] = {
        "Authorization": f"Bearer {zabbix_key}",
        "Content-Type": "application/json-rpc",
    }
    for hostgroup_name in names_to_check:
        log.logger.info("Finding Zabbix hostgroup ID for %s.", hostgroup_name)
        response = requests.post(
            zabbix_ip + "/api_jsonrpc.php",
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
                    zabbix_ip + "/api_jsonrpc.php",
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
    sync_output: sync_output_model = sync_output_model()
    log.logger.info("Starting synchronization of Netbox and Zabbix devices.")
    for netbox_device in netbox_devices:
        log.logger.info(
            "Device %s found in Netbox but not in Zabbix, creating in Zabbix.",
            netbox_device.name,
        )
        create_zabbix_device(netbox_device, sync_output)
    device_service.map_port_type_device(netbox_devices, zabbix_devices,numbered=True)
    for diffrence in differences:
        device_service.map_port_type_device(
            [diffrence.nb_device], [diffrence.zb_device],numbered=True
        )
    for difference in differences:
        log.logger.info(
            "Applying differences for device %s and %s.",
            difference.nb_device.name,
            difference.zb_device.name,
        )
        apply_differences(difference, sync_output)

    log.logger.info("Synchronization of Netbox and Zabbix devices completed.")
    return sync_output
