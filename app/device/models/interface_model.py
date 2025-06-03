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
        result = []
        for index,addr in enumerate(self.addresses):
            result.append({
                "type": 2,
                "main": 1 if index == 0 else 0,
                "useip": 1,
                "ip": addr.address,
                "dns": addr.dns_name,
                "port": 161,
                "details": {
                    "version": 3
                }
            })
        return result
