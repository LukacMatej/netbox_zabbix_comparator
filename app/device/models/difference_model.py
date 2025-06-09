from app.device.models.device_model import Device as DeviceModel

class DeviceDifference:
    def __init__(self, nb_device: DeviceModel, zb_device: DeviceModel, differences: tuple[list[str],list[str]]) -> None:
        """Initializes the DeviceDifference model with Netbox and Zabbix device models and their differences."""
        self.nb_device: DeviceModel = nb_device
        self.zb_device: DeviceModel = zb_device
        self.differences: tuple[list[str],list[str]] = differences # (differennt_fields, same_fields)

    def __str__(self) -> str:
        """Returns a string representation of the DeviceDifference."""
        return f"{self.nb_device} {self.zb_device} {self.differences}" 
        