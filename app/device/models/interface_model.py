from app.device.models.address_model import Address as addr

class Interface:
    name: str = ""
    addresses: list[addr] = []
    mac_address: str = ""
    
    def __init__(self, name, addresses, mac_address) -> None:
        self.name = name
        self.addresses = addresses
        self.mac_address = mac_address
    
    def __str__(self) -> str:
        return f"{self.name} {self.addresses} {self.mac_address}"
    
    def to_dict(self) -> dict:
        """Creates a dictionary representation of the interface."""
        return {
            "name": self.name,
            "mac_address": self.mac_address,
            "addresses": [address.to_dict() for address in self.addresses]
        }
