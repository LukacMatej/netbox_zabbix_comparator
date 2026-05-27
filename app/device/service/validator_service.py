import json
import requests
import os
from app.logger import logger_conf as log
from app.enums.item_types import ItemTypes

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

    def __init__(self, hostid: str, groupids: list[str], templateids: list[str],
                 interfaces: list[dict] | None = None, items: list[dict] | None = None) -> None:
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
    """Queries Zabbix for a host matching the given device name.
    This function is a placeholder for the actual implementation that would query Zabbix's API to find a host based on the device name.

    Args:
        device_name (str): The name of the device to search for in Zabbix.

    Returns:
        str | None: The JSON response from Zabbix or None if no matching host is found.
    """
    zabbix_api_token: str | None = os.environ.get("ZABBIX_KEY")
    zabbix_api_url: str | None = os.environ.get("ZABBIX_URL")
    if not zabbix_api_token or not zabbix_api_url:
        return None
    headers= {
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
            zabbix_api_url,
            headers=headers,
            json=payload,
            timeout=5.0
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if "error" in response.json():
            log.logger.error(f"Error querying Zabbix for host {device_name}: {response.json()['error']}")
            return None
        return result[0] if result else None
    except requests.RequestException as e:
        log.logger.error(f"Error querying Zabbix for host {device_name}: {e}")
    return None

def check_items_dependency(zabbix_host_result: dict, data: dict) -> bool:
    """Checks if the items in the Zabbix host are dependent on the old port type.
    This function checks if items associated with the Zabbix host are linked to a specific
    interface type that would be affected by changing the port type.

    Args:
        zabbix_host_result (dict): The Zabbix host object containing host details.
        data (dict): The input data containing information about the device update.

    Returns:
        bool: True if items are NOT dependent on the old port type (update is safe), False if items depend on old port type.
    """
    if not zabbix_host_result or not isinstance(zabbix_host_result, dict):
        return True  # Safe to update if no host data available

    # Get current interface types on the host
    interfaces = zabbix_host_result.get("interfaces", [])
    current_interface_types = {interface.get("type") for interface in interfaces}

    # Get items associated with the host
    items = zabbix_host_result.get("selectItems", [])
    if not items:
        return True  # No items to check

    # Map item types to required interface types
    # Based on Zabbix documentation, certain item types require specific interface types
    item_type_to_interface_mapping = {
        ItemTypes.ZABBIX_AGENT.value: "1",  # Agent
        ItemTypes.ZABBIX_AGENT_ACTIVE.value: "1",  # Agent (active)
        ItemTypes.SNMP_AGENT.value: "2",  # SNMP
        ItemTypes.SNMP_TRAP.value: "2",  # SNMP Trap
        ItemTypes.IPMI_AGENT.value: "3",  # IPMI
        ItemTypes.JMX_AGENT.value: "4",  # JMX
        ItemTypes.SSH_AGENT.value: "1",  # SSH uses Agent interface
        ItemTypes.TELNET_AGENT.value: "1",  # Telnet uses Agent interface
        ItemTypes.HTTP_AGENT.value: "1",  # HTTP Agent uses Agent interface
        # Item types that don't require specific interfaces
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

    # Check each item and its interface dependency
    for item in items:
        item_type = int(item.get("type", 0))
        required_interface_type = item_type_to_interface_mapping.get(item_type)

        # If item type requires a specific interface
        if required_interface_type is not None:
            # Check if item has an interfaceid (is bound to a specific interface)
            if item.get("interfaceid"):
                # If the required interface type is not in current interfaces, items depend on current config
                if required_interface_type not in current_interface_types:
                    return False  # Unsafe to update

    return True  # Safe to update

def find_zabbix_host(data: dict) -> DeviceModelValidator | None:
    """Finds the corresponding Zabbix host based on the provided data.
    This function takes a dictionary containing information about a device update and attempts to find the corresponding Zabbix host in Zabbix.
    It uses the device's name and other relevant details to perform the lookup.

    Args:
        data (dict): A dictionary containing information about the device update, including custom fields and other relevant details for identifying the corresponding Zabbix host.

    Returns:
        DeviceModelValidator | None: An instance of the DeviceModelValidator representing the corresponding Zabbix host if found, or None if no matching host is found.
    """
    device_name = data.get("data", {}).get("name")
    if not device_name:
        return None

    zabbix_host_result: dict | None = query_zabbix_for_host(device_name)
    if not zabbix_host_result:
        return None

    if not check_items_dependency(zabbix_host_result, data):
        return None

    # Extract necessary fields from Zabbix response
    hostid = zabbix_host_result.get("hostid", "")

    # Extract group IDs
    groups = zabbix_host_result.get("groups", [])
    groupids = [group.get("groupid") for group in groups if group.get("groupid")]

    # Extract template IDs
    parent_templates = zabbix_host_result.get("parentTemplates", [])
    templateids = [template.get("templateid") for template in parent_templates if template.get("templateid")]

    # Get interfaces and items
    interfaces = zabbix_host_result.get("interfaces", [])
    items = zabbix_host_result.get("selectItems", [])

    return DeviceModelValidator(hostid, groupids, templateids, interfaces, items)

def can_update_device(data: dict):
    """Checks if update is allowed to change zabbix host.
    If update contains templates or hostgroups, then update is allowed.
    If update contains different port type than linked zabbix host, then check if data items in zabbix are linked to old port type.
    If data items are linked to old port type, then update is not allowed, otherwise update is allowed.

    Args:
        data (dict): The input data containing information about the device update, including custom fields and other relevant details for validation.

    Returns:
        dict: A dictionary containing the validation result with keys 'valid' (bool) indicating if the update is allowed, and 'message' (str) providing additional information about the validation outcome.
    """
    # 1. Define the fields that are relevant for validation
    TARGET_FIELDS: set[str] = {"zabbix_port_type", "zabbix_templates", "zabbix_hostgroups"}

    # 2. Extract custom fields from the update data
    custom_fields = data.get("data", {}).get("custom_fields", {})
    if not custom_fields:
        return {"valid": True, "message": "No custom fields to validate"}

    # 3. Check if update contains templates or hostgroups
    has_templates = custom_fields.get("zabbix_templates") is not None
    has_hostgroups = custom_fields.get("zabbix_hostgroups") is not None

    if has_templates or has_hostgroups:
        return {"valid": True, "message": "Update contains templates or hostgroups"}

    # 4. Check if port type is being changed
    new_port_type = custom_fields.get("zabbix_port_type")
    if not new_port_type:
        return {"valid": True, "message": "No port type change in update"}

    # 5. Find the corresponding Zabbix host
    zabbix_host: DeviceModelValidator | None = find_zabbix_host(data)
    if not zabbix_host:
        return {"valid": True, "message": "Zabbix host not found"}

    # 6. Check if port type is different from current interfaces
    current_interface_types = zabbix_host.get_interface_types()

    # Map port type strings to Zabbix interface type numbers
    # Agent = 1, SNMP = 2, IPMI = 3, JMX = 4
    port_type_mapping: dict[str, str] = {
        "Agent": "1",
        "SNMP": "2",
        "IPMI": "3",
        "JMX": "4",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4"
    }

    mapped_port_type: str | None = port_type_mapping.get(str(new_port_type))

    # If port type is not changing, allow update
    if mapped_port_type in current_interface_types:
        return {"valid": True, "message": "Port type not changing"}

    # 7. Port type is changing, but no dependent items exist
    # (already validated in check_items_dependency called from find_zabbix_host)
    return {"valid": True, "message": "Port type change is safe"}
