"""_summary_
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from app.logger import logger_conf as log
import app.device.service.device_service as device_service
from app.device.models.device_model import Device as device_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.address_model import Address as address_model
from app.device.models.interface_model import Interface as interface_model

def find_differences(nb_device: device_model, zb_device: device_model) -> list[bool, tuple[device_model, device_model], str]:
    differences: tuple[bool, tuple[device_model, device_model], str] = (False, (nb_device, zb_device), "")
    found = False
    fields_to_compare: list[str] = device_model.__annotations__.keys() + address_model.__annotations__.keys() + interface_model.__annotations__.keys()
    for field in fields_to_compare: 
        fields: list[str] = []
        if getattr(nb_device, field) != getattr(zb_device, field):
            found = True
            fields.append(field)
    differences= found, (nb_device, zb_device), fields
    return differences

def compare_devices(nb_device_list: list[device_model], zb_device_list: list[device_model]) -> list[device_difference_model]:
    different_devices: list[device_difference_model] = []
    differences: tuple[bool, tuple[device_model, device_model], str]
    nb_devices: list[device_model] = []
    zb_devices: list[device_model] = []
    found: bool
    for nb_device in nb_device_list:
        found = False
        for zb_device in zb_device_list:
            differences = find_differences(nb_device, zb_device)
            if differences[0]:
                different_devices.append(device_difference_model(nb_device, zb_device, differences[2]))
                found = True
                break
            found = False
        if found:
            nb_devices.append(nb_device)
    for zb_device in zb_device_list:
        found = False
        for nb_device in nb_device_list:
            differences = find_differences(nb_device, zb_device)
            if differences[0]:
                found = True
                break
            found = False
        if found:
            zb_devices.append(zb_device)
    return different_devices, nb_devices, zb_devices
    
def compare(nb_ip, nb_key, zb_ip, zb_key) -> Exception | tuple[list[device_difference_model], list[device_model], list[device_model]]:
    log.logger.info("Starting compare")
    nb_graphql = nb_ip + "/graphql/"
    nb_device_list: list[device_model] | str = device_service.get_nb_devices(nb_key, nb_graphql)
    if isinstance(nb_device_list, str):
        log.logger.error(f"Error: {nb_device_list}")
        return Exception(nb_device_list)
    print("\nNetbox Devices:")
    device_service.print_devices(nb_device_list)
    print("\nZabbix Devices:")
    zb_device_list: list[device_model] | str = device_service.get_zb_devices(zb_key, zb_ip)
    if isinstance(zb_device_list, str):
        log.logger.error(f"Error: {zb_device_list}")
        return Exception(zb_device_list)
    
    device_service.print_devices(zb_device_list)
    different_devices: tuple[list[device_difference_model],list[device_model],list[device_model]] = compare_devices(nb_device_list, zb_device_list)
    log.logger.info("Ending compare")
    return different_devices
    

# compare("https://netbox-test.int.netsystem.cz","22548c0c73603b896d4acfb3aecad1f5128f9d4e","localhost","14a116237840d411e877d16b511eecc00818a3c050470648db9a91d2326e00f5")


