"""Validator service for Zabbix device updates.

This module provides validation functions to ensure device updates are compatible
with existing Zabbix host configurations, especially for port type changes.
"""
import os

import requests

from app.logger import logger_conf as log
from app.enums.item_types import ItemTypes

# Port type name mappings
INTERFACE_TYPE_NAMES = {
    "1": "Agent",
    "2": "SNMP",
    "3": "IPMI",
    "4": "JMX",
}


def get_port_type_names(interface_types: set[str]) -> list[str]:
    """Convert interface type numbers to human-readable names.

    Args:
        interface_types (set[str]): Set of interface type IDs (e.g., {"1", "2"}).

    Returns:
        list[str]: List of port type names (e.g., ["Agent", "SNMP"]).
    """
    return sorted([INTERFACE_TYPE_NAMES.get(iface_type, iface_type) for iface_type in interface_types])

class DeviceModelValidator:
    """
    Validator class representing a Zabbix host with its configuration.
    Used to validate if device updates are compatible with existing Zabbix host configuration.

    Attributes:
        hostid (str): The unique identifier of the Zabbix host.
        groupids (list[str]): List of host group IDs associated with the host.
        templateids (list[str]): List of template IDs linked to the host.
        interfaces (list[dict]): List of interfaces configured for the host.
        items (list[dict]): List of items (metrics) monitored on the host.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        hostid: str,
        groupids: list[str],
        templateids: list[str],
        interfaces: list[dict] | None = None,
        items: list[dict] | None = None,
    ) -> None:
        """Initialize a DeviceModelValidator instance.

        Args:
            hostid (str): The Zabbix host ID.
            groupids (list[str]): List of group IDs.
            templateids (list[str]): List of template IDs.
            interfaces (list[dict], optional): List of interface configurations. Defaults to None.
            items (list[dict], optional): List of items. Defaults to None.
        """
        self.hostid: str = hostid
        self.groupids: list[str] = groupids if groupids else []
        self.templateids: list[str] = templateids if templateids else []
        self.interfaces: list[dict] = interfaces if interfaces else []
        self.items: list[dict] = items if items else []

    def get_interface_types(self) -> set[str]:
        """Get all interface types configured on the host.

        Returns:
            set[str]: Set of interface types (e.g., "1" for Agent, "2" for SNMP).
        """
        return {interface.get("type", "") for interface in self.interfaces}

    def get_item_types(self) -> set[int]:
        """Get all item types used by items on the host.

        Returns:
            set[int]: Set of item type IDs.
        """
        return {int(item.get("type", 0)) for item in self.items}

def query_zabbix_for_host(device_name: str) -> dict | None:
    """Query Zabbix for a host matching the given device name.

    Args:
        device_name (str): The name of the device to search for in Zabbix.

    Returns:
        dict | None: The host data from Zabbix or None if not found.
    """
    zabbix_api_token: str | None = os.environ.get("ZABBIX_KEY")
    zabbix_api_url: str | None = os.environ.get("ZABBIX_IP")
    if not zabbix_api_token or not zabbix_api_url:
        log.logger.debug(
            "Zabbix API credentials not configured (ZABBIX_KEY=%s, ZABBIX_IP=%s)",
            "set" if zabbix_api_token else "not set",
            "set" if zabbix_api_url else "not set",
        )
        return None

    log.logger.debug("Querying Zabbix for host: %s", device_name)

    headers = {
        'Content-Type': 'application/json-rpc',
        'Authorization': f'Bearer {zabbix_api_token}'
    }
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": "extend",
            "filter": {
                "host": [device_name]
            },
            "selectInterfaces": "extend",
            "selectGroups": "extend",
            "selectParentTemplates": "extend",
            "selectItems": "extend"
        },
        "id": 1,
    }
    try:
        log.logger.debug(
            "Posting to Zabbix API at %s/api_jsonrpc.php",
            zabbix_api_url,
        )
        response = requests.post(
            f"{zabbix_api_url}/api_jsonrpc.php",
            headers=headers,
            json=payload,
            timeout=5.0
        )
        response.raise_for_status()
        response_json = response.json()

        if "error" in response_json:
            log.logger.error(
                "Zabbix API error for host %s: %s",
                device_name,
                response_json["error"],
            )
            return None

        result = response_json.get("result", [])
        if result:
            host_data = result[0]
            log.logger.info(
                "Found Zabbix host '%s' (hostid=%s) with %d interfaces and %d items",
                device_name,
                host_data.get("hostid"),
                len(host_data.get("interfaces", [])),
                len(host_data.get("items", [])),
            )
            return host_data

        log.logger.debug("No Zabbix host found for: %s", device_name)
        return None

    except requests.RequestException as e:
        log.logger.error(
            "HTTP error querying Zabbix for host %s: %s",
            device_name,
            e,
        )
        return None

def check_new_port_type_compatibility(
    zabbix_host_result: dict,
    new_port_types: list[str],
) -> bool:
    """Check if new port types can satisfy the host's existing items.

    The validation is based on the current items in Zabbix. If an existing
    item requires a specific interface type, that interface must be present in
    the new port types list.

    Args:
        zabbix_host_result (dict): The Zabbix host with current config.
        new_port_types (list[str]): List of new port types to validate.

    Returns:
        bool: True if the new port types satisfy all required item interfaces,
              False otherwise.
    """
    if not zabbix_host_result:
        return True

    # Port type to interface type mapping
    port_type_mapping: dict[str, str] = {
        "Agent": "1",
        "SNMP": "2",
        "IPMI": "3",
        "JMX": "4",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
    }

    # Map all new port types to interface types
    mapped_port_types: set[str] = set()
    for port_type in new_port_types:
        mapped_port_type = port_type_mapping.get(str(port_type))
        if not mapped_port_type:
            log.logger.error(
                "Invalid port type '%s' (no mapping found)",
                port_type,
            )
            return False  # Invalid port type
        mapped_port_types.add(mapped_port_type)

    log.logger.debug(
        "Validating %d new port types: %s (mapped to interfaces: %s)",
        len(new_port_types),
        new_port_types,
        mapped_port_types,
    )

    # Item type to required interface mapping
    item_type_to_interface_mapping = {
        ItemTypes.ZABBIX_AGENT.value: "1",
        ItemTypes.ZABBIX_AGENT_ACTIVE.value: "1",
        ItemTypes.SNMP_AGENT.value: "2",
        ItemTypes.SNMP_TRAP.value: "2",
        ItemTypes.IPMI_AGENT.value: "3",
        ItemTypes.JMX_AGENT.value: "4",
        ItemTypes.SSH_AGENT.value: "1",
        ItemTypes.TELNET_AGENT.value: "1",
        ItemTypes.HTTP_AGENT.value: "1",
        ItemTypes.ZABBIX_TRAPPER.value: None,
        ItemTypes.SIMPLE_CHECK.value: None,
        ItemTypes.ZABBIX_INTERNAL.value: None,
        ItemTypes.WEB_ITEM.value: None,
        ItemTypes.EXTERNAL_CHECK.value: None,
        ItemTypes.DATABASE_MONITOR.value: None,
        ItemTypes.CALCULATED.value: None,
        ItemTypes.DEPENDENT_ITEM.value: None,
        ItemTypes.SCRIPT.value: None,
        ItemTypes.BROWSER.value: None,
    }

    # Check existing items against the requested port types
    items = zabbix_host_result.get("items", [])
    log.logger.debug(
        "Checking %d items against new port types: %s",
        len(items),
        new_port_types,
    )
    for item in items:
        item_type = int(item.get("type", 0))
        required_interface_type = item_type_to_interface_mapping.get(item_type)

        if required_interface_type is not None and required_interface_type not in mapped_port_types:
            log.logger.warning(
                "Item '%s' (type=%s) requires interface %s, but new port types %s only provide %s",
                item.get("name", "unknown"),
                item_type,
                required_interface_type,
                new_port_types,
                mapped_port_types,
            )
            return False

    log.logger.debug(
        "Port type compatibility check passed for %d new port types (interfaces: %s)",
        len(new_port_types),
        mapped_port_types,
    )
    return True  # Safe to change port types

def find_zabbix_host(data: dict) -> tuple[DeviceModelValidator | None, dict | None]:
    """Find the corresponding Zabbix host based on the provided data.

    Args:
        data (dict): Dictionary containing device update information with
            custom fields for identifying the Zabbix host.

    Returns:
        tuple[DeviceModelValidator | None, dict | None]: Tuple containing the DeviceModelValidator instance if found and the Zabbix host result, or (None, None) otherwise.
    """
    device_name = data.get("data", {}).get("name")
    if not device_name:
        log.logger.warning("No device name found in update data")
        return None, None

    log.logger.debug("Looking up Zabbix host for device: %s", device_name)
    zabbix_host_result: dict | None = query_zabbix_for_host(device_name)
    if not zabbix_host_result:
        log.logger.warning(
            "Zabbix host not found for device: %s",
            device_name,
        )
        return None, None

    log.logger.debug(
        "Found Zabbix host %s with %d interfaces and %d items",
        device_name,
        len(zabbix_host_result.get("interfaces", [])),
        len(zabbix_host_result.get("items", [])),
    )

    # Extract necessary fields from Zabbix response
    hostid = zabbix_host_result.get("hostid", "")

    # Extract group IDs
    groups = zabbix_host_result.get("groups", [])
    groupids = [group.get("groupid") for group in groups if group.get("groupid")]

    # Extract template IDs
    parent_templates = zabbix_host_result.get("parentTemplates", [])
    templateids = [
        template.get("templateid")
        for template in parent_templates
        if template.get("templateid")
    ]

    # Get interfaces and items
    interfaces = zabbix_host_result.get("interfaces", [])
    items = zabbix_host_result.get("items", [])

    return DeviceModelValidator(hostid, groupids, templateids, interfaces, items), zabbix_host_result

def can_update_device(data: dict):  # pylint: disable=too-many-return-statements
    """Check if device update is allowed.

    Validates port type changes against existing Zabbix configuration.
    Updates with templates or hostgroups are always allowed.

    Args:
        data (dict): Input data containing device update information with
            custom fields for validation.

    Returns:
        dict: Validation result with 'valid' (bool) and 'message' (str).
    """
    device_name = data.get("data", {}).get("name", "unknown")

    # Extract custom fields from the update data
    custom_fields = data.get("data", {}).get("custom_fields", {})
    if not custom_fields:
        log.logger.info(
            "Device %s: No custom fields to validate",
            device_name,
        )
        return {"valid": True, "message": "No custom fields to validate"}

    # Check if port type is being changed (this must be validated first)
    new_port_types_raw = custom_fields.get("zabbix_port_type")
    new_port_types = []

    # Handle case where Netbox sends port_type as a list (e.g., ['2'] or ['1', '2'])
    if isinstance(new_port_types_raw, list):
        if len(new_port_types_raw) > 0:
            new_port_types = new_port_types_raw
            log.logger.debug(
                "Device %s: Port types extracted from list: %s",
                device_name,
                new_port_types,
            )
        else:
            # Empty list - no port type change
            new_port_types = []
    elif new_port_types_raw:
        # Single value (not in a list)
        new_port_types = [new_port_types_raw]
        log.logger.debug(
            "Device %s: Single port type value: %s",
            device_name,
            new_port_types_raw,
        )

    # Check if update contains templates or hostgroups
    has_templates = custom_fields.get("zabbix_templates") is not None
    has_hostgroups = custom_fields.get("zabbix_hostgroups") is not None

    # If port types is NOT being changed but templates/hostgroups are, allow it
    if not new_port_types and (has_templates or has_hostgroups):
        log.logger.info(
            "Device %s: Update contains templates=%s or hostgroups=%s, "
            "but NO port type change (always allowed)",
            device_name,
            has_templates,
            has_hostgroups,
        )
        return {"valid": True, "message": "Update contains templates or hostgroups"}

    # If no port type change AND no templates/hostgroups, nothing to validate
    if not new_port_types:
        log.logger.info(
            "Device %s: No port type change in update",
            device_name,
        )
        return {"valid": True, "message": "No port type change in update"}

    log.logger.debug(
        "Device %s: Validating %d port type(s): %s (templates=%s, hostgroups=%s)",
        device_name,
        len(new_port_types),
        new_port_types,
        has_templates,
        has_hostgroups,
    )

    # Find the corresponding Zabbix host
    zabbix_host: DeviceModelValidator | None
    zabbix_host_result: dict | None
    result: tuple[DeviceModelValidator | None, dict | None] = find_zabbix_host(data)
    zabbix_host, zabbix_host_result = result
    if not zabbix_host:
        log.logger.info(
            "Device %s: Zabbix host not found (allowing update)",
            device_name,
        )
        return {"valid": True, "message": "Zabbix host not found"}

    # Port type to interface type mapping
    port_type_mapping: dict[str, str] = {
        "Agent": "1",
        "SNMP": "2",
        "IPMI": "3",
        "JMX": "4",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
    }

    # Get current interface types on the host
    current_interface_types = zabbix_host.get_interface_types()
    log.logger.debug(
        "Device %s: Current interface types: %s",
        device_name,
        current_interface_types,
    )

    # Map new port types to interface types
    mapped_new_interface_types = set()
    for port_type in new_port_types:
        mapped = port_type_mapping.get(str(port_type))
        if mapped:
            mapped_new_interface_types.add(mapped)

    # Check if all new port types are already present (no actual change)
    if mapped_new_interface_types == current_interface_types:
        log.logger.info(
            "Device %s: Port types not changing (interfaces %s already present)",
            device_name,
            mapped_new_interface_types,
        )
        return {"valid": True, "message": "Port types not changing"}

    # Validate all port types together (each item depends on only ONE interface type,
    # so we need to ensure all required interface types are covered by the new port types)
    log.logger.debug(
        "Device %s: Validating %d port type(s): %s against existing items",
        device_name,
        len(new_port_types),
        new_port_types,
    )

    if zabbix_host_result and not check_new_port_type_compatibility(zabbix_host_result, new_port_types):
        log.logger.warning(
            "Device %s: Port type(s) %s are incompatible with existing items",
            device_name,
            new_port_types,
        )
        return {
            "valid": False,
            "message": f"Port types {get_port_type_names(mapped_new_interface_types)} incompatible with existing items",
        }

    log.logger.info(
        "Device %s: All %d port type(s) are safe: %s",
        device_name,
        len(new_port_types),
        new_port_types,
    )
    return {"valid": True, "message": f"All {len(new_port_types)} port type(s) are safe"}
