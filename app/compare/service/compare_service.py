"""_summary_
"""
from app.logger import logger_conf as log
import app.device.service.device_service as device_service
from app.device.models.device_model import Device as device_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.address_model import Address as address_model
from app.device.models.interface_model import Interface as interface_model
from app.device.service import device_service as ds

def find_differences(nb_device: device_model, zb_device: device_model) -> tuple[int, tuple[device_model, device_model], tuple[list[str], list[str]]]:
    differences: tuple[bool, tuple[device_model, device_model], str] = (0, (nb_device, zb_device), "")
    found = 0
    fields: list[str] = []
    count = 0
    fields_counter = 0
    same: list[str] = []
    device_fields: list[str] = list(device_model.__annotations__.keys())
    device_fields = [key for key in device_model.__annotations__.keys() if key not in ["hostgroup","description", "status","templates","interfaces"]]
    for field in device_fields:
        nb_value = getattr(nb_device, field)
        zb_value = getattr(zb_device, field)
        if nb_value == "" and zb_value == "":
            continue
        fields_counter += 1
        if nb_value != zb_value:
            found = 1
            if field == "name":
                fields.append(f"{field} ({nb_value} != {zb_value}), Hodnota v netboxu přepíše hodnotu v zabbixu")
            else:
                fields.append(field)
        else:
            count += 1
            same.append(field)
    for nb_interface, zb_interface in zip(nb_device.interfaces, zb_device.interfaces):
        # interface_fields: list[str] = list(interface_model.__annotations__.keys())
        # interface_fields = [key for key in interface_model.__annotations__.keys() if key not in ["name","addresses","mac_address"]]
        # for field in interface_fields:
        #     nb_value = getattr(nb_interface, field)
        #     zb_value = getattr(zb_interface, field)
        #     if field == "port_type":
        #         nb_value = ds.formatPortType(nb_value)
        #         zb_value = ds.formatPortType(zb_value)
        #     if nb_value == "" and zb_value == "":
        #         continue
        #     fields_counter += 1
        #     if nb_value != zb_value:
        #         found = 1
        #         fields.append(f"{field}")
        #     else:
        #         count += 1
        #         same.append(field)
        for nb_address, zb_address in zip(nb_interface.addresses, zb_interface.addresses):
            address_fields: list[str] = list(address_model.__annotations__.keys())
            for field in address_fields:
                nb_value = getattr(nb_address, field)
                zb_value = getattr(zb_address, field)
                if nb_value == "" and zb_value == "":
                    continue
                fields_counter += 1
                if nb_value != zb_value:
                    found = 1
                    if field == "address" or field == "dns_name":
                        fields.append(f"{field} ({nb_value} != {zb_value}), Hodnota v netboxu přepíše hodnotu v zabbixu")
                    else:
                        fields.append(f"{field}")
                else:
                    count += 1
                    same.append(field)
    if count < 1 or len(fields) < 1:
        found = 0
    if len(same) == fields_counter:
        found = 2
    if len(fields) > 0:
        device_fields: list[str] = list(device_model.__annotations__.keys())
        device_fields = [key for key in device_model.__annotations__.keys() if key not in ["hostgroup","description","name","status","interfaces"]]
        for field in device_fields:
            nb_value = getattr(nb_device, field)
            zb_value = getattr(zb_device, field)
            if nb_value == "" and zb_value == "":
                continue
            if nb_value != zb_value:
                fields.append(field)
            else:
                same.append(field)
        for nb_interface, zb_interface in zip(nb_device.interfaces, zb_device.interfaces):
            interface_fields: list[str] = list(interface_model.__annotations__.keys())
            interface_fields = [key for key in interface_model.__annotations__.keys() if key not in ["name","addresses","mac_address"]]
            for field in interface_fields:
                nb_value = getattr(nb_interface, field)
                zb_value = getattr(zb_interface, field)
                if field == "port_type":
                    nb_value = ds.formatPortType(nb_value)
                    zb_value = ds.formatPortType(zb_value)
                if nb_value == "" and zb_value == "":
                    continue
                if nb_value != zb_value:
                    fields.append(f"{field}")
                else:
                    same.append(field)
    log.logger.debug(f"Fields counter: {fields_counter}, same: {len(same)}, different: {len(fields)}")
    log.logger.debug(f"Tag: {found}, {nb_device.name}, {zb_device.name}, {fields}, {same}")
    differences = found, (nb_device, zb_device), (fields, same)
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
            if nb_device == zb_device:
                continue
            differences = find_differences(nb_device, zb_device)
            if differences[0] == 1:
                different_devices.append(device_difference_model(nb_device, zb_device, differences[2]))
                found = True
                break
            elif differences[0] == 2:
                found = True
                break
            found = False
        if not found:
                nb_devices.append(nb_device)
    for zb_device in zb_device_list:
        found = False
        for nb_device in nb_device_list:
            if nb_device == zb_device:
                continue
            differences = find_differences(nb_device, zb_device)
            if differences[0] == 1:
                found = True
                break
            elif differences[0] == 2:
                found = True
                break
            found = False
        if not found:
                zb_devices.append(zb_device)
    return different_devices, nb_devices, zb_devices

def compare(nb_ip, nb_key, zb_ip, zb_key) -> Exception | tuple[list[device_difference_model], list[device_model], list[device_model]]:
    log.logger.info("Starting compare")
    nb_graphql = nb_ip + "/graphql/"
    log.logger.debug(f"Netbox IP: {nb_ip}")
    log.logger.debug(f"Netbox Key: {nb_key}")
    log.logger.debug(f"Zabbix IP: {zb_ip}")
    log.logger.debug(f"Zabbix Key: {zb_key}")
    log.logger.debug(f"Netbox GraphQL: {nb_graphql}")
    nb_device_list: list[device_model] | str = device_service.get_nb_devices(nb_key, nb_graphql)
    if isinstance(nb_device_list, str):
        log.logger.error(f"Error: {nb_device_list}")
        return Exception(nb_device_list)
    log.logger.debug("Netbox Devices:")
    log.logger.debug(device_service.print_devices(nb_device_list))
    zb_device_list: list[device_model] | str = device_service.get_zb_devices(zb_key, zb_ip)
    if isinstance(zb_device_list, str):
        log.logger.error(f"Error: {zb_device_list}")
        return Exception(zb_device_list)
    log.logger.debug("Zabbix Devices:")
    log.logger.debug(device_service.print_devices(zb_device_list))
    ds.mapPortTypeDevices(nb_device_list, zb_device_list)
    different_devices: tuple[list[device_difference_model],list[device_model],list[device_model]] = compare_devices(nb_device_list, zb_device_list)
    log.logger.info("Ending compare")
    return different_devices
