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

import re
import os
import requests
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.address_model import Address as address_model
from app.device.models.difference_model import DeviceDifference as difference_model
from app.logger import logger_conf as log


def find_hostinterface_id(hostid: str) -> int:
    """
    Finds the interface ID for a given Zabbix host ID and interface name.
    Args:
      hostid (str): The Zabbix host ID.
      interface_name (str): The name (DNS or IP) of the interface to find.
    Returns:
      int: The interface ID if found, otherwise -1.
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
        response = requests.post(
            f"{zb_url}/api_jsonrpc.php", headers=headers, json=payload, timeout=10
        )
        response.raise_for_status()
        log.logger.debug("Response from Zabbix API: %s", response.json())
        result = response.json()
        if "error" in result:
            log.logger.error("Error in Zabbix API response: %s", result["error"])
            return -1
        interface = result.get("result", [])
        return int(interface[0]["interfaceid"]) if interface else -1
    except requests.exceptions.RequestException as e:
        log.logger.error("Failed to find Zabbix interface ID for hostid %s: %s", hostid, e)
    return -1


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
        f"{nb_ip}/api/dcim/sites/?name={site_name}", headers=headers, timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        if data["count"] > 0:
            site_id = data["results"][0]["id"]
            log.logger.info("Found Netbox site ID: %s for %s.", site_id, site_name)
            return int(site_id)
    log.logger.error("Failed to find Netbox site ID for %s: %s", site_name, response.text)
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
        f"{nb_ip}/api/dcim/device-types/?model={device_type}", headers=headers, timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        if data["count"] > 0:
            device_type_id = data["results"][0]["id"]
            log.logger.info("Found Netbox device type ID: %s for %s.", device_type_id, device_type)
            return int(device_type_id)
    log.logger.error("Failed to find Netbox device type ID for %s: %s", device_type, response.text)
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
        f"{nb_ip}/api/dcim/device-roles/?name={device_role}", headers=headers, timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        if data["count"] > 0:
            device_role_id = data["results"][0]["id"]
            log.logger.info("Found Netbox device role ID: %s for %s.", device_role_id, device_role)
            return int(device_role_id)
    log.logger.error("Failed to find Netbox device role ID for %s: %s", device_role, response.text)
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
    disabled_statuses = {"offline", "staged", "planned", "failed", "inventory", "decommissioning"}
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
    headers: dict[str, str] = {"Authorization": f"Token {key}", "Accept": "application/json"}
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
    }
    """
    try:
        response: requests.Response = requests.post(
            ip, headers=headers, json={"query": query}, timeout=10
        )
        log.logger.debug(
            "Request to Netbox API: %s %s  with headers %s and body %s",
            response.request.method,
            response.request.url,
            response.request.headers,
            response.request.body,
        )
        device_list: list[device_model] = []
        log.logger.debug(response)
        if response.status_code != 200:
            log.logger.error("Failed to fetch devices from Netbox: %s", response.text)
            return f"Failed to fetch devices from Netbox: {response.text}"
        if response.status_code == 200:
            data = response.json()
            for device in data["data"]["device_list"]:
                if (
                    device["config_context"]
                    and "zabbix" in device["config_context"]
                    and "templates" in device["config_context"]["zabbix"]
                    and "port_type" in device["config_context"]["zabbix"]
                ):
                    device_list.append(
                        device_model(
                            name=device["name"],
                            hostgroup=(
                                device["custom_fields"]["zabbix_hostgroups"]
                                if device["custom_fields"]
                                else ""
                                ),
                            description=device["description"],
                            templates=(
                                device["config_context"]["zabbix"]["templates"]
                                if device["config_context"]
                                else ""
                            ),
                            status=format_status(device["status"]),
                            interfaces=[
                                interface_model(
                                    name=interface["name"],
                                    mac_address=(
                                        format_mac(interface["mac_addresses"][0]["mac_address"])
                                        if interface["mac_addresses"]
                                        else ""
                                    ),
                                    port_type=(
                                        device["config_context"]["zabbix"]["port_type"]
                                        if device["config_context"]
                                        else ""
                                    ),
                                    addresses=[
                                        address_model(
                                            address=(
                                                str(device["primary_ip4"]["address"]).split(
                                                    "/", maxsplit=1
                                                )[0]
                                                if device["primary_ip4"]
                                                else ""
                                            ),
                                            dns_name=(
                                                device["primary_ip4"]["dns_name"]
                                                if device["primary_ip4"]
                                                else ""
                                            ),
                                        )
                                    ],
                                )
                                for interface in device["interfaces"]
                                if interface["ip_addresses"]
                            ],
                        )
                    )
        return device_list
    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"


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
            "Requesting Zabbix: %s devices with payload: %s and headers: %s", ip, payload, headers
        )
        response: requests.Response = requests.post(ip, headers=headers, json=payload, timeout=10)
        log.logger.debug(response)
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            log.logger.error("Error in Zabbix API response: %s", result["error"])
            return f"Error in Zabbix API response: {result['error']}"
        log.logger.debug(result)
        for host in result["result"]:
            try:
                zb_device_list.append(
                    device_model(
                        name=host["name"],
                        hostgroup=host["hostgroups"],
                        description=host["description"],
                        templates=[template["name"] for template in host["parentTemplates"]],
                        status=format_status(host["status"]),
                        interfaces=[
                            interface_model(
                                name=interface["dns"],
                                mac_address="",
                                port_type=interface["type"],
                                addresses=[
                                    address_model(
                                        address=interface["ip"], dns_name=interface["dns"]
                                    )
                                ],
                            )
                            for interface in host["interfaces"]
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


def format_port_type(port_type: str) -> str:
    """Maps the port type to a Netbox compatible format."""
    if isinstance(port_type, list):
        port_type = port_type[0] if port_type else ""
    port_type_map: dict[str, str] = {
        "Agent": "1",
        "SNMP": "2",
        "IPMI": "3",
        "JMX": "4",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
    }
    return port_type_map.get(port_type, "1")


def uniform_port_type(port_type: str) -> str:
    """Uniforms the port type to a human readable format."""
    if isinstance(port_type, list):
        port_type = port_type[0] if port_type else ""
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


def map_port_type_device(nb_devices: list[device_model], zb_devices: list[device_model]) -> None:
    """Map interface port types in NetBox/Zabbix lists to a uniform format."""
    for device in nb_devices:
        for interface in device.interfaces:
            interface.port_type = uniform_port_type(interface.port_type)
    for device in zb_devices:
        for interface in device.interfaces:
            interface.port_type = uniform_port_type(interface.port_type)


def uniform_output_text(
    differences: list[difference_model],
    netbox_devices: list[device_model],
    zabbix_devices: list[device_model],
) -> None:
    """Uniforms the output text for differences, netbox devices and zabbix devices."""
    try:
        dif_nb_devices: list[device_model] = [difference.nb_device for difference in differences]
        dif_zb_devices: list[device_model] = [difference.zb_device for difference in differences]
        for device_list in [dif_nb_devices, dif_zb_devices, netbox_devices, zabbix_devices]:
            for device in device_list:
                if isinstance(device.hostgroup, list):
                    device.hostgroup = (
                        ", ".join(group["name"] for group in device.hostgroup)
                        if device.hostgroup
                        else ""
                    )
                else:
                    device.hostgroup = device.hostgroup if device.hostgroup else ""
                if isinstance(device.templates, list):
                    device.templates = (
                        ", ".join(str(template) for template in device.templates)
                        if device.templates
                        else ""
                    )
    except (TypeError, AttributeError, KeyError) as e:
        log.logger.error("Error uniforming output text: %s", e)
