"""Validator service for Zabbix device updates.

This module provides validation functions to ensure device updates are compatible
with existing Zabbix host configurations, especially for port type changes.
"""
import os
import re
from typing import Any

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

PORT_TYPE_MAPPING: dict[str, str] = {
    "Agent": "1", "SNMP": "2", "IPMI": "3", "JMX": "4",
    "1": "1", "2": "2", "3": "3", "4": "4",
}


def map_port_types(port_types: list[str]) -> set[str] | None:
    """Map a list of port type names/codes to Zabbix's numeric interface type codes.

    Returns None if any entry doesn't map to a known port type.
    """
    mapped: set[str] = set()
    for port_type in port_types:
        code = PORT_TYPE_MAPPING.get(str(port_type))
        if not code:
            log.logger.error("Invalid port type '%s' (no mapping found)", port_type)
            return None
        mapped.add(code)
    return mapped


def _normalize_to_list(value: Any) -> list:
    """Normalize a NetBox custom field value (str, list, or None/empty) to a list."""
    if isinstance(value, list):
        return [v for v in value if v]
    if value:
        return [value]
    return []


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


def _zabbix_post(method: str, params: Any) -> list | None:
    """POST a Zabbix JSON-RPC request and return its "result".

    Returns None on any failure: missing credentials, a network error, or a
    Zabbix API-level error. Centralizes what query_zabbix_for_host and
    query_zabbix_template_items both need.
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

    headers = {
        'Content-Type': 'application/json-rpc',
        'Authorization': f'Bearer {zabbix_api_token}'
    }
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
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
            log.logger.error("Zabbix API error calling %s: %s", method, response_json["error"])
            return None

        return response_json.get("result", [])

    except requests.RequestException as e:
        log.logger.error("HTTP error calling Zabbix %s: %s", method, e)
        return None


def query_zabbix_for_host(device_name: str) -> dict | None:
    """Query Zabbix for a host matching the given device name."""
    log.logger.debug("Querying Zabbix for host: %s", device_name)
    result = _zabbix_post(
        "host.get",
        {
            "output": "extend",
            "filter": {
                "host": [device_name]
            },
            "selectInterfaces": "extend",
            # "hostgroups" (Zabbix >= 6.0) - the pre-6.0 "groups"/selectGroups
            # naming is silently ignored by newer Zabbix and returns nothing.
            "selectHostGroups": "extend",
            "selectParentTemplates": "extend",
            "selectItems": "extend"
        },
    )
    if not result:
        return None

    host_data = result[0]
    log.logger.info(
        "Found Zabbix host '%s' (hostid=%s) with %d interfaces and %d items",
        device_name,
        host_data.get("hostid"),
        len(host_data.get("interfaces", [])),
        len(host_data.get("items", [])),
    )
    return host_data


def query_zabbix_template_items(template_names: list[str]) -> list[dict]:
    """Fetch the items that belong to the given Zabbix templates (by name).

    Used to check whether templates NetBox wants to newly link to a host
    would need an interface type the host doesn't (or won't) have — Zabbix
    only rejects this at update time, so this lets it be caught ahead of time.
    Fails open (returns []) on any lookup failure, consistent with the rest
    of this module's fail-open behavior when Zabbix can't be reached.
    """
    if not template_names:
        return []
    templates = _zabbix_post(
        "template.get",
        {"filter": {"host": template_names}, "output": ["templateid", "host"]},
    )
    if not templates:
        return []
    templateids = [t["templateid"] for t in templates if "templateid" in t]
    if not templateids:
        return []
    items = _zabbix_post(
        "item.get",
        {"templateids": templateids, "output": ["itemid", "name", "type", "key_", "params"]},
    )
    return items or []


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


def _first_unsatisfied_item(items: list[dict], mapped_port_types: set[str]) -> dict | None:
    """Return the first item whose interface requirement isn't covered by
    mapped_port_types (RULES 2 & 3 below), or None if every item is satisfied.

    Shared between check_new_port_type_compatibility (existing items on the
    host vs. proposed port types) and the new-template check in
    can_update_device (a new template's items vs. the effective port types).
    """
    for item in items:
        item_type = int(item.get("type", 0))
        item_key = item.get("key_", "")
        item_params = item.get("params", "")
        req_interface = get_item_interface_requirement(item_type, item_key, item_params)

        # --- RULE 2: Strict Requirement Check ---
        if isinstance(req_interface, str):
            if req_interface not in mapped_port_types:
                log.logger.warning(
                    "Item '%s' (type=%s) strictly requires interface %s, not covered by port types %s",
                    item.get("name", "unknown"),
                    item_type,
                    req_interface,
                    mapped_port_types,
                )
                return item

        # --- RULE 3: Loose Requirement Check ---
        elif req_interface is True:
            if not mapped_port_types:
                log.logger.warning(
                    "Item '%s' (type=%s) requires an interface, but no port types are provided.",
                    item.get("name", "unknown"),
                    item_type
                )
                return item

    return None


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

    mapped_port_types = map_port_types(new_port_types)
    if mapped_port_types is None:
        return False

    # 1. Map current Interface IDs to their Interface Types
    # This is crucial because Zabbix will block deleting an interface if an item is linked to it.
    existing_interfaces = zabbix_host_result.get("interfaces", [])
    interface_id_to_type = {
        iface.get("interfaceid"): iface.get("type")
        for iface in existing_interfaces if iface.get("interfaceid")
    }

    items = zabbix_host_result.get("items", [])
    for item in items:
        linked_interface_id = item.get("interfaceid", "0")

        # --- RULE 1: Zabbix API Database Constraint ---
        # If the item is already hard-linked to an interface ID, what type is it?
        current_linked_type = interface_id_to_type.get(linked_interface_id)

        # If the item is linked to an interface, and that interface type is NOT in the new payload,
        # Zabbix will throw a constraint error ("Interface is linked to item...").
        if linked_interface_id and linked_interface_id != "0" and current_linked_type:
            if current_linked_type not in mapped_port_types:
                log.logger.warning(
                    "Validation Failed: Item '%s' is hard-linked to interface type %s (ID: %s). "
                    "Removing this interface type will trigger a Zabbix API constraint error.",
                    item.get("name", "unknown"),
                    current_linked_type,
                    linked_interface_id
                )
                return False

    return _first_unsatisfied_item(items, mapped_port_types) is None

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
    # "hostgroups" is the Zabbix >= 6.0 key (from selectHostGroups); the old
    # "groups"/selectGroups naming this used to read is silently ignored by
    # newer Zabbix and never actually populated groupids.
    groups = zabbix_host_result.get("hostgroups", [])
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


def can_update_device(data: dict):  # pylint: disable=too-many-return-statements,too-many-branches
    """Check if a device update is compatible with the host's Zabbix configuration.

    Both zabbix_port_type and zabbix_templates changes can affect which
    interface types the host's Zabbix items need, so both are checked:
      - Case A (port type changing): do the currently-linked items still
        have an interface to attach to under the new port types?
      - Case B (templates changing): do the *new* templates' items have an
        interface to attach to, given the effective port types (the new
        ones if those are also changing, otherwise the host's current ones)?
    zabbix_hostgroups alone never affects interfaces, so it's not checked.
    """
    device_name = data.get("data", {}).get("name", "unknown")
    custom_fields = data.get("data", {}).get("custom_fields", {})
    if not custom_fields:
        return {"valid": True, "message": "No custom fields to validate"}

    new_port_types = _normalize_to_list(custom_fields.get("zabbix_port_type"))
    new_templates = _normalize_to_list(custom_fields.get("zabbix_templates"))

    if not new_port_types and not new_templates:
        return {"valid": True, "message": "No port type or template change in update"}

    result: tuple[DeviceModelValidator | None, dict | None] = find_zabbix_host(data)
    zabbix_host, zabbix_host_result = result

    if not zabbix_host:
        return {"valid": True, "message": "Zabbix host not found"}

    current_interface_types = zabbix_host.get_interface_types()

    port_type_changing = False
    if new_port_types:
        mapped_new_interface_types = map_port_types(new_port_types)
        if mapped_new_interface_types is None:
            return {"valid": False, "message": f"Invalid port type(s) in update: {new_port_types}"}
        port_type_changing = mapped_new_interface_types != current_interface_types
    else:
        # Port type isn't part of this update, so whatever ends up on the
        # host is whatever's already there.
        mapped_new_interface_types = current_interface_types

    if port_type_changing:
        if zabbix_host_result and not check_new_port_type_compatibility(zabbix_host_result, new_port_types):
            return {
                "valid": False,
                "message": f"Port types {get_port_type_names(mapped_new_interface_types)} incompatible with existing items",
            }

    if new_templates:
        new_items = query_zabbix_template_items(new_templates)
        offending = _first_unsatisfied_item(new_items, mapped_new_interface_types)
        if offending:
            return {
                "valid": False,
                "message": (
                    f"Template item '{offending.get('name') or offending.get('key_', 'unknown')}' "
                    f"requires an interface not in {get_port_type_names(mapped_new_interface_types)}"
                ),
            }

    if new_port_types and not port_type_changing and not new_templates:
        return {"valid": True, "message": "Port types not changing"}

    if new_port_types:
        return {"valid": True, "message": f"All {len(new_port_types)} port type(s) are safe"}

    return {"valid": True, "message": "Template change is compatible with existing port types"}
