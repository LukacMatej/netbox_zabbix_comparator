from app.device.models.interface_model import Interface as InterfaceModel

class Device:
    name: str = ""
    interfaces: list[InterfaceModel] = []
    hostgroup: str = ""
    description: str = ""
    templates: str = ""
    status: str = ""
    
    def __init__(self, name, interfaces, hostgroup, description, templates, status):
        self.name = name
        self.interfaces = interfaces
        self.hostgroup = hostgroup
        self.description = description
        self.templates = templates
        self.status = status
        
    
    def __str__(self):
        return f"{self.name} {self.interfaces} {self.hostgroup} {self.description} {self.templates} {self.status}"
