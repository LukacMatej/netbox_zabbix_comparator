from dataclasses import dataclass

@dataclass
class Device:
    name: str = ""
    address: str = ""
    interface: str = ""
    hostgroup: str = ""
    description: str = ""
    dns_name: str = ""
    templates: str = ""
    status: str = ""
    