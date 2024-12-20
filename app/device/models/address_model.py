class Address:
    address: str
    dns_name: str
    
    def __init__(self, address: str, dns_name: str) -> None:
        self.address = address
        self.dns_name = dns_name
    
    def __str__(self) -> str:
        return f"{self.address} {self.dns_name}"