"""
Module for synchronization output data management between Netbox and Zabbix systems.
This module provides the SyncOutput class which serves as a data model for tracking
and storing synchronization operations between Netbox and Zabbix systems. It maintains
separate logs for differences detected, Netbox operation outputs, and Zabbix operation
outputs.
Classes:
    SyncOutput: A model class for managing synchronization output data.

"""


class SyncOutput:
    """
    A model class for managing and storing synchronization output data
    between Netbox and Zabbix systems.
    This class tracks three types of outputs during synchronization operations:
    - Differences detected between systems
    - Outputs from Netbox operations
    - Outputs from Zabbix operations
    Attributes:
        synchronization_output_differences (list[str]):
            List of differences found during synchronization.
        synchronization_output_netbox (list[str]):
            List of outputs from Netbox operations.
        synchronization_output_zabbix (list[str]):
            List of outputs from Zabbix operations.
    Methods:
        add_difference_output(difference: str):
            Appends a difference message to the differences list.
        add_netbox_output(output: str):
            Appends a Netbox output message to the Netbox outputs list.
        add_zabbix_output(output: str):
            Appends a Zabbix output message to the Zabbix outputs list.
        __str__(): Returns a formatted string representation of all synchronization outputs.
    """

    def __init__(
        self,
        synchronization_output_differences: list[str] = None,
        synchronization_output_netbox: list[str] = None,
        synchronization_output_zabbix: list[str] = None,
    ) -> None:
        """Initialize optional lists for differences, NetBox, and Zabbix outputs."""
        self.synchronization_output_differences: list[str] = (
            synchronization_output_differences
            if synchronization_output_differences is not None
            else []
        )
        self.synchronization_output_netbox: list[str] = (
            synchronization_output_netbox
            if synchronization_output_netbox is not None
            else []
        )
        self.synchronization_output_zabbix: list[str] = (
            synchronization_output_zabbix if synchronization_output_zabbix is not None else []
        )

    def add_difference_output(self, difference: str):
        """Adds a difference to the synchronization output."""
        self.synchronization_output_differences.append(difference)

    def add_netbox_output(self, output: str):
        """Adds a Netbox output to the synchronization output."""
        self.synchronization_output_netbox.append(output)

    def add_zabbix_output(self, output: str):
        """Adds a Zabbix output to the synchronization output."""
        self.synchronization_output_zabbix.append(output)

    def __str__(self):
        """Returns a string representation of the synchronization output."""
        return (
            f"Synchronization Output Differences: {self.synchronization_output_differences}\n"
            f"Netbox Outputs: {self.synchronization_output_netbox}\n"
            f"Zabbix Outputs: {self.synchronization_output_zabbix}"
        )
