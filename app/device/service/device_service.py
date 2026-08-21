"""
Device service module for synchronizing devices between Netbox and Zabbix APIs.
This module provides utilities for:
- Fetching device information from Netbox and Zabbix
- Finding device-related IDs (sites, device types, roles, interfaces)
- Formatting device data (MAC addresses, status, port types)
- Comparing and printing device differences
- Mapping and uniforming device data structures
Functions:
    find_hostinterface_id(hostid: str) -> int:
        Finds the interface ID for a given Zabbix host ID.
  find_nb_site_id(site_name: str) -> int: Finds the Netbox site ID by site name.
    find_nb_device_type_id(device_type: str) -> int:
        Finds the Netbox device type ID by device type name.
    find_nb_device_role_id(device_role: str) -> int:
        Finds the Netbox device role ID by device role name.
  format_address(address: str) -> str: Extracts IP address from CIDR notation.
  formatStatus(status: str) -> str: Converts device status to standardized format.
  formatMac(mac: str) -> str: Formats MAC address to Cisco notation (XXXX.XXXX.XXXX).
  print_differences(difference_model: list) -> str: Formats device differences for display.
  print_devices(nb_device_list: list) -> str: Formats multiple devices for display.
  print_device(device: device_model) -> str: Formats a single device for display.
    get_nb_devices(key: str, ip: str) -> list[device_model] | str:
        Retrieves devices from Netbox API.
    get_zb_devices(key: str, ip: str) -> list[device_model] | str:
        Retrieves devices from Zabbix API.
  formatPortType(port_type: str) -> str: Maps port type to Zabbix compatible format.
  uniformPortType(port_type: str) -> str: Converts port type to human-readable format.
    mapPortTypeDevices(nb_devices: list, zb_devices: list) -> None:
        Uniforms port types across device lists.
    uniformOutputText(
            differences: list, netbox_devices: list, zabbix_devices: list
    ) -> None:
    Normalizes output formatting for differences and device lists.
Dependencies:
  - requests: For HTTP communication with APIs
  - re: For regular expression operations
  - os: For environment variable access
  - app.device.models: Device data models
  - app.logger: Logging module

"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any

import requests

from app.device.models.address_model import Address as address_model
from app.device.models.device_model import Device as device_model
from app.device.models.difference_model import DeviceDifference as difference_model
from app.device.models.interface_model import Interface as interface_model
from app.logger import logger_conf as log

# pylint: disable=line-too-long


def find_hostinterface_ids(hostid: str) -> list[int]:
    """
    Finds the interface IDs for a given Zabbix host ID.
    Args:
      hostid (str): The Zabbix host ID.
    Returns:
      list[int]: A list of interface IDs if found, otherwise an empty list.
    """
    zb_url = os.environ.get("ZABBIX_IP")
    zb_key = os.environ.get("ZABBIX_KEY")
    headers = {
        "Authorization": f"Bearer {zb_key}",
        "Content-Type": "application/json-rpc",
    }
    payload = {
        "jsonrpc": "2.0",
        "method": "hostinterface.get",
        "params": {"hostids": hostid, "output": ["interfaceid"]},
        "id": 1,
    }
    try:
        log.logger.info("Finding Zabbix interface IDs for hostid %s.", hostid)
        response = requests.post(
            f"{zb_url}/api_jsonrpc.php", headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()
        result = json.loads(response.text)
        log.logger.debug("Response from Zabbix API: %s", result)
        if "error" in result:
            log.logger.error("Error in Zabbix API response: %s", result["error"])
            return []
        interface = result.get("result", [])
        for iface in interface:
            log.logger.info(
                "Found Zabbix interface ID: %s for hostid %s.",
                iface["interfaceid"],
                hostid,
            )
        return [int(iface["interfaceid"]) for iface in interface]
    except requests.exceptions.RequestException as e:
        log.logger.error(
            "Failed to find Zabbix interface IDs for hostid %s: %s", hostid, e
        )
    return []


def find_nb_site_id(site_name: str) -> int:
    """Finds the Netbox site ID based on the provided site name.
    Args:
        site_name (str): The name of the site to find.
    Returns:
        int: The ID of the site if found, otherwise -1.
    """
    log.logger.info("Finding Netbox site ID for %s", site_name)
    nb_ip = os.environ.get("NETBOX_IP")
    nb_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {nb_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.get(
        f"{nb_ip}/api/dcim/sites/?name={site_name}", headers=headers, timeout=30
    )
    if response.status_code == 200:
        data = json.loads(response.text)
        if data["count"] > 0:
            site_id = data["results"][0]["id"]
            log.logger.info("Found Netbox site ID: %s for %s.", site_id, site_name)
            return int(site_id)
    log.logger.error(
        "Failed to find Netbox site ID for %s: %s", site_name, response.text
    )
    return -1


def find_nb_device_type_id(device_type: str) -> int:
    """Finds the Netbox device type ID based on the provided device type.
    Args:
        device_type (str): The name of the device type to find.
    Returns:
        int: The ID of the device type if found, otherwise -1.
    """
    log.logger.info("Finding Netbox device type ID for %s.", device_type)
    nb_ip = os.environ.get("NETBOX_IP")
    nb_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {nb_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.get(
        f"{nb_ip}/api/dcim/device-types/?model={device_type}",
        headers=headers,
        timeout=30,
    )
    if response.status_code == 200:
        data = json.loads(response.text)
        if data["count"] > 0:
            device_type_id = data["results"][0]["id"]
            log.logger.info(
                "Found Netbox device type ID: %s for %s.", device_type_id, device_type
            )
            return int(device_type_id)
    log.logger.error(
        "Failed to find Netbox device type ID for %s: %s", device_type, response.text
    )
    return -1


def find_nb_device_role_id(device_role: str) -> int:
    """Finds the Netbox device role ID based on the provided device role.
    Args:
        device_role (str): The name of the device role to find.
    Returns:
        int: The ID of the device role if found, otherwise -1.
    """
    log.logger.info("Finding Netbox device role ID for %s.", device_role)
    nb_ip = os.environ.get("NETBOX_IP")
    nb_key = os.environ.get("NETBOX_KEY")
    headers = {
        "Authorization": f"Token {nb_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.get(
        f"{nb_ip}/api/dcim/device-roles/?name={device_role}",
        headers=headers,
        timeout=30,
    )
    if response.status_code == 200:
        data = json.loads(response.text)
        if data["count"] > 0:
            device_role_id = data["results"][0]["id"]
            log.logger.info(
                "Found Netbox device role ID: %s for %s.", device_role_id, device_role
            )
            return int(device_role_id)
    log.logger.error(
        "Failed to find Netbox device role ID for %s: %s", device_role, response.text
    )
    return -1


def format_address(address: str) -> str:
    """
    Extract the IP address from a CIDR notation string.
    If the address contains a forward slash (indicating CIDR notation),
    returns only the IP address portion. Otherwise, returns the address unchanged.
    Args:
      address (str): An IP address, optionally in CIDR notation (e.g., "192.168.1.0/24").
    Returns:
      str: The IP address without the CIDR prefix length.
    Examples:
      >>> format_address("192.168.1.0/24")
      "192.168.1.0"
      >>> format_address("10.0.0.1")
      "10.0.0.1"
    """
    if "/" in address:
        return address.split("/")[0]
    return address


def format_status(status: str) -> str:
    """
    Convert a device status string to a standardized format.
    Maps various device status values to either "Active" or "Disabled".
    If the status doesn't match any known mappings, returns the original status.
    Args:
      status (str): The device status to format. Can be values like "active", 0,
             "offline", "staged", "planned", "failed", "inventory",
             "decommissioning", or any other custom status.
    Returns:
      str: Standardized status string - either "Active", "Disabled", or the
         original status value if it doesn't match any known mappings.
    Examples:
      >>> formatStatus("active")
      "Active"
      >>> formatStatus(0)
      "Active"
      >>> formatStatus("offline")
      "Disabled"
      >>> formatStatus("custom_status")
      "custom_status"
    """
    enabled_statuses = {"active", 0}
    disabled_statuses = {
        "offline",
        "staged",
        "planned",
        "failed",
        "inventory",
        "decommissioning",
    }
    if status in enabled_statuses:
        return "Active"
    if status in disabled_statuses:
        return "Disabled"
    return status


def format_mac(mac: str) -> str:
    """
    Format a MAC address string into a standardized dot-separated notation.
    Removes all non-hexadecimal characters from the input MAC address and
    reformats it into groups of 4 characters separated by dots (e.g., 1234.5678.90ab).
    Args:
      mac (str): The MAC address string to format. Can contain various separators
             like colons, hyphens, or spaces (e.g., "12:34:56:78:90:ab").
    Returns:
      str: A formatted MAC address in the format "xxxx.xxxx.xxxx" (lowercase).
         Returns an empty string if the input is None or empty.
    Example:
      >>> format_mac("12:34:56:78:90:ab")
      "1234.5678.90ab"
      >>> format_mac("12-34-56-78-90-AB")
      "1234.5678.90ab"
      >>> format_mac("")
      ""
    """
    if not mac:
        return ""
    mac_clean = re.sub(r"[^0-9A-Fa-f]", "", mac)
    return f"{mac_clean[0:4]}.{mac_clean[4:8]}.{mac_clean[8:12]}".lower()


def print_differences(difference_models: list[difference_model]) -> str:
    """
    Generate a formatted string report of device differences and similarities.
    Iterates through a list of difference models and creates a formatted text
    report comparing Netbox and Zabbix devices, including their differences
    and similarities.
    Args:
      difference_model: A list of difference_model objects, each containing
        a Netbox device, a Zabbix device, and their differences/similarities.
    Returns:
      A formatted string containing the comparison report with device information,
      differences, and similarities for each device pair.
    """
    txt_builder: str = ""
    for differ in difference_models:
        txt_builder += f"Netbox device: {print_device(differ.nb_device)}\n"
        txt_builder += f"Zabbix device: {print_device(differ.zb_device)}\n"
        txt_builder += "Differences:\n"
        for difference in differ.differences[0]:
            txt_builder += f"  {difference}\n"
        txt_builder += "Similarities:\n"
        for similarity in differ.differences[1]:
            txt_builder += f"  {similarity}\n"
    return txt_builder


def print_devices(nb_device_list: list[device_model]) -> str:
    """
    Generate a formatted string representation of a list of network devices.
    Iterates through a list of device models and constructs a detailed text
    representation including device information, interfaces, and IP addresses.
    Args:
      nb_device_list (list[device_model]): A list of device model objects to be formatted.
    Returns:
      str: A formatted string containing device details including:
        - Device name, description, status, hostgroup, and templates
        - For each interface: name, MAC address, and port type
        - For each interface address: IP address and DNS name
    Example:
      >>> devices = [device1, device2]
      >>> output = print_devices(devices)
      >>> print(output)
      Device Name: router-01
      Description: Main router
      ...
    """
    txt_builder: str = ""
    for device in nb_device_list:
        txt_builder += f"Device Name: {device.name}\n"
        txt_builder += f"Description: {device.description}\n"
        txt_builder += f"Status: {device.status}\n"
        txt_builder += f"Hostgroup: {device.hostgroup}\n"
        txt_builder += f"Templates: {device.templates}\n"
        for interface in device.interfaces:
            txt_builder += f"  Interface Name: {interface.name}\n"
            txt_builder += f"  MAC Address: {interface.mac_address}\n"
            txt_builder += f"  Port Type: {uniform_port_type(interface.port_type)}\n"
            for address in interface.addresses:
                txt_builder += f"    IP Address: {address.address}\n"
                txt_builder += f"    DNS Name: {address.dns_name}\n"
    return txt_builder


def print_device(device: device_model) -> str:
    """
    Format device information into a human-readable string representation.
    Converts a device object and its nested interface and address information
    into a formatted text string suitable for display or logging.
    Args:
      device (device_model): The device object containing name, description,
        status, hostgroup, templates, and a list of interfaces with their
        addresses.
    Returns:
      str: A formatted string containing:
        - Device metadata (name, description, status, hostgroup, templates)
        - Interface details (name, MAC address, port type)
        - IP address information (address, DNS name) for each interface
    Example:
      >>> output = print_device(device)
      >>> print(output)
      Device Name: router-01
      Description: Core Router
      Status: active
      ...
    """
    txt_builder: str = ""
    txt_builder += f"Device Name: {device.name}\n"
    txt_builder += f"Description: {device.description}\n"
    txt_builder += f"Status: {device.status}\n"
    txt_builder += f"Hostgroup: {device.hostgroup}\n"
    txt_builder += f"Templates: {device.templates}\n"
    for interface in device.interfaces:
        txt_builder += f"  Interface Name: {interface.name}\n"
        txt_builder += f"  MAC Address: {interface.mac_address}\n"
        txt_builder += f"  Port Type: {uniform_port_type(interface.port_type)}\n"
        for address in interface.addresses:
            txt_builder += f"    IP Address: {address.address}\n"
            txt_builder += f"    DNS Name: {address.dns_name}\n"
    return txt_builder


def get_nb_devices(key: str, ip: str) -> list[device_model] | str:
    """
    Fetch devices from Netbox API and return a list of device models.
    This function queries the Netbox GraphQL API to retrieve device information
    including site, device type, role, configuration context, status, and network
    interfaces. It filters devices based on required Zabbix configuration context
    fields (templates and port_type).
    Args:
      key (str): Authentication token for Netbox API authorization.
      ip (str): Base URL/IP address of the Netbox API endpoint.
    Returns:
      list[device_model] | str: A list of device_model objects containing
        device information and interfaces if the request is successful.
        Returns an error message string if the request fails or returns
        a non-200 status code.
    Raises:
      Implicitly handles requests.exceptions.RequestException and returns
      an error message string instead of raising.
    Note:
      - Devices are only included if they have valid Zabbix configuration context
        with 'templates' and 'port_type' fields.
      - Only interfaces with associated IP addresses are included in the result.
      - Primary IPv4 address is extracted from CIDR notation (e.g., "192.168.1.1/24").
      - MAC addresses are formatted using the format_mac() utility function.
      - Device status is formatted using the format_status() utility function.
    """
    log.logger.info("Fetching Netbox devices from %s.", ip)
    headers: dict[str, str] = {
        "Authorization": f"Token {key}",
        "Accept": "application/json",
    }
    query = """
    {
    device_list {
        id
        name
        site {
            name
        }
        device_type {
            manufacturer {
                name
          }
        }
        role {
            name
        }
        config_context
        custom_fields
        status
        description
        primary_ip4 {
            address
            dns_name
        }
        interfaces {
            name
            mac_addresses {
                mac_address
            }
            ip_addresses {
                address
                dns_name
            }
        }
      }
    device_role_list {
      name
      custom_fields
    }
    }
    """
    try:
        response: requests.Response = requests.post(
            ip, headers=headers, json={"query": query}, timeout=30
        )

        log.logger.debug(
            "Request to Netbox API: %s %s  with headers %s and body %s",
            response.request.method,
            response.request.url,
            response.request.headers,
            response.request.body,
        )
        if response.status_code != 200:
            log.logger.error("Failed to fetch devices from Netbox: %s", response.text)
            return f"Failed to fetch devices from Netbox: {response.text}"

        data = json.loads(response.text)
        log.logger.debug(data)

        # Extract JSON structure with validation
        try:
            response_data = data["data"]
            device_role_list = response_data["device_role_list"]
            devices = response_data["device_list"]
        except KeyError as e:
            log.logger.error("Missing expected key in Netbox response: %s", e)
            return f"Invalid Netbox API response structure: {e}"

        device_role_map = get_device_role_map(device_role_list)
        device_role_port_type_map = get_device_role_port_type_map(device_role_list)
        device_list: list[device_model] = []

        for device in devices:
            try:
                config_context = (
                    device["config_context"]
                    if isinstance(device["config_context"], dict)
                    else {}
                )
                custom_fields = (
                    device["custom_fields"] if device["custom_fields"] else {}
                )
                role_name = device["role"]["name"] if device["role"] else None

                # Check if device has required Zabbix configuration
                has_zabbix_config = (
                    (
                        config_context
                        and "zabbix" in config_context
                        and "templates" in config_context["zabbix"]
                        and "port_type" in config_context["zabbix"]
                    )
                    or custom_fields["zabbix_templates"]
                    or (
                        role_name
                        and role_name in device_role_map
                        and device_role_map[role_name]
                    )
                    or (
                        role_name
                        and role_name in device_role_port_type_map
                        and device_role_port_type_map[role_name]
                    )
                )

                if not has_zabbix_config:
                    log.logger.warning(
                        "Device %s skipped due to missing Zabbix configuration context or custom fields.",
                        device["name"],
                    )
                    continue

                custom_templates = custom_fields["zabbix_templates"]
                device_templates = get_nb_templates(
                    device, custom_templates, device_role_map
                )
                interfaces = device["interfaces"]

                primary_ip_str = ""
                if device["primary_ip4"]:
                    primary_ip_str = device["primary_ip4"]["address"]

                primary_ip_interface = find_primary_ip_interface(
                    interfaces, primary_ip_str
                )
                port_types = get_port_types(
                    custom_fields, device, device_role_port_type_map
                )
                primary_ip, primary_dns = get_primary_ip_info(device)
                mac_address = get_mac_address(primary_ip_interface)

                device_list.append(
                    device_model(
                        name=device["name"],
                        hostgroup=custom_fields["zabbix_hostgroups"]
                        if custom_fields["zabbix_hostgroups"]
                        else "",
                        description=device["description"],
                        templates=(
                            sorted(device_templates)
                            if isinstance(device_templates, list)
                            else device_templates
                        ),
                        status=format_status(device["status"]),
                        interfaces=[
                            interface_model(
                                name=primary_ip_interface["name"]
                                if primary_ip_interface
                                else "",
                                mac_address=mac_address,
                                port_type=port_type,
                                addresses=[
                                    address_model(
                                        address=primary_ip,
                                        dns_name=primary_dns,
                                    )
                                ],
                            )
                            for port_type in sorted(port_types)
                            if port_types
                        ],
                    )
                )
            except (KeyError, TypeError) as e:
                log.logger.error("Error processing device: %s", e)
                continue

        return device_list
    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"


def get_port_types(
    custom_fields: dict[str, Any],
    device: dict[str, Any],
    device_role_port_type_map: dict[str, list[str]],
) -> list[str] | str:
    """
    Retrieve port types for a device from custom fields, device role, or config context.
    Args:
        custom_fields (dict): Device custom fields.
        device (dict): Device data containing role and config_context.
        device_role_port_type_map (dict): Mapping of device roles to port types.
    Returns:
        list[str] | str: List of port types or empty list.
    """
    if custom_fields["zabbix_port_type"] and len(custom_fields["zabbix_port_type"]) > 0:
        return custom_fields["zabbix_port_type"]

    role_name = device["role"]["name"] if device["role"] else None
    if (
        role_name
        and role_name in device_role_port_type_map
        and len(device_role_port_type_map[role_name]) > 0
    ):
        return device_role_port_type_map[role_name]

    config_context = (
        device["config_context"] if isinstance(device["config_context"], dict) else {}
    )
    return config_context["zabbix"]["port_type"] if "zabbix" in config_context else []


def get_mac_address(primary_ip_interface: dict[str, Any] | None) -> str:
    """
    Extract and format MAC address from interface.
    Args:
        primary_ip_interface (dict | None): Interface data containing MAC addresses.
    Returns:
        str: Formatted MAC address or empty string.
    """
    if not primary_ip_interface:
        return ""

    mac_addresses = (
        primary_ip_interface["mac_addresses"]
        if primary_ip_interface["mac_addresses"]
        else []
    )
    if mac_addresses and isinstance(mac_addresses, list) and len(mac_addresses) > 0:
        mac_addr = mac_addresses[0]["mac_address"]
        return format_mac(mac_addr) if mac_addr else ""

    return ""


def get_primary_ip_info(device: dict[str, Any]) -> tuple[str, str]:
    """
    Extract primary IP address and DNS name from device.
    Args:
        device (dict): Device data containing primary_ip4.
    Returns:
        tuple: (ip_address, dns_name)
    """
    primary_ip4 = device["primary_ip4"]
    if not primary_ip4:
        return "", ""

    address = primary_ip4["address"] if primary_ip4["address"] else ""
    dns_name = primary_ip4["dns_name"] if primary_ip4["dns_name"] else ""

    # Extract IP from CIDR notation
    ip_address = address.split("/")[0] if address else ""

    return ip_address, dns_name


def get_nb_templates(
    device: Any,
    custom_templates: list[str] | None,
    device_role_map: dict[str, list[str]],
) -> list[str] | str:
    """
    Retrieve Zabbix templates for a given NetBox device based on custom fields, device role, or config context.
    Args:
        device (Any): The NetBox device object containing configuration context and custom fields.
        custom_templates (list[str] | None): A list of templates specified in the device's custom fields, if available.
        device_role_map (dict[str, list[str]]): A map of device roles to their corresponding Zabbix templates.
    Returns:
        list[str] | str: A list of Zabbix templates associated with the device, or an error message string if templates cannot be determined.
    """
    device_templates: list[str] = []
    try:
        if isinstance(custom_templates, list) and len(custom_templates) > 0:
            device_templates = [str(template) for template in custom_templates]
            log.logger.info(
                "Device %s has Zabbix templates from custom fields: %s",
                device["name"],
                device_templates,
            )
        elif (
            device["role"]
            and device["role"]["name"] in device_role_map
            and len(device_role_map[device["role"]["name"]]) > 0
        ):
            device_templates = [
                str(template) for template in device_role_map[device["role"]["name"]]
            ]
            log.logger.info(
                "Device %s has Zabbix templates from device role %s: %s",
                device["name"],
                device["role"]["name"],
                device_templates,
            )
        else:
            config_context = (
                device["config_context"]
                if isinstance(device["config_context"], dict)
                else {}
            )
            config_templates = (
                config_context["zabbix"]["templates"]
                if "zabbix" in config_context
                else []
            )
            device_templates = (
                [str(template) for template in config_templates]
                if isinstance(config_templates, list)
                else []
            )
            log.logger.info(
                "Device %s has Zabbix templates from config context: %s",
                device["name"],
                device_templates,
            )
    except KeyError as e:
        log.logger.error("Missing expected key in NetBox device data: %s", e)
        return f"Missing expected key in NetBox device data: {e}"
    return device_templates


def get_device_role_map(device_role_list: list[dict[str, Any]]) -> dict[str, list[str]]:
    """
    Create a mapping of device roles to their associated Zabbix templates based on NetBox device role data.
    Args:
        device_role_list (list[dict[str, Any]]): A list of device role dictionaries from NetBox, each containing a name and custom fields.
    Returns:
        dict[str, list[str]]: A mapping where the key is the device role name and the value is a list of Zabbix templates associated with that role.
    """
    device_role_map: dict[str, list[str]] = {}
    for device_role in device_role_list:
        try:
            role_name = device_role["name"]
            custom_fields = (
                device_role["custom_fields"] if device_role["custom_fields"] else {}
            )
            zabbix_templates = (
                custom_fields["zabbix_templates"]
                if custom_fields["zabbix_templates"]
                else []
            )
            if role_name and isinstance(zabbix_templates, list):
                device_role_map[role_name] = [
                    str(template) for template in zabbix_templates
                ]
                log.logger.info(
                    "Device role %s has Zabbix templates: %s",
                    role_name,
                    device_role_map[role_name],
                )
            else:
                log.logger.info(
                    "Device role %s does not have Zabbix templates defined.", role_name
                )
        except KeyError as e:
            log.logger.warning("Missing key in device role data: %s", e)
            continue
    return device_role_map


def get_device_role_port_type_map(
    device_role_list: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """
    Create a mapping of device roles to their associated Zabbix port types based on NetBox device role data.
    Args:
        device_role_list (list[dict[str, Any]]): A list of device role dictionaries from NetBox, each containing a name and custom fields.
    Returns:
        dict[str, list[str]]: A mapping where the key is the device role name and the value is a list of Zabbix port types associated with that role.
    """
    device_role_port_type_map: dict[str, list[str]] = {}
    for device_role in device_role_list:
        try:
            role_name = device_role["name"]
            custom_fields = (
                device_role["custom_fields"] if device_role["custom_fields"] else {}
            )
            zabbix_port_types = (
                custom_fields["zabbix_port_type"]
                if custom_fields["zabbix_port_type"]
                else []
            )
            if role_name and isinstance(zabbix_port_types, list):
                device_role_port_type_map[role_name] = [
                    str(port_type) for port_type in zabbix_port_types
                ]
                log.logger.info(
                    "Device role %s has Zabbix port types: %s",
                    role_name,
                    device_role_port_type_map[role_name],
                )
            else:
                log.logger.info(
                    "Device role %s does not have Zabbix port types defined.", role_name
                )
        except KeyError as e:
            log.logger.warning("Missing key in device role data: %s", e)
            continue
    return device_role_port_type_map


def find_primary_ip_interface(
    interfaces: list[dict[str, Any]], primary_ip: str
) -> dict[str, Any] | None:
    """
    Find the interface that has the primary IP address assigned.
    Args:
      interfaces (list[dict]): A list of interface dictionaries, each containing
        interface details including IP addresses.
      primary_ip (str): The primary IP address to match against the interfaces.
    Returns:
      dict: The interface dictionary that contains the primary IP address, or None if not found.
    """
    primary_interface: dict[str, Any] | None = None
    for interface in interfaces:
        for ip in interface["ip_addresses"]:
            if ip["address"] == primary_ip:
                primary_interface = {
                    "name": interface["name"],
                    "mac_addresses": interface["mac_addresses"]
                    if interface["mac_addresses"]
                    else [],
                    "address": ip["address"],
                    "dns_name": ip["dns_name"],
                }
                break
    return primary_interface


def get_zb_devices(key: str, ip: str) -> list[device_model] | str:
    """
    Retrieve devices from a Zabbix instance via its API.
    Makes a JSON-RPC call to the Zabbix API to fetch all enabled hosts
    along with their interfaces, host groups, and parent templates.
    Args:
      key (str): API authentication token for Zabbix authorization.
      ip (str): Base URL or IP address of the Zabbix instance.
    Returns:
      list[device_model] | str: A list of device_model objects containing
        host information (name, hostgroups, description, templates, status, interfaces),
        or an error message string if the request fails or the API returns an error.
    Raises:
      Logs KeyError if expected keys are missing in host data and continues processing.
      Logs RequestException if the HTTP request fails.
    Note:
      - The function filters for hosts with status 0 (enabled).
      - Missing expected keys in individual hosts are logged and skipped.
      - Interfaces are mapped to address_model objects with their IP and DNS information.
      - Templates are extracted from parentTemplates and mapped to their names.
    """
    ip = f"{ip}/api_jsonrpc.php"
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host", "name", "status", "description"],
            "selectInterfaces": ["interfaceid", "dns", "ip", "type"],
            "selectHostGroups": ["groupid", "name"],
            "selectParentTemplates": ["templateid", "name"],
            "filter": {"status": [0]},
        },
        "id": 1,
    }
    headers: dict[str, str] = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json-rpc",
        "Accept": "application/json",
    }
    try:
        zb_device_list: list[device_model] = []
        log.logger.debug(
            "Requesting Zabbix: %s devices with payload: %s and headers: %s",
            ip,
            payload,
            headers,
        )
        response: requests.Response = requests.post(
            ip, headers=headers, json=payload, timeout=30
        )
        log.logger.debug(response)
        response.raise_for_status()
        result = json.loads(response.text)
        if "error" in result:
            log.logger.error("Error in Zabbix API response: %s", result["error"])
            return f"Error in Zabbix API response: {result['error']}"
        log.logger.debug(result)
        for host in result["result"]:
            try:
                # Sort interfaces by port_type for consistent ordering
                sorted_interfaces = sorted(host["interfaces"], key=lambda x: x["type"])
                zb_device_list.append(
                    device_model(
                        name=host["host"],
                        hostgroup=host["hostgroups"],
                        description=host["description"],
                        templates=sorted(
                            [template["name"] for template in host["parentTemplates"]]
                        ),
                        status=format_status(host["status"]),
                        interfaces=[
                            interface_model(
                                name=interface["dns"],
                                mac_address="",
                                port_type=interface["type"],
                                addresses=[
                                    address_model(
                                        address=interface["ip"],
                                        dns_name=interface["dns"],
                                    )
                                ],
                            )
                            for interface in sorted_interfaces
                        ],
                    )
                )
            except KeyError as e:
                log.logger.error("Missing expected key in Zabbix host data: %s", e)
                continue
    except requests.exceptions.RequestException as e:
        log.logger.error("Request failed: %s", e)
        return f"Request failed: {e}"
    return zb_device_list


def uniform_port_type(port_type: str, numbered: bool = False) -> str:
    """Uniforms the port type to a human readable format."""
    if isinstance(port_type, list):
        port_type = port_type[0] if port_type else ""
    if numbered:
        port_type_map: dict[str, str] = {
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
            "Agent": "1",
            "SNMP": "2",
            "IPMI": "3",
            "JMX": "4",
        }
    else:
        port_type_map: dict[str, str] = {
            "1": "Agent",
            "2": "SNMP",
            "3": "IPMI",
            "4": "JMX",
            "Agent": "Agent",
            "SNMP": "SNMP",
            "IPMI": "IPMI",
            "JMX": "JMX",
        }
    return port_type_map.get(port_type, port_type)


def map_port_type_device(
    nb_devices: list[device_model],
    zb_devices: list[device_model],
    numbered: bool = False,
) -> None:
    """Map interface port types in NetBox/Zabbix lists to a uniform format."""
    for device in nb_devices:
        for interface in device.interfaces:
            interface.port_type = uniform_port_type(interface.port_type, numbered)
    for device in zb_devices:
        for interface in device.interfaces:
            interface.port_type = uniform_port_type(interface.port_type, numbered)


# pylint: disable=too-many-nested-blocks
def uniform_output_text(
    differences: list[difference_model],
    netbox_devices: list[device_model],
    zabbix_devices: list[device_model],
) -> tuple[list[difference_model], list[device_model], list[device_model]]:
    """Return display-ready copies of differences, NetBox devices, and Zabbix devices."""
    try:
        display_differences: list[difference_model] = copy.deepcopy(differences)
        display_netbox_devices: list[device_model] = copy.deepcopy(netbox_devices)
        display_zabbix_devices: list[device_model] = copy.deepcopy(zabbix_devices)
        dif_nb_devices: list[device_model] = [
            difference.nb_device for difference in display_differences
        ]
        dif_zb_devices: list[device_model] = [
            difference.zb_device for difference in display_differences
        ]
        for device_list in [
            dif_nb_devices,
            dif_zb_devices,
            display_netbox_devices,
            display_zabbix_devices,
        ]:
            for device in device_list:
                display_device: Any = device
                if isinstance(display_device.hostgroup, list):
                    hostgroup_names: list[str] = []
                    for group in display_device.hostgroup:
                        if isinstance(group, dict) and "name" in group:
                            hostgroup_names.append(str(group["name"]))
                        elif isinstance(group, str):
                            hostgroup_names.append(group)
                        elif group:
                            hostgroup_names.append(str(group))
                    display_device.hostgroup = ", ".join(hostgroup_names)
                else:
                    display_device.hostgroup = (
                        display_device.hostgroup if display_device.hostgroup else ""
                    )
                if isinstance(display_device.templates, list):
                    display_device.templates = (
                        ", ".join(
                            str(template)
                            for template in sorted(display_device.templates)
                        )
                        if display_device.templates
                        else []
                    )
        return display_differences, display_netbox_devices, display_zabbix_devices
    except (TypeError, AttributeError, KeyError) as e:
        log.logger.error("Error uniforming output text: %s", e)
        return differences, netbox_devices, zabbix_devices


def parse_webhook_create(data: dict) -> device_model:
    device_data = data["data"]
    custom_fields = device_data.get("custom_fields", {})
    return device_model(
        name=device_data["name"],
        interfaces=[],
        hostgroup=custom_fields.get("zabbix_hostgroups", []),
        description=device_data.get("description", ""),
        templates=None,
        status=device_data.get("status", {}).get("value", "Inactive"),
    )


def parse_webhook_update(data: dict) -> device_model:
    """Build the Device that should be synced into Zabbix from a NetBox webhook."""
    device_data = data["data"]
    postchange = data["snapshots"].get("postchange") or {}

    custom_fields = postchange.get("custom_fields") or device_data.get("custom_fields", {})
    # zabbix_port_type is a NetBox multi-select custom field, e.g. ["1"]
    zabbix_port_type_list = custom_fields.get("zabbix_port_type") or []
    zabbix_port_type = zabbix_port_type_list[0] if zabbix_port_type_list else "1"

    primary_interface = get_primary_interface(device_data, zabbix_port_type)
    interfaces = [primary_interface] if primary_interface else []
    role_data = device_data.get("role")
    role = role_data.get("name") if role_data else ""

    if custom_fields.get("zabbix_templates"):
        templates: list[str] = custom_fields.get("zabbix_templates")
    else:
    	try:
        	templates: list[str] = query_netbox_role_templates(role)
    	except requests.exceptions.HTTPError:
    		templates: list[str] = []
    if not templates:
        templates = device_data.get("config_context", {}).get("zabbix", []).get("templates", [])
    return device_model(
        name=postchange.get("name", device_data.get("name", "")),
        interfaces=interfaces,
        hostgroup=custom_fields.get("zabbix_hostgroups", []),
        description=postchange.get("description", ""),
        templates=templates,
        status=postchange.get("status", "Inactive"),
    )

def query_netbox_role_templates(role: str) -> list[str]:
    netbox_ip: str | None = os.environ.get("NETBOX_IP")
    netbox_key: str | None = os.environ.get("NETBOX_KEY")
    headers = {"Authorization": f"Token {netbox_key}"} if netbox_key else {}
    query = """
    {
        device_role_list {
            name
            custom_fields
        }
    }
    """
    response: requests.Response = requests.post(netbox_ip, headers=headers, json={"query": query}, timeout=30)
    response.raise_for_status()
    data_json = response.json()
    role_data = data_json.get("data", {}).get("device_role_list", [])

    role_dict = {r.get("name"): r for r in role_data}

    role_entry = role_dict.get(role, {})
    custom_fields = role_entry.get("custom_fields") or {}
    templates_roles = custom_fields.get("zabbix_templates") or []
    return templates_roles

def get_primary_interface(device_data: dict, zabbix_port_type: str) -> interface_model | None:
    """
    Resolve the interface holding the device's primary IPv4 address.
    port_type comes from the device's zabbix_port_type custom field
    (1=Agent, 2=SNMP, 3=IPMI, 4=JMX) — NOT the physical NetBox interface type.
    """
    netbox_ip = os.environ.get("NETBOX_IP")
    netbox_key = os.environ.get("NETBOX_KEY")
    headers = {"Authorization": f"Token {netbox_key}"} if netbox_key else {}
    primary_ip4 = device_data.get("primary_ip4")
    if not primary_ip4 or primary_ip4 == "None":
        return None

    ip_id = primary_ip4["id"]
    resp = requests.get(
        f"{netbox_ip}/api/ipam/ip-addresses/{ip_id}/",
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    ip_obj = resp.json()

    assigned = ip_obj.get("assigned_object")
    if not assigned or ip_obj.get("assigned_object_type") != "dcim.interface":
        return None

    interface_id = assigned["id"]
    iface_resp = requests.get(
        f"{netbox_ip}/api/dcim/interfaces/{interface_id}/",
        headers=headers,
        timeout=10,
    )
    iface_resp.raise_for_status()
    iface = iface_resp.json()

    mac = iface.get("mac_address") or ""
    if not mac and iface.get("primary_mac_address"):
        mac = iface["primary_mac_address"].get("mac_address", "")

    return interface_model(
        name=iface["name"],
        addresses=[
            address_model(address=primary_ip4["address"], dns_name=primary_ip4.get("dns_name", "")),
        ],
        mac_address=mac,
        port_type=zabbix_port_type,  # e.g. "1" — matches Zabbix's own numeric type codes
    )


def parse_webhook_delete(data: dict) -> device_model:
    device_data = data["data"]
    custom_fields = device_data.get("custom_fields", {})
    return device_model(
        name=device_data["name"],
        interfaces=[],
        hostgroup=custom_fields.get("zabbix_hostgroups", []),
        description=device_data.get("description", ""),
        templates=None,
        status=device_data.get("status", {}).get("value", "Inactive"),
    )


def get_zabbix_device(name: str) -> device_model | None:
    """
    Fetches a single device from Zabbix by exact host name.
    Args:
        name (str): The Zabbix host name to look up.
    Returns:
        device_model | None: The matching device, or None if not found
            or if Zabbix credentials are missing.
    """
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    REQUEST_TIMEOUT: int = 30
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return None

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
            "method": "host.get",
            "params": {
                "filter": {"host": [name]},
                "output": ["hostid", "host", "description", "status"],
                "selectInterfaces": [
                    "interfaceid",
                    "ip",
                    "dns",
                    "port",
                    "type",
                    "main",
                ],
                "selectGroups": ["name"],
                "selectParentTemplates": ["name"],
            },
            "id": 1,
        },
    )

    if response.status_code != 200:
        log.logger.error(
            "Zabbix API request failed for %s: HTTP %s", name, response.status_code
        )
        return None

    data = response.json()
    if "error" in data:
        log.logger.error("Error in Zabbix API response for %s: %s", name, data["error"])
        return None

    results = data.get("result", [])
    if not results:
        log.logger.info("No Zabbix host found for %s.", name)
        return None

    host = results[0]

    interfaces: list[interface_model] = []
    for iface in host.get("interfaces", []):
        addresses: list[address_model] = []
        if iface.get("ip"):
            addresses.append(
                address_model(address=iface["ip"], dns_name=iface.get("dns", ""))
            )
        interfaces.append(
            interface_model(
                name=f"if{iface.get('interfaceid', '')}",
                addresses=addresses,
                mac_address="",  # Zabbix host interfaces don't carry MAC addresses
                port_type=str(iface.get("type", "")),
            )
        )

    hostgroup: list[str] = [g["name"] for g in host.get("groups", []) if "name" in g]
    templates: list[str] = [
        t["name"] for t in host.get("parentTemplates", []) if "name" in t
    ]

    return device_model(
        name=host.get("host", name),
        interfaces=interfaces,
        hostgroup=hostgroup,
        description=host.get("description", ""),
        templates=templates,
        status=host.get("status", "Inactive"),
    )


def delete_zabbix_device(device: device_model) -> tuple[str, int]:
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return "None", 400
    headers: dict[str, str] = {
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {zabbix_key}",
    }
    REQUEST_TIMEOUT: int = 30
    log.logger.info("Deleting Zabbix device for %s", device.name)
    zabbix_host = get_zabbix_hostid(device.name)
    if zabbix_host:
        log.logger.info("Deleting Zabbix host for %s", device.name)
        response: requests.Response = requests.post(
            zabbix_ip + "/api_jsonrpc.php",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            json={
                "jsonrpc": "2.0",
                "method": "host.delete",
                "params": [zabbix_host],
                "id": 1,
            },
        )
        if response.status_code == 200:
            log.logger.info("Zabbix host deleted successfully")
            return "OK", 200
        else:
            log.logger.error("Failed to delete Zabbix host: %s", response.text)
            return "Error", response.status_code
    else:
        log.logger.info("No Zabbix host found for %s", device.name)
        return "OK", 200


def get_zabbix_hostid(name: str) -> str | None:
    zabbix_ip: str | None = os.environ.get("ZABBIX_IP")
    zabbix_key: str | None = os.environ.get("ZABBIX_KEY")
    REQUEST_TIMEOUT: int = 30
    if zabbix_ip is None or zabbix_key is None:
        log.logger.error("Zabbix IP or API key not set in environment variables.")
        return None

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
            "method": "host.get",
            "params": {
                "filter": {"host": [name]},
                "output": ["hostid", "host", "description", "status"],
                "selectInterfaces": [
                    "interfaceid",
                    "ip",
                    "dns",
                    "port",
                    "type",
                    "main",
                ],
                "selectGroups": ["name"],
                "selectParentTemplates": ["name"],
            },
            "id": 1,
        },
    )

    if response.status_code != 200:
        log.logger.error(
            "Zabbix API request failed for %s: HTTP %s", name, response.status_code
        )
        return None

    data = response.json()
    if "error" in data:
        log.logger.error("Error in Zabbix API response for %s: %s", name, data["error"])
        return None

    results = data.get("result", [])
    if not results:
        log.logger.info("No Zabbix host found for %s.", name)
        return None

    host = results[0]
    return host.get("hostid")
