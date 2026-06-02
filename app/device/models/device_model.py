"""
Device model module for managing network device information and Zabbix API operations.
This module provides the Device class and utility functions for device status normalization,
interface conversion, and port type mapping for Zabbix API integration.
Classes:
    Device: Represents a network device with properties and methods for Zabbix operations.
Functions:
    format_nb_status(status: str) -> str:
        Convert NetBox device status to a standardized lowercase format.
    map_port_type(port_type: str) -> str:
        Map port type to Zabbix-compatible format (Agent, SNMP, IPMI, JMX).
    normalize_status(status: str) -> str:
        Normalize device status to standard "Active" or "Inactive" format.
    dict_interfaces_zb(interfaces: list[InterfaceModel]) -> list[dict]:
        Convert InterfaceModel objects to Zabbix API interface dictionaries for host creation.
    dict_interfaces_zb_id(interfaces: list[InterfaceModel], interface_id) -> list[dict]:
        Convert InterfaceModel objects to Zabbix API interface dictionaries for host updates.
"""

from app.device.models.interface_model import Interface as InterfaceModel


class Device:
    """
    A Device model class for managing device information and Zabbix API operations.
    This class represents a network device with its properties and provides methods
    to serialize device data for Zabbix API interactions.
    Attributes:
        name (str): The name of the device.
        interfaces (list[InterfaceModel]): List of network interfaces associated with the device.
        hostgroup (list[str]): List of host groups the device belongs to.
        description (str): Description of the device.
        templates (list[str]): List of monitoring templates applied to the device.
        status (str): The status of the device (e.g., "Active", "Inactive").
    Methods:
        __init__(name, interfaces, hostgroup, description, templates, status):
            Initializes a Device instance with the provided parameters.
            Normalizes the status using the normalize_status function.
        __str__() -> str:
            Returns a string representation of the device containing all its attributes.
        update_data_zabbix(hostid, interface_id, hostgroupIds, templateids, name) -> dict:
            Generates a Zabbix API request dictionary for updating an existing host.
            Handles various hostgroup ID formats
            and constructs proper group and template configurations.
        create_data_zabbix(hostgroupIds, templateids) -> dict:
            Generates a Zabbix API request dictionary for creating a new host.
            Processes hostgroup IDs and template IDs into the required Zabbix format.
    """

    name: str = ""
    interfaces: list[InterfaceModel] = []
    hostgroup: list[str] | str = []
    description: str = ""
    templates: list[str] = []
    status: str = ""

    def __init__(
        self, name, interfaces, hostgroup, description, templates, status
    ) -> None:
        self.name = name
        self.interfaces = interfaces
        self.hostgroup = hostgroup
        self.description = description
        self.templates = templates
        self.status = normalize_status(status)

    def __str__(self) -> str:
        return (
            f"{self.name} {self.interfaces} {self.hostgroup} "
            f"{self.description} {self.templates} {self.status}"
        )

    def update_data_zabbix(
        self,
        hostid,
        interface_ids,
        hostgroupids,
        templateids,
        name,
        include_interfaces: bool = True,
    ) -> dict:
        """Creates a dictionary representation of the device for Zabbix API."""
        groups = []
        for gid in hostgroupids:
            if gid and gid != -1:  # Skip invalid IDs
                try:
                    if isinstance(gid, (int, str)):
                        groups.append({"groupid": int(gid)})
                    elif isinstance(gid, list) and gid:
                        groups.append({"groupid": int(gid[0])})
                    elif isinstance(gid, dict) and "groupid" in gid:
                        groups.append({"groupid": int(gid["groupid"])})
                except (ValueError, TypeError):
                    continue

        params = {
            "hostid": hostid,
            "host": name,
            "name": name,
            "groups": groups,
            "description": self.description,
            "templates": [{"templateid": tempId} for tempId in templateids if tempId],
            "status": 0 if self.status == "Active" else 1,
        }
        if include_interfaces:
            params["interfaces"] = ([
                dict_interfaces_zb_id(self.interfaces, interface_id=interface_id)
                if self.interfaces
                else []
            ] for interface_id in interface_ids
                                    )

        return {
            "jsonrpc": "2.0",
            "method": "host.update",
            "params": params,
            "id": 1,
        }

    def clear_templates_data_zabbix(self, hostid, templateids) -> dict:
        """Creates a dictionary representation for Zabbix host template update."""
        return {
            "jsonrpc": "2.0",
            "method": "host.update",
            "params": {
                "hostid": hostid,
                "templates_clear": [{"templateid": tempId} for tempId in templateids if tempId],
            },
            "id": 1,
        }

    def update_interface_data_zabbix(self, interface_ids) -> dict:
        """Creates a dictionary representation for Zabbix host interface update."""

        params = []
        for index, interface_id in enumerate(interface_ids):
            params.append(
                {
                    "interfaceid": interface_id,
                    "type": self.interfaces[index].port_type,
                    "main": _is_main_interface(self.interfaces, index),
                    "useip": 1,
                    "ip": (
                        str(self.interfaces[index].addresses[0].address).split("/", maxsplit=1)[0]
                        if self.interfaces[index].addresses
                        else ""
                    ),
                    "dns": self.interfaces[index].addresses[0].dns_name if self.interfaces[index].addresses else "",
                    "port": map_port_type_default_port(self.interfaces[index].port_type),
                    "details": {"version": 3},
                }
            )
        return {
            "jsonrpc": "2.0",
            "method": "hostinterface.update",
            "params": params,
            "id": 1,
        }

    def create_data_zabbix(self, hostgroupids, templateids) -> dict:
        """Creates a dictionary representation of the device for Zabbix API."""
        groups = []
        for gid in hostgroupids:
            if gid and gid != -1:  # Skip invalid IDs
                try:
                    if isinstance(gid, (int, str)):
                        groups.append({"groupid": int(gid)})
                    elif isinstance(gid, list) and gid:
                        groups.append({"groupid": int(gid[0])})
                    elif isinstance(gid, dict) and "groupid" in gid:
                        groups.append({"groupid": int(gid["groupid"])})
                except (ValueError, TypeError):
                    continue
        return {
            "jsonrpc": "2.0",
            "method": "host.create",
            "params": {
                "host": self.name,
                "name": self.name,
                "interfaces": dict_interfaces_zb(self.interfaces) if self.interfaces else [],
                "groups": groups,
                "description": self.description,
                "templates": [{"templateid": tempId} for tempId in templateids if tempId],
                "status": 0 if self.status == "Active" else 1,
            },
            "id": 1,
        }

    @staticmethod
    def get_device_fields() -> list[str]:
        """Returns a list of device fields for comparison."""
        return list(Device.__annotations__.keys())



def format_nb_status(status: str) -> str:
    """
    Convert NetBox device status to a standardized status format.
    Maps NetBox status values to their corresponding lowercase representations.
    If the status is not found in the mapping, defaults to "offline".
    Args:
        status (str): The NetBox device status to be converted.
                     Expected values: "Active", "Inactive", "Planned", "Staged",
                     "Failed", "Inventory", or "Decommissioning".
    Returns:
        str: The standardized status string in lowercase.
             Possible values: "active", "offline", "planned", "staged",
             "failed", "inventory", or "decommissioning".
    Examples:
        >>> format_nb_status("Active")
        'active'
        >>> format_nb_status("Inactive")
        'offline'
        >>> format_nb_status("Unknown")
        'offline'
    """

    status_map = {
        "Active": "active",
        "Inactive": "offline",
        "Planned": "planned",
        "Staged": "staged",
        "Failed": "failed",
        "Inventory": "inventory",
        "Decommissioning": "decommissioning",
    }
    return status_map.get(status, "offline")

def normalize_status(status: str) -> str:
    """
    Normalize device status to a standard format.
    Converts various representations of active status into a standardized
    "Active" or "Inactive" string. Accepts numeric (0), string ("0"), or
    text ("Active") representations of active status.
    Args:
        status (str): The status value to normalize. Can be 0, "0", or "Active".
    Returns:
        str: "Active" if status matches active indicators, otherwise "Inactive".
    Examples:
        >>> normalize_status(0)
        "Active"
        >>> normalize_status("0")
        "Active"
        >>> normalize_status("Active")
        "Active"
        >>> normalize_status("Inactive")
        "Inactive"
    """

    if status in (0, "0", "Active"):
        return "Active"
    return "Inactive"


def _is_main_interface(interfaces: list[InterfaceModel], index: int) -> int:
    """Mark the first interface for each monitoring type as the default."""
    port_type = interfaces[index].port_type
    for previous_index in range(index):
        if interfaces[previous_index].port_type == port_type:
            return 0
    return 1


def dict_interfaces_zb(interfaces: list[InterfaceModel]) -> list[dict]:
    """Converts a list of InterfaceModel objects to a list of dictionaries."""
    result = []
    for index, interface in enumerate(interfaces):
        if interface.port_type in ("1", "Agent"):
            result.append(
                {
                    "type": interface.port_type,
                    "main": _is_main_interface(interfaces, index),
                    "useip": 1,
                    "ip": (
                        str(interface.addresses[0].address).split("/", maxsplit=1)[0]
                        if interface.addresses
                        else ""
                    ),
                    "dns": interface.addresses[0].dns_name if interface.addresses else "",
                    "port": map_port_type_default_port(interface.port_type),
                }
            )
        elif interface.port_type in ("2", "SNMP"):
            result.append(
                {
                    "type": interface.port_type,
                    "main": _is_main_interface(interfaces, index),
                    "useip": 1,
                    "ip": (
                        str(interface.addresses[0].address).split("/", maxsplit=1)[0]
                        if interface.addresses
                        else ""
                    ),
                    "dns": interface.addresses[0].dns_name if interface.addresses else "",
                    "port": map_port_type_default_port(interface.port_type),
                    "details": {"version": 3},
                }
            )
        else:
            result.append(
                {
                    "type": interface.port_type,
                    "main": _is_main_interface(interfaces, index),
                    "useip": 1,
                    "ip": (
                        str(interface.addresses[0].address).split("/", maxsplit=1)[0]
                        if interface.addresses
                        else ""
                    ),
                    "dns": interface.addresses[0].dns_name if interface.addresses else "",
                    "port": map_port_type_default_port(interface.port_type),
                    "details": {"version": 3},
                }
            )
    return result


def dict_interfaces_zb_id(interfaces: list[InterfaceModel], interface_id) -> list[dict]:
    """Converts a list of InterfaceModel objects to a list of dictionaries."""
    result = []
    for index, interface in enumerate(interfaces):
        result.append(
            {
                "type": interface.port_type,
                "interfaceid": interface_id,
                "main": _is_main_interface(interfaces, index),
                "useip": 1,
                "ip": (
                    str(interface.addresses[0].address).split("/", maxsplit=1)[0]
                    if interface.addresses
                    else ""
                ),
                "dns": interface.addresses[0].dns_name if interface.addresses else "",
                "port": map_port_type_default_port(interface.port_type),
                "details": {"version": 3},
            }
        )
    return result

def map_port_type_default_port(port_type: str) -> str:
    """
    Maps the port type to its default port number.
    Args:
        port_type (str): The port type to be mapped.
    Returns:
        str: The default port number corresponding to the given port type.
    """
    port_map = {
        "1": "10050",
        "2": "161",
        "3": "623",
        "4": "12345",
        "Agent": "10050",
        "SNMP": "161",
        "IPMI": "623",
        "JMX": "12345",
    }
    return port_map.get(port_type, "161")
