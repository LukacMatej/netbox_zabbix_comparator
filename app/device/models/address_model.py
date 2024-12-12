class Address:
    address: str
    dns_name: str
    def __init__(self, address: str, dns_name: str):
        self.address = address
        self.dns_name = dns_name
    
    def __str__(self):
        return f"{self.address} {self.dns_name}"