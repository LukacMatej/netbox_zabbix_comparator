from app.device.models.interface_model import Interface as InterfaceModel
from app.device.service import device_service as ds

class Device:
    name: str = ""
    interfaces: list[InterfaceModel] = []
    hostgroup: str = ""
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

    def create_data_zabbix(self, hostgroupId, templateids) -> dict:
        """Creates a dictionary representation of the device for Zabbix API."""
        return {
            "jsonrpc": "2.0",
            "method": "host.create",
            "params": {
                "host": self.name,
                "interfaces": dict_interfaces_zb(self.interfaces),
                "groups": [{"groupid": hostgroupId}],
                "description": self.description,
                "templates": [{"templateid": tempId} for tempId in templateids if tempId],
                "status": 0 if self.status == "Active" else 1,
                "inventory_mode": 0,
                "inventory": {
                    "macaddress_a": self.interfaces[0].mac_address if self.interfaces else "",
                    "macaddress_b": self.interfaces[1].mac_address if len(self.interfaces) > 1 else "",
                }
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

def normalize_status(status: str) -> str:
    if status == 0 or status == "Active" or status == "0":
        return "Active"
    return "Inactive"

def dict_interfaces_zb(interfaces: list[InterfaceModel]) -> list[dict]:
    """Converts a list of InterfaceModel objects to a list of dictionaries."""
    result = []
    for index, interface in enumerate(interfaces):
        result.append({
            "type": 2,
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