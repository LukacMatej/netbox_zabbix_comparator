from app.device.models.device_model import Device as DeviceModel

class DeviceDifference:
    def __init__(self, nb_device: DeviceModel, zb_device: DeviceModel, differences: list[str]):
        self.nb_device: DeviceModel = nb_device
        self.zb_device: DeviceModel = zb_device
        self.differences: list[str] = []

    def __str__(self):
        return f"{self.nb_device} {self.zb_device} {self.differences}"
