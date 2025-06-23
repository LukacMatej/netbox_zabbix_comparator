from app.device.models.interface_model import Interface as InterfaceModel
from app.device.service import device_service as ds

class Device:
    name: str = ""
    interfaces: list[InterfaceModel] = []
    hostgroup: list[str] = []
    description: str = ""
    templates: list[str] = []
    status: str = ""
            
    def __init__(self, name, interfaces, hostgroup, description, templates, status) -> None:
        self.name = name
        self.interfaces = interfaces
        self.hostgroup = hostgroup
        self.description = description
        self.templates = templates
        self.status = normalize_status(status)
        
    def __str__(self) -> str:
        return f"{self.name} {self.interfaces} {self.hostgroup} {self.description} {self.templates} {self.status}"

    def update_data_zabbix(self, hostid, interface_id, hostgroupId, templateids) -> dict:
        """Creates a dictionary representation of the device for Zabbix API."""
        return {
            "jsonrpc": "2.0",
            "method": "host.update",
            "params": {
                "hostid": hostid,
                "interfaces": dict_interfaces_zb_id(self.interfaces,interface_id=interface_id) if self.interfaces else [],
                "groups": [{"groupid": hostgroupId}],
                "description": self.description,
                "templates": [{"templateid": tempId} for tempId in templateids if tempId],
                "status": 0 if self.status == "Active" else 1
            },
            "id": 1
        }
    def create_data_zabbix(self, hostgroupIds, templateids) -> dict:
        """Creates a dictionary representation of the device for Zabbix API."""
        return {
            "jsonrpc": "2.0",
            "method": "host.create",
            "params": {
            "host": self.name,
            "interfaces": dict_interfaces_zb(self.interfaces) if self.interfaces else [],
            "groups": [{"groupid": int(groupId)} for groupId in hostgroupIds if groupId],
            "description": self.description,
            "templates": [{"templateid": tempId} for tempId in templateids if tempId],
            "status": 0 if self.status == "Active" else 1
            },
            "id": 1
        }

    def create_data_netbox(self) -> dict:
        """Creates a dictionary representation of the device for Netbox API."""
        return {
            "name": self.name,
            "device_type": ds.find_nb_device_type_id("Catalyst 2970 Series"), # Replace with actual device type
            "role": ds.find_nb_device_role_id(str(self.hostgroup).split("/")[2]),
            "site": ds.find_nb_site_id(str(self.hostgroup).split("/")[0]),
            "status": format_nb_status(self.status),
            "local_context_data": {
                "zabbix": {
                    "templates": [
                        str(template) for template in self.templates if template
                    ]
                    }
            }
        }

def format_nb_status(status: str) -> str:
    status_map = {
        "Active": "active",
        "Inactive": "offline",
        "Planned": "planned",
        "Staged": "staged",
        "Failed": "failed",
        "Inventory": "inventory",
        "Decommissioning": "decommissioning"
    }
    return status_map.get(status, "offline")

def map_port_type(port_type: str) -> str:
    """Maps the port type to a Netbox compatible format."""
    if isinstance(port_type, list):
        port_type = port_type[0] if port_type else ""
    port_type_map = {
        "Agent": "1",
        "SNMP": "2",
        "IPMI": "3",
        "JMX": "4",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4"
    }
    return port_type_map.get(port_type, "1")

def normalize_status(status: str) -> str:
    if status == 0 or status == "Active" or status == "0":
        return "Active"
    return "Inactive"

def dict_interfaces_zb(interfaces: list[InterfaceModel]) -> list[dict]:
    """Converts a list of InterfaceModel objects to a list of dictionaries."""
    result = []
    for index, interface in enumerate(interfaces):
        result.append({
            "type": map_port_type(interface.port_type),
            "main": 1 if index == 0 else 0,
            "useip": 1,
            "ip": str(interface.addresses[0].address).split("/")[0] if interface.addresses else "",
            "dns": interface.addresses[0].dns_name if interface.addresses else "",
            "port": 161,
            "details": {
                "version": 3
            }
        })
    return result

def dict_interfaces_zb_id(interfaces: list[InterfaceModel],interface_id) -> list[dict]:
    """Converts a list of InterfaceModel objects to a list of dictionaries."""
    result = []
    for index, interface in enumerate(interfaces):
        result.append({
            "type": map_port_type(interface.port_type),
            "interfaceid": interface_id,
            "main": 1 if index == 0 else 0,
            "useip": 1,
            "ip": str(interface.addresses[0].address).split("/")[0] if interface.addresses else "",
            "dns": interface.addresses[0].dns_name if interface.addresses else "",
            "port": 161,
            "details": {
                "version": 3
            }
        })
    return result