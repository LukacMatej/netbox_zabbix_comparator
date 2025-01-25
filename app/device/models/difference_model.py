from app.device.models.device_model import Device as DeviceModel
from app.device.service import device_service as ds


class DeviceDifference:
    def __init__(self, nb_device: DeviceModel, zb_device: DeviceModel, differences: tuple[list[str],list[str]]) -> None:
        self.nb_device: DeviceModel = nb_device
        self.zb_device: DeviceModel = zb_device
        self.differences: tuple[list[str],list[str]] = differences

    def __str__(self) -> str:
        return f"{self.nb_device} {self.zb_device} {self.differences}"

    def print_differences(self) -> str:
        txt_builder: str = ""
        txt_builder += f"Netbox device: {ds.print_device(self.nb_device)}\n"
        txt_builder += f"Zabbix device: {ds.print_device(self.zb_device.name)}\n"
        txt_builder += "Differences:\n"
        for difference in self.differences[0]:
            txt_builder += f"  {difference}\n"
        txt_builder += "Similarities:\n"
        for similarity in self.differences[1]:
            txt_builder += f"  {similarity}\n"
        return txt_builder