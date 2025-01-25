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

def normalize_status(status: str) -> str:
    if status == 0 or status == "Active" or status == "0":
        return "Active"
    return "Inactive"
