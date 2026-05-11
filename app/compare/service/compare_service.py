"""
Compare two lists of device models and identify devices with differences.
    nb_device_list (list[device_model]): List of device models from NetBox.
    zb_device_list (list[device_model]): List of device models from Zabbix.
    tuple[list[device_difference_model], list[device_model], list[device_model]]:
        - list[device_difference_model]: Devices found in both NetBox and Zabbix
                                         with differences between them.
        - list[device_model]: Devices found only in NetBox (no match in Zabbix).
        - list[device_model]: Devices found only in Zabbix (no match in NetBox).
Compare devices from NetBox and Zabbix sources using their connection parameters.
    nb_ip (str): NetBox server IP address or hostname.
    nb_key (str): NetBox API authentication key.
    zb_ip (str): Zabbix server IP address or hostname.
    zb_key (str): Zabbix API authentication key.
    Exception | tuple[list[device_difference_model], list[device_model], list[device_model]]:
        On success, returns a tuple containing:
        - list[device_difference_model]: Devices with differences between NetBox and Zabbix.
        - list[device_model]: Devices found only in NetBox.
        - list[device_model]: Devices found only in Zabbix.
        On error, returns an Exception object with error message details.
"""

from __future__ import annotations

from app.logger import logger_conf as log
from app.device.service import device_service as ds
from app.device.models.device_model import Device as device_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.address_model import Address as address_model
from app.device.models.interface_model import Interface as interface_model
import re


def normalize_name(name: str) -> str:
    """Normalize device names for matching.

    Lowercase, replace common long words with short forms (e.g. "switch" -> "sw"),
    then remove non-alphanumeric characters so "Switch 1" -> "sw1" and "Sw1" -> "sw1".
    """
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = s.replace("switch", "sw").replace("router", "r")
    s = re.sub(r"[^a-z0-9]", "", s)
    return s

def check_device_model(nb_device: device_model, zb_device: device_model, device_fields: list[str]) -> tuple[bool, str | None]:
    """
    Check if two device models are identical based on specified fields.
    Args:
        nb_device (device_model): Device model from NetBox.
        zb_device (device_model): Device model from Zabbix.
        device_fields (list[str]): List of field names to compare between devices.
    Returns:
        tuple[bool, str | None]: A tuple containing a boolean indicating if the devices are identical and a string with the name of the differing field or None if they are identical.
    """
    for field in device_fields:
        nb_value = getattr(nb_device, field)
        zb_value = getattr(zb_device, field)
        if nb_value != zb_value:
            return False, field, nb_value, zb_value
    return True, None , None, None

def find_differences(
    nb_device: device_model, zb_device: device_model
) -> tuple[int, tuple[device_model, device_model], tuple[list[str], list[str]]]:
    """
    Compare two device models and identify differences between them.
    Args:
        nb_device (device_model): Device model from NetBox.
        zb_device (device_model): Device model from Zabbix.
    Returns:
        tuple[int, tuple[device_model, device_model], tuple[list[str], list[str]]]:
            A tuple containing:
            - int: Status code (0 = differences found, 1 = no differences,
                    2 = all fields are identical)
            - tuple of two device_model: (nb_device, zb_device)
            - tuple of two lists: (differences, similarities)
              - differences: List of field names/descriptions that differ between devices.
                            Critical fields (name, address, dns_name) include detailed
                            comparison info and note that NetBox value overwrites Zabbix.
              - similarities: List of field names that are identical between devices.
    """
    differences: tuple[int, tuple[device_model, device_model], tuple[list[str], list[str]]] = (
        0,
        (nb_device, zb_device),
        ([], []),
    )
    found = 0
    fields: list[str] = []
    count = 0
    fields_counter = 0
    same: list[str] = []
    device_fields: list[str] = list(device_model.__annotations__.keys())
    #name, interfaces, hostgroup, description, templates, status
    device_fields = [
        key
        for key in device_model.__annotations__.keys()
        if key not in ["hostgroup", "description", "status", "templates", "interfaces"]
    ]
    for field in device_fields:
        nb_value = getattr(nb_device, field)
        zb_value = getattr(zb_device, field)
        if nb_value == "" and zb_value == "":
            continue
        fields_counter += 1
        if nb_value != zb_value:
            found = 1
            if field == "name":
                fields.append(
                            f"{field} ({nb_value} != {zb_value}), "
                            "Hodnota v netboxu přepíše hodnotu v zabbixu"
                )
            else:
                fields.append(field)
        else:
            count += 1
            same.append(field)
    for nb_interface, zb_interface in zip(nb_device.interfaces, zb_device.interfaces):
        # interface_fields: list[str] = list(interface_model.__annotations__.keys())
        # interface_fields = [
        #   key for key in interface_model.__annotations__.keys()
        #   if key not in ["name", "addresses", "mac_address"]
        # ]
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
                    if field in ("address", "dns_name"):
                        fields.append(
                            f"{field} ({nb_value} != {zb_value}), "
                            "Hodnota v netboxu přepíše hodnotu v zabbixu"
                        )
                    else:
                        fields.append(f"{field}")
                else:
                    count += 1
                    same.append(field)
    if count < 1 or len(fields) < 1:
        found = 0
    if len(same) == fields_counter:
        check_device_model_result: tuple[bool, str | None, str | None, str | None]
        check_device_model_result = check_device_model(nb_device, zb_device, device_fields)
        if check_device_model_result[0]:
            found = 2
        else:
            found = 1
            fields.append(
                f"{check_device_model_result[1]} ({check_device_model_result[2]} != {check_device_model_result[3]}), "
                "Hodnota v netboxu přepíše hodnotu v zabbixu"
            )
    if len(fields) > 0:
        device_fields: list[str] = list(device_model.__annotations__.keys())
        device_fields = [
            key
            for key in device_model.__annotations__.keys()
            if key not in ["description", "name", "interfaces"]
        ]
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
            interface_fields = [
                key
                for key in interface_model.__annotations__.keys()
                if key not in ["name", "addresses", "mac_address"]
            ]
            for field in interface_fields:
                nb_value = getattr(nb_interface, field)
                zb_value = getattr(zb_interface, field)
                if field == "port_type":
                    nb_value = ds.format_port_type(nb_value)
                    zb_value = ds.format_port_type(zb_value)
                if nb_value == "" and zb_value == "":
                    continue
                if nb_value != zb_value:
                    fields.append(f"{field}")
                else:
                    same.append(field)
    log.logger.debug(
        "Fields counter: %s, same: %s, different: %s", fields_counter, len(same), len(fields)
    )
    log.logger.debug("Tag: %s, %s, %s, %s, %s", found, nb_device.name, zb_device.name, fields, same)
    differences = found, (nb_device, zb_device), (fields, same)
    return differences


def compare_devices(
    nb_device_list: list[device_model], zb_device_list: list[device_model]
) -> tuple[list[device_difference_model], list[device_model], list[device_model]]:
    """
    Compare devices from two sources (NetBox and Zabbix) and identify differences.
    This function compares devices from a NetBox device list against a Zabbix device list.
    It identifies devices with differences, devices only in NetBox, and devices only in Zabbix.
    Args:
        nb_device_list (list[device_model]): List of devices from NetBox.
        zb_device_list (list[device_model]): List of devices from Zabbix.
    Returns:
        tuple: A tuple containing three elements:
                        - list[device_difference_model]: List of devices with detected
                            differences between sources.
                        - list[device_model]: List of devices found only in NetBox
                            (not matched in Zabbix).
                        - list[device_model]: List of devices found only in Zabbix
                            (not matched in NetBox).
    Note:
        The function uses find_differences() to detect differences between device pairs.
        Return code 1 indicates differences found, code 2 indicates exact match or exclusion.
    """

    different_devices: list[device_difference_model] = []
    nb_devices: list[device_model] = []
    zb_devices: list[device_model] = []

    # Build normalized-name -> [devices] maps for both sources. This avoids
    # matching by incidental similarity (templates/port types) and allows
    # explicit name-based pairing (including fuzzy normalization like
    # "Switch 1" -> "sw1").
    nb_map: dict[str, list[device_model]] = {}
    zb_map: dict[str, list[device_model]] = {}
    for d in nb_device_list:
        key = normalize_name(getattr(d, "name", ""))
        nb_map.setdefault(key, []).append(d)
    for d in zb_device_list:
        key = normalize_name(getattr(d, "name", ""))
        zb_map.setdefault(key, []).append(d)

    all_keys = set(nb_map.keys()) | set(zb_map.keys())
    for key in all_keys:
        nbl = nb_map.get(key, [])
        zbl = zb_map.get(key, [])

        # If both sides have devices with the same normalized key, pair them
        # by simple deterministic ordering and compare each pair deeply.
        if nbl and zbl:
            nbl_sorted = sorted(nbl, key=lambda d: d.name.lower())
            zbl_sorted = sorted(zbl, key=lambda d: d.name.lower())
            for nb_dev, zb_dev in zip(nbl_sorted, zbl_sorted):
                differences = find_differences(nb_dev, zb_dev)
                if differences[0] == 1:
                    different_devices.append(
                        device_difference_model(nb_dev, zb_dev, differences[2])
                    )
            # Any leftovers on either side are unmatched
            if len(nbl_sorted) > len(zbl_sorted):
                nb_devices.extend(nbl_sorted[len(zbl_sorted) :])
            if len(zbl_sorted) > len(nbl_sorted):
                zb_devices.extend(zbl_sorted[len(nbl_sorted) :])
        else:
            # Only in NetBox
            if nbl and not zbl:
                nb_devices.extend(nbl)
            # Only in Zabbix
            if zbl and not nbl:
                zb_devices.extend(zbl)

    return different_devices, nb_devices, zb_devices


def compare(
    nb_ip, nb_key, zb_ip, zb_key
) -> Exception | tuple[list[device_difference_model], list[device_model], list[device_model]]:
    """
    Compare devices between Netbox and Zabbix systems.
    Retrieves device lists from both Netbox and Zabbix, maps port types,
    and compares the devices to identify differences.
    Args:
        nb_ip (str): IP address or hostname of the Netbox server.
        nb_key (str): API key for Netbox authentication.
        zb_ip (str): IP address or hostname of the Zabbix server.
        zb_key (str): API key for Zabbix authentication.
    Returns:
        Exception | tuple[list[device_difference_model], list[device_model], list[device_model]]:
            On success, returns a tuple containing:
                - List of device differences between Netbox and Zabbix
                - List of devices in Netbox only
                - List of devices in Zabbix only
            On error, returns an Exception object with error message.
    Raises:
        Exception: If device retrieval from Netbox or Zabbix fails.
    """
    log.logger.info("Starting compare")
    nb_graphql = nb_ip + "/graphql/"
    log.logger.debug("Netbox IP: %s", nb_ip)
    log.logger.debug("Netbox Key: %s", nb_key)
    log.logger.debug("Zabbix IP: %s", zb_ip)
    log.logger.debug("Zabbix Key: %s", zb_key)
    log.logger.debug("Netbox GraphQL: %s", nb_graphql)
    nb_device_list: list[device_model] | str = ds.get_nb_devices(nb_key, nb_graphql)
    if isinstance(nb_device_list, str):
        log.logger.error("Error: %s", nb_device_list)
        return Exception(nb_device_list)
    log.logger.debug("Netbox Devices:")
    log.logger.debug(ds.print_devices(nb_device_list))
    zb_device_list: list[device_model] | str = ds.get_zb_devices(zb_key, zb_ip)
    if isinstance(zb_device_list, str):
        log.logger.error("Error: %s", zb_device_list)
        return Exception(zb_device_list)
    log.logger.debug("Zabbix Devices:")
    log.logger.debug(ds.print_devices(zb_device_list))
    ds.map_port_type_device(nb_device_list, zb_device_list)
    different_devices: tuple[
        list[device_difference_model], list[device_model], list[device_model]
    ] = compare_devices(nb_device_list, zb_device_list)
    log.logger.info("Ending compare")
    return different_devices
