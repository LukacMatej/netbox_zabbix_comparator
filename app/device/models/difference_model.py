"""
Module for comparing and representing differences between device models from Netbox and Zabbix.
This module provides the DeviceDifference class which encapsulates the comparison results
between two device instances, tracking which fields differ and which fields are identical.

"""

from app.device.models.device_model import Device as DeviceModel


class DeviceDifference:
    """
    A model representing the differences between a Netbox device and a Zabbix device.
    This class encapsulates comparison data between two device models, storing references
    to both the Netbox and Zabbix device instances along with their divergent and matching fields.
    Attributes:
        nb_device (DeviceModel): The device model from Netbox.
        zb_device (DeviceModel): The device model from Zabbix.
        differences (tuple[list[str], list[str]]): A tuple containing two lists:
            - First list: Field names that differ between the two devices.
            - Second list: Field names that are identical between the two devices.
    """

    def __init__(
        self,
        nb_device: DeviceModel,
        zb_device: DeviceModel,
        differences: tuple[list[str], list[str]],
    ) -> None:
        """Initialize DeviceDifference with NetBox/Zabbix models and diff fields."""
        self.nb_device: DeviceModel = nb_device
        self.zb_device: DeviceModel = zb_device
        self.differences: tuple[list[str], list[str]] = (
            differences  # (differennt_fields, same_fields)
        )

    def __str__(self) -> str:
        """Returns a string representation of the DeviceDifference."""
        return f"{self.nb_device} {self.zb_device} {self.differences}"

    def __repr__(self) -> str:
        """Returns a detailed string representation of the DeviceDifference."""
        return (
            f"DeviceDifference(nb_device={self.nb_device}, "
            f"zb_device={self.zb_device}, differences={self.differences})"
        )

    def get_nb_devices(self) -> DeviceModel:
        """Returns the NetBox device model."""
        return self.nb_device

    def get_zb_devices(self) -> DeviceModel:
        """Returns the Zabbix device model."""
        return self.zb_device
