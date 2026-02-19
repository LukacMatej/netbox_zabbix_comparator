"""
Represents a network address with its associated DNS name.
This class encapsulates an IP address and its corresponding DNS hostname,
providing methods for string representation and dictionary conversion.
Attributes:
    address (str): The IP address.
    dns_name (str): The DNS name associated with the address.

"""
class Address:
    """
    Represents a network address with its associated DNS name.
    Attributes:
        address (str): The IP address.
        dns_name (str): The DNS name associated with the address.
    """

    address: str
    dns_name: str

    def __init__(self, address: str, dns_name: str) -> None:
        self.address = address
        self.dns_name = dns_name

    def __str__(self) -> str:
        return f"{self.address} {self.dns_name}"

    def to_dict(self) -> dict:
        """Creates a dictionary representation of the address."""
        return {
            "address": self.address,
            "dns_name": self.dns_name
        }
