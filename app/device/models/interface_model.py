from app.device.models.address_model import Address as addr

class Interface:
    name: str = ""
    addresses: list[addr] = []
    mac_address: str = ""
    port_type: str = ""
    
    def __init__(self, name, addresses, mac_address, port_type) -> None:
        self.name = name
        self.addresses = addresses
        self.mac_address = mac_address
        self.port_type = port_type
    
    def __str__(self) -> str:
        return f"{self.name} {self.addresses} {self.mac_address} {self.port_type}"

