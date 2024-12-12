from app.device.models.device_model import device_model as device_model

class DeviceDifference:
    def __init__(self, nb_device: device_model, zb_device: device_model):
        self.nb_device: device_model = nb_device
        self.zb_device: device_model = zb_device
        self.differences: list[str] = []

    def __str__(self):
        return f"{self.nb_device} {self.zb_device} {self.differences}"
