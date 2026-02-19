"""
Model class representing a network interface.
This class encapsulates the properties and behavior of a network interface,
including its name, associated IP addresses, MAC address, and port type.
Attributes:
    name (str): The name of the interface (e.g., "eth0", "GigabitEthernet0/0/1").
    addresses (list[Address]): A list of Address objects associated with this interface.
    mac_address (str): The MAC (Media Access Control) address of the interface.
    port_type (str): The type of port (e.g., "ethernet", "gigabit-ethernet").
Methods:
    __init__: Initializes an Interface instance with the provided parameters.
    __str__: Returns a string representation of the interface.

"""
from app.device.models.address_model import Address as addr

class Interface:
    """
    Represents a network interface with its configuration details.
    This class encapsulates information about a network interface including its name,
    IP addresses, MAC address, and port type.
    Attributes:
        name (str): The name or identifier of the interface (e.g., 'eth0', 'GigabitEthernet0/1').
        addresses (list[addr]): A list of IP addresses assigned to this interface.
        mac_address (str): The MAC (Media Access Control) address of the interface.
        port_type (str): The type of port (e.g., 'ethernet', 'virtual', 'loopback').
    """

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
