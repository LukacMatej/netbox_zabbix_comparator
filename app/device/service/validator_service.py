"""Validator service for Zabbix device updates.

This module provides validation functions to ensure device updates are compatible
with existing Zabbix host configurations, especially for port type changes.
"""
import os
import re
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
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        hostid: str,
        groupids: list[str],
        templateids: list[str],
        interfaces: list[dict] | None = None,
        items: list[dict] | None = None,
    ) -> None:
        self.hostid: str = hostid
        self.groupids: list[str] = groupids if groupids else []
        self.templateids: list[str] = templateids if templateids else []
        self.interfaces: list[dict] = interfaces if interfaces else []
        self.items: list[dict] = items if items else []

    def get_interface_types(self) -> set[str]:
        return {interface.get("type", "") for interface in self.interfaces}

    def get_item_types(self) -> set[int]:
        return {int(item.get("type", 0)) for item in self.items}


def query_zabbix_for_host(device_name: str) -> dict | None:
    """Query Zabbix for a host matching the given device name."""
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
        response = requests.post(
            f"{zabbix_api_url}/api_jsonrpc.php",
            headers=headers,
            json=payload,
            timeout=5.0
        )
        response.raise_for_status()
        response_json = response.json()

        if "error" in response_json:
            log.logger.error("Zabbix API error for host %s: %s", device_name, response_json["error"])
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

        return None

    except requests.RequestException as e:
        log.logger.error("HTTP error querying Zabbix for host %s: %s", device_name, e)
        return None


def get_item_interface_requirement(item_type: int, item_key: str = "", extra_params: str = "") -> str | bool:
    """
    Determines the interface requirement for a Zabbix item.

    Returns:
        str: The specific interface type required (e.g., "1" for Agent, "2" for SNMP).
        True: If ANY interface is required (loose requirement, e.g., Simple Checks).
        False: If no interface is required at all.
    """
    # 1. Strictly Required by Zabbix API
    strict_mapping = {
        ItemTypes.ZABBIX_AGENT.value: "1",
        ItemTypes.ZABBIX_AGENT_ACTIVE.value: "1",
        ItemTypes.SNMP_AGENT.value: "2",
        ItemTypes.SNMP_TRAP.value: "2",
        ItemTypes.IPMI_AGENT.value: "3",
        ItemTypes.JMX_AGENT.value: "4",
    }
    if item_type in strict_mapping:
        return strict_mapping[item_type]

    # 2. Strictly Exempt (Never requires an interface)
    exempt_types = {
        ItemTypes.ZABBIX_TRAPPER.value,
        ItemTypes.ZABBIX_INTERNAL.value,
        ItemTypes.WEB_ITEM.value,
        ItemTypes.DATABASE_MONITOR.value,
        ItemTypes.CALCULATED.value,
        ItemTypes.DEPENDENT_ITEM.value
    }
    if item_type in exempt_types:
        return False

    # 3. Conditional / Loose Requirements
    # Simple and External checks implicitly require an IP to target, even without macros
    if item_type in {ItemTypes.SIMPLE_CHECK.value, ItemTypes.EXTERNAL_CHECK.value}:
        return True

    # Check for macros in the key or params that rely on connection info
    macro_pattern = re.compile(r"\{HOST\.(CONN|IP|DNS|PORT)\d*\}")
    if macro_pattern.search(item_key) or macro_pattern.search(extra_params):
        return True

    return False


def check_new_port_type_compatibility(
    zabbix_host_result: dict,
    new_port_types: list[str],
) -> bool:
    """Check if new port types can satisfy the host's existing items.

    Args:
        zabbix_host_result (dict): The Zabbix host with current config.
        new_port_types (list[str]): List of new port types to validate.

    Returns:
        bool: True if the new port types satisfy all required item interfaces.
    """
    if not zabbix_host_result:
        return True

    port_type_mapping: dict[str, str] = {
        "Agent": "1", "SNMP": "2", "IPMI": "3", "JMX": "4",
        "1": "1", "2": "2", "3": "3", "4": "4",
    }

    mapped_port_types: set[str] = set()
    for port_type in new_port_types:
        mapped_port_type = port_type_mapping.get(str(port_type))
        if not mapped_port_type:
            log.logger.error("Invalid port type '%s' (no mapping found)", port_type)
            return False
        mapped_port_types.add(mapped_port_type)

    items = zabbix_host_result.get("items", [])
    for item in items:
        item_type = int(item.get("type", 0))
        item_key = item.get("key_", "")
        item_params = item.get("params", "")

        # Call our 3-phase algorithm
        req_interface = get_item_interface_requirement(item_type, item_key, item_params)

        if isinstance(req_interface, str):
            # The item strictly requires a specific interface (e.g., SNMP_AGENT needs "2")
            if req_interface not in mapped_port_types:
                log.logger.warning(
                    "Item '%s' (type=%s) strictly requires interface %s, but new port types %s only provide %s",
                    item.get("name", "unknown"),
                    item_type,
                    req_interface,
                    new_port_types,
                    mapped_port_types,
                )
                return False

        elif req_interface is True:
            # The item requires AT LEAST ONE interface, but doesn't care which type (e.g. Simple Check)
            if not mapped_port_types:
                log.logger.warning(
                    "Item '%s' (type=%s) requires an interface, but no port types are provided.",
                    item.get("name", "unknown"),
                    item_type
                )
                return False

    return True


def find_zabbix_host(data: dict) -> tuple[DeviceModelValidator | None, dict | None]:
    """Find the corresponding Zabbix host based on the provided data."""
    device_name = data.get("data", {}).get("name")
    if not device_name:
        log.logger.warning("No device name found in update data")
        return None, None

    zabbix_host_result: dict | None = query_zabbix_for_host(device_name)
    if not zabbix_host_result:
        return None, None

    hostid = zabbix_host_result.get("hostid", "")
    groups = zabbix_host_result.get("groups", [])
    groupids = [group.get("groupid") for group in groups if group.get("groupid")]

    parent_templates = zabbix_host_result.get("parentTemplates", [])
    templateids = [
        template.get("templateid")
        for template in parent_templates
        if template.get("templateid")
    ]

    interfaces = zabbix_host_result.get("interfaces", [])
    items = zabbix_host_result.get("items", [])

    return DeviceModelValidator(hostid, groupids, templateids, interfaces, items), zabbix_host_result


def can_update_device(data: dict):  # pylint: disable=too-many-return-statements
    """Check if device update is allowed."""
    device_name = data.get("data", {}).get("name", "unknown")
    custom_fields = data.get("data", {}).get("custom_fields", {})
    if not custom_fields:
        return {"valid": True, "message": "No custom fields to validate"}

    new_port_types_raw = custom_fields.get("zabbix_port_type")
    new_port_types = []

    if isinstance(new_port_types_raw, list):
        if len(new_port_types_raw) > 0:
            new_port_types = new_port_types_raw
    elif new_port_types_raw:
        new_port_types = [new_port_types_raw]

    has_templates = custom_fields.get("zabbix_templates") is not None
    has_hostgroups = custom_fields.get("zabbix_hostgroups") is not None

    if not new_port_types and (has_templates or has_hostgroups):
        return {"valid": True, "message": "Update contains templates or hostgroups"}

    if not new_port_types:
        return {"valid": True, "message": "No port type change in update"}

    result: tuple[DeviceModelValidator | None, dict | None] = find_zabbix_host(data)
    zabbix_host, zabbix_host_result = result

    if not zabbix_host:
        return {"valid": True, "message": "Zabbix host not found"}

    port_type_mapping: dict[str, str] = {
        "Agent": "1", "SNMP": "2", "IPMI": "3", "JMX": "4",
        "1": "1", "2": "2", "3": "3", "4": "4",
    }

    current_interface_types = zabbix_host.get_interface_types()

    mapped_new_interface_types = set()
    for port_type in new_port_types:
        mapped = port_type_mapping.get(str(port_type))
        if mapped:
            mapped_new_interface_types.add(mapped)

    if mapped_new_interface_types == current_interface_types:
        return {"valid": True, "message": "Port types not changing"}

    if zabbix_host_result and not check_new_port_type_compatibility(zabbix_host_result, new_port_types):
        return {
            "valid": False,
            "message": f"Port types {get_port_type_names(mapped_new_interface_types)} incompatible with existing items",
        }

    return {"valid": True, "message": f"All {len(new_port_types)} port type(s) are safe"}
