from app.device.models.address_model import Address as addr

class Interface:
    name: str = ""
    addresses: list[addr] = []
    mac_address: str = ""
    
    def __init__(self, name, addresses, mac_address):
        self.name = name
        self.addresses = addresses
        self.mac_address = mac_address
    
    def __str__(self):
        return f"{self.name} {self.addresses} {self.mac_address}"
