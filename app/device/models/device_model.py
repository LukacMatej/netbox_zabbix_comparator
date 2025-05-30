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

    def create_data_zabbix(self) -> dict:
        """Creates a dictionary representation of the device for Zabbix API."""
        return {
            "jsonrpc": "2.0",
            "method": "host.create",
            "params": {
                "host": self.name,
                "groups": [{"name": self.hostgroup}],
                "interfaces": [interface.to_dict() for interface in self.interfaces],
                "description": self.description,
                "templates": [{"name": template} for template in self.templates.split(",") if template],
                "status": 0 if self.status == "Active" else 1
            },
            "auth": None,  # This should be set when calling the API
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
