from app.device.models.device_model import Device as DeviceModel

class DeviceDifference:
    def __init__(self, nb_device: DeviceModel, zb_device: DeviceModel, differences: tuple[list[str],list[str]]) -> None:
        self.nb_device: DeviceModel = nb_device
        self.zb_device: DeviceModel = zb_device
        self.differences: tuple[list[str],list[str]] = differences

    def __str__(self) -> str:
        return f"{self.nb_device} {self.zb_device} {self.differences}"
