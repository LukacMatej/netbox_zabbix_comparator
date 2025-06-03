from app.device.models.interface_model import Interface as InterfaceModel

class Device:
    name: str = ""
    interfaces: list[InterfaceModel] = []
    hostgroup: str = ""
    description: str = ""
    templates: str = ""
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
                "interfaces": dict_interfaces(self.interfaces),
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
            "device_type": self.hostgroup,
            "device_role": self.description,
            "status": self.status,
            "custom_fields": {
                "templates": self.templates
            },
            "interfaces": [interface.to_dict() for interface in self.interfaces]
        }

def normalize_status(status: str) -> str:
    if status == 0 or status == "Active" or status == "0":
        return "Active"
    return "Inactive"

def dict_interfaces(interfaces: list[InterfaceModel]) -> list[dict]:
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