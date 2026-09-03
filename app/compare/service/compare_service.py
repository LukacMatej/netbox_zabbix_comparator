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

import re

from scipy.optimize import linear_sum_assignment

from app.logger import logger_conf as log
from app.device.service import device_service as ds
from app.device.models.device_model import Device as device_model
from app.device.models.interface_model import Interface as interface_model
from app.device.models.difference_model import DeviceDifference as device_difference_model
from app.device.models.address_model import Address as address_model


def normalize_name(name: str) -> str:
    """Normalize device names for matching.

    Converts to lowercase and removes all non-alphanumeric characters.
    Examples:
        "Router-01" -> "router01"
        "Switch 1" -> "switch1"
        "ESX1-CIMC" -> "esx1cimc"
    """
    if not isinstance(name, str):
        return ""
    # Convert to lowercase and keep only alphanumeric characters
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_base_name(name: str) -> str:
    """Extract the base name before the first dash or dot.

    For example:
    - "esx1" -> "esx1"
    - "esx1-cimc" -> "esx1"
    - "esx1-cimc.netsystem.local" -> "esx1"

    This is useful for matching related devices like a server and its management interface.
    """
    if not isinstance(name, str):
        return ""
    # Split on dash or dot and take the first part
    base = name.split("-")[0].split(".")[0]
    return normalize_name(base)


def _primary_ip_dns(device: device_model) -> tuple[str, str]:
    """Return the primary IP and DNS name for a device if available.

    Uses the first interface and its first address when present. IPs are
    returned without CIDR suffix.
    """
    try:
        if device.interfaces and device.interfaces[0].addresses:
            addr = device.interfaces[0].addresses[0]
            ip = str(getattr(addr, "address", ""))
            ip = ip.split("/", 1)[0] if ip else ""
            dns = str(getattr(addr, "dns_name", ""))
            return ip, dns
    except (AttributeError, IndexError, TypeError):
        pass
    return "", ""

def _normalize_hostgroups(hostgroups) -> list[str]:
    """Normalize hostgroups for comparison.

    Converts Zabbix format (list of dicts with 'name' key) to simple list of names.
    """
    if not hostgroups:
        return []
    if isinstance(hostgroups, list):
        normalized = []
        for item in hostgroups:
            if isinstance(item, dict) and "name" in item:
                normalized.append(item["name"])
            elif isinstance(item, str):
                normalized.append(item)
        return sorted(normalized)
    return []


def check_device_model(
    nb_device: device_model,
    zb_device: device_model,
    device_fields: list[str],
) -> tuple[bool, str | None, list[str] | None, list[str] | None]:
    """
    Check if two device models are identical based on specified fields.
    Args:
        nb_device (device_model): Device model from NetBox.
        zb_device (device_model): Device model from Zabbix.
        device_fields (list[str]): List of field names to compare between devices.
    Returns:
        tuple[bool, str | None, list[str] | None, list[str] | None]: A tuple containing a boolean indicating if the
            devices are identical and strings with the name of the differing
            field and their values or None if they are identical.
    """
    for field in device_fields:
        nb_value = getattr(nb_device, field)
        zb_value = getattr(zb_device, field)

        # Special handling for hostgroups: normalize both formats
        compare_value = zb_value
        if field == "hostgroup":
            nb_value = _normalize_hostgroups(nb_value)
            compare_value = _normalize_hostgroups(zb_value)

        if nb_value != compare_value:
            return False, field, nb_value, compare_value
    return True, None, None, None


def _compare_device_fields(
    nb_device: device_model,
    zb_device: device_model,
    exclude: list[str],
) -> tuple[list[str], list[str], int, int]:
    """Compare top-level device fields except those in exclude.

    Returns (differences, same, fields_counter, same_count)
    """
    diffs: list[str] = []
    same: list[str] = []
    fields_counter = 0
    same_count = 0
    device_fields = [
        key
        for key in device_model.__annotations__.keys()
        if key not in exclude
    ]
    for field in device_fields:
        nb_value = getattr(nb_device, field)
        zb_value = getattr(zb_device, field)
        if nb_value == "" and zb_value == "":
            continue
        fields_counter += 1

        # Special handling for hostgroups: normalize both formats
        compare_value = zb_value
        if field == "hostgroup":
            nb_value = _normalize_hostgroups(nb_value)
            compare_value = _normalize_hostgroups(zb_value)

        if nb_value != compare_value:
            if field == "name":
                msg = f"{field} ({nb_value} != {compare_value}), "
                msg += "Field in Netbox will overwrite value in Zabbix"
                diffs.append(msg)
            else:
                diffs.append(field)
        else:
            same_count += 1
            same.append(field)
    return diffs, same, fields_counter, same_count


def _compare_address_fields(
    nb_device: device_model,
    zb_device: device_model,
) -> tuple[list[str], list[str], int, int]:
    """Compare address fields across interfaces and addresses using zips.

    Returns (differences, same, fields_counter, same_count)
    """
    diffs: list[str] = []
    same: list[str] = []
    fields_counter = 0
    same_count = 0
    for nb_interface, zb_interface in zip(nb_device.interfaces, zb_device.interfaces):
        for nb_address, zb_address in zip(nb_interface.addresses, zb_interface.addresses):
            address_fields: list[str] = list(address_model.__annotations__.keys())
            for field in address_fields:
                nb_value = getattr(nb_address, field)
                zb_value = getattr(zb_address, field)
                if nb_value == "" and zb_value == "":
                    continue
                fields_counter += 1
                if nb_value != zb_value:
                    if field in ("address", "dns_name"):
                        msg = f"{field} ({nb_value} != {zb_value}), "
                        msg += "Field in Netbox will overwrite value in Zabbix"
                        diffs.append(msg)
                    else:
                        diffs.append(f"{field}")
                else:
                    same_count += 1
                    same.append(field)
    return diffs, same, fields_counter, same_count

def _compare_interface_fields(
    nb_device: device_model,
    zb_device: device_model,
) -> tuple[list[str], list[str], int, int]:
    """Compare interface fields by matching interfaces with same port_type.

    Tries to match interfaces by port_type first. Compares matched interfaces,
    and reports unmatched ones as differences.

    Returns (differences, same, fields_counter, same_count)
    """
    diffs: list[str] = []
    same: list[str] = []
    fields_counter = 0
    same_count = 0
    interface_fields = ["port_type"]

    nb_interfaces: list[interface_model] = nb_device.interfaces or []
    zb_interfaces: list[interface_model] = zb_device.interfaces or []

    # Build dictionaries mapping port_type to list of interfaces
    nb_by_port: dict[str, list[interface_model]] = {}
    for iface in nb_interfaces:
        port_type = getattr(iface, "port_type", "")
        if port_type:
            if port_type not in nb_by_port:
                nb_by_port[port_type] = []
            nb_by_port[port_type].append(iface)

    zb_by_port: dict[str, list[interface_model]] = {}
    for iface in zb_interfaces:
        port_type = getattr(iface, "port_type", "")
        if port_type:
            if port_type not in zb_by_port:
                zb_by_port[port_type] = []
            zb_by_port[port_type].append(iface)

    # Find all unique port types
    all_port_types = set(nb_by_port.keys()) | set(zb_by_port.keys())

    # Compare interfaces for each port type
    for port_type in sorted(all_port_types):
        nb_list = nb_by_port.get(port_type, [])
        zb_list = zb_by_port.get(port_type, [])

        # Match up interfaces with same port_type
        for i in range(max(len(nb_list), len(zb_list))):
            if i < len(nb_list) and i < len(zb_list):
                # Both have an interface at this position
                nb_iface = nb_list[i]
                zb_iface = zb_list[i]

                for field in interface_fields:
                    nb_value = getattr(nb_iface, field, "")
                    zb_value = getattr(zb_iface, field, "")
                    if nb_value == "" and zb_value == "":
                        continue
                    fields_counter += 1
                    if nb_value != zb_value:
                        msg = f"{field} ({nb_value} != {zb_value}), "
                        msg += "Field in Netbox will overwrite value in Zabbix"
                        diffs.append(msg)
                    else:
                        same_count += 1
                        same.append(field)
            elif i < len(nb_list):
                # Only NetBox has this interface
                fields_counter += 1
                diffs.append(
                    f"Interface with port_type '{port_type}' missing in Zabbix"
                )
            else:
                # Only Zabbix has this interface
                fields_counter += 1
                diffs.append(
                    f"Interface with port_type '{port_type}' extra in Zabbix"
                )

    return diffs, same, fields_counter, same_count

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

    # Compare top-level device fields (excluding some heavy/irrelevant ones)
    diffs, same, fields_counter, same_count = _compare_device_fields(
        nb_device,
        zb_device,
        exclude=["description", "status", "interfaces"],
    )

    # Compare address fields nested in interfaces
    addr_diffs, addr_same, addr_counter, addr_same_count = _compare_address_fields(
        nb_device, zb_device
    )
    diffs.extend(addr_diffs)
    same.extend(addr_same)
    fields_counter += addr_counter
    same_count += addr_same_count

    # Compare interface fields (port_type, mac_address, etc.)
    iface_diffs, iface_same, iface_counter, iface_same_count = _compare_interface_fields(
        nb_device, zb_device
    )
    diffs.extend(iface_diffs)
    same.extend(iface_same)
    fields_counter += iface_counter
    same_count += iface_same_count

    found = 1 if diffs else 0

    # If no address/device field comparisons were done, ensure we don't falsely
    # mark as unmatched
    if same_count < 1 or len(diffs) < 1:
        found = 0

    # If all compared fields were the same, use check_device_model as final check
    if len(same) == fields_counter and fields_counter > 0:
        check_device_model_result = check_device_model(nb_device, zb_device, [
            key
            for key in device_model.__annotations__.keys()
            if key not in ["hostgroup", "description", "status", "templates", "interfaces"]
        ])
        if check_device_model_result[0]:
            found = 2
        else:
            found = 1
            msg = f"{check_device_model_result[1]} ({check_device_model_result[2]} "
            msg += f"!= {check_device_model_result[3]}), "
            msg += "Field in Netbox will overwrite value in Zabbix"
            diffs.append(msg)

    # No secondary pass: matching occurs before calling this function, so a
    # single-pass comparison of device and address fields is sufficient.
    log.logger.debug(
        "Fields counter: %s, same: %s, different: %s", fields_counter, len(same), len(diffs)
    )
    log.logger.debug(
        "Tag: %s, %s, %s, %s, %s", found, nb_device.name, zb_device.name, diffs, same
    )
    differences = found, (nb_device, zb_device), (diffs, same)
    return differences


def _calculate_match_score(nb_dev: device_model, zb_dev: device_model) -> float:
    """Calculate a match score between two devices (0.0 to 1.0).

    Prioritizes exact matches for IP, DNS, and name in that order.
    Higher score means better match.
    """
    score = 0.0

    nb_ip, nb_dns = _primary_ip_dns(nb_dev)
    zb_ip, zb_dns = _primary_ip_dns(zb_dev)
    nb_name = normalize_name(getattr(nb_dev, "name", ""))
    zb_name = normalize_name(getattr(zb_dev, "name", ""))

    # Priority 1: IP address match (strongest signal)
    if nb_ip and zb_ip and nb_ip == zb_ip:
        score += 0.6
        log.logger.debug(
            "IP match: %s (%s) == %s (%s)",
            getattr(nb_dev, "name", ""), nb_ip,
            getattr(zb_dev, "name", ""), zb_ip
        )

    # Priority 2: DNS name match
    if nb_dns and zb_dns and nb_dns == zb_dns:
        score += 0.5
        log.logger.debug(
            "DNS match: %s (%s) == %s (%s)",
            getattr(nb_dev, "name", ""), nb_dns,
            getattr(zb_dev, "name", ""), zb_dns
        )

    # Priority 3: Device name matching (multiple strategies)
    if nb_name and zb_name:
        # Exact normalized name match
        if nb_name == zb_name:
            score += 0.55
            log.logger.debug(
                "Name exact match: %s == %s",
                getattr(nb_dev, "name", ""), getattr(zb_dev, "name", "")
            )
        else:
            # Base name match (e.g., "esx1" in "esx1-cimc.netsystem.local")
            nb_base = get_base_name(getattr(nb_dev, "name", ""))
            zb_base = get_base_name(getattr(zb_dev, "name", ""))
            if nb_base and zb_base and nb_base == zb_base and len(nb_base) > 2:
                score += 0.35
                log.logger.debug(
                    "Base name match: %s (%s) == %s (%s)",
                    getattr(nb_dev, "name", ""), nb_base,
                    getattr(zb_dev, "name", ""), zb_base
                )
            else:
                # Substring match (shorter name is part of longer)
                shorter = min(nb_name, zb_name, key=len)
                longer = max(nb_name, zb_name, key=len)
                if shorter and shorter in longer and len(shorter) > 2:
                    score += 0.2

    return min(score, 1.0)  # Cap at 1.0


def _tie_break_signals(nb_dev: device_model, zb_dev: device_model) -> tuple[int, int, int]:
    """Return (templates_overlap, hostgroup_overlap, secondary_score) for a device pair.

    Used to break ties between otherwise equally-scored candidates: prefer more shared
    templates, then more shared hostgroups, then exact IP/DNS/name matches as a fallback.
    """
    # templates overlap (normalized)
    try:
        nb_templates = set(
            t.lower() for t in (nb_dev.templates or []) if isinstance(t, str)
        )
    except (TypeError, AttributeError):
        nb_templates = set()
    try:
        zb_templates = set(
            t.lower() for t in (zb_dev.templates or []) if isinstance(t, str)
        )
    except (TypeError, AttributeError):
        zb_templates = set()
    templates_overlap = len(nb_templates & zb_templates)

    # hostgroup overlap (Zabbix hostgroups may be list of dicts)
    def hg_names(hg):
        if not hg:
            return set()
        if isinstance(hg, list):
            names = set()
            for item in hg:
                if isinstance(item, dict) and "name" in item:
                    names.add(str(item["name"]).lower())
                elif isinstance(item, str):
                    names.add(item.lower())
            return names
        if isinstance(hg, str):
            return {hg.lower()}
        return set()

    nb_hg = hg_names(nb_dev.hostgroup)
    zb_hg = hg_names(zb_dev.hostgroup)
    hostgroup_overlap = len(nb_hg & zb_hg)

    # secondary exact matches weight (IP/DNS/name)
    nb_ip, nb_dns = _primary_ip_dns(nb_dev)
    zb_ip, zb_dns = _primary_ip_dns(zb_dev)
    nb_name = normalize_name(getattr(nb_dev, "name", ""))
    zb_name = normalize_name(getattr(zb_dev, "name", ""))

    secondary = 0
    if nb_ip and zb_ip and nb_ip == zb_ip:
        secondary += 8
    if nb_dns and zb_dns and nb_dns == zb_dns:
        secondary += 4
    if nb_name and zb_name and nb_name == zb_name:
        secondary += 2

    return templates_overlap, hostgroup_overlap, secondary


# Bonus weights are ordered by magnitude (templates > hostgroups > secondary matches) and
# capped so the combined bonus can never approach the smallest real gap between
# _calculate_match_score's tiers (0.05, between its 0.5/0.55/0.6 tiers). This lets ties in
# match score resolve the same way the old per-candidate tie-break logic resolved them,
# without the bonus ever being able to override an outcome the real score should decide.
_TEMPLATE_BONUS_WEIGHT = 5e-4
_HOSTGROUP_BONUS_WEIGHT = 5e-6
_SECONDARY_BONUS_WEIGHT = 5e-8
_MAX_OVERLAP_COUNT = 50  # defensive cap; realistic overlaps are a handful of items


def _overlap_bonus(nb_dev: device_model, zb_dev: device_model) -> float:
    """Small tie-break bonus folded into the assignment score matrix.

    Never large enough to override a real score-tier difference; only distinguishes
    between candidates that would otherwise score identically under _calculate_match_score.
    """
    templates_overlap, hostgroup_overlap, secondary = _tie_break_signals(nb_dev, zb_dev)
    return (
        min(templates_overlap, _MAX_OVERLAP_COUNT) * _TEMPLATE_BONUS_WEIGHT
        + min(hostgroup_overlap, _MAX_OVERLAP_COUNT) * _HOSTGROUP_BONUS_WEIGHT
        + min(secondary, _MAX_OVERLAP_COUNT) * _SECONDARY_BONUS_WEIGHT
    )


def compare_devices(
    nb_device_list: list[device_model], zb_device_list: list[device_model]
) -> tuple[list[device_difference_model], list[device_model], list[device_model]]:
    """
    Compare devices from two sources (NetBox and Zabbix) and identify differences.

    Builds a NetBox x Zabbix match-score matrix (via _calculate_match_score, with a small
    tie-break bonus from _overlap_bonus folded in) and solves it as a bipartite assignment
    problem (Hungarian algorithm) to find the pairing that maximizes total match score
    across all devices at once. This avoids the order-dependency of a per-device greedy
    match, where a device could permanently claim a mediocre match before a better match
    for it was discovered elsewhere in the list.
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

    if not nb_device_list:
        return different_devices, nb_devices, list(zb_device_list)
    if not zb_device_list:
        return different_devices, list(nb_device_list), zb_devices

    n = len(nb_device_list)
    m = len(zb_device_list)

    # Raw scores drive the >0.3 acceptance threshold and log output (unchanged semantics).
    # Augmented scores add the tiny tie-break bonus and are what the solver optimizes.
    raw_scores = [[0.0] * m for _ in range(n)]
    aug_scores = [[0.0] * m for _ in range(n)]
    for i, nb_dev in enumerate(nb_device_list):
        for j, zb_dev in enumerate(zb_device_list):
            score = _calculate_match_score(nb_dev, zb_dev)
            raw_scores[i][j] = score
            aug_scores[i][j] = score + _overlap_bonus(nb_dev, zb_dev) if score > 0 else 0.0

    # Globally optimal one-to-one assignment maximizing total (augmented) score.
    row_ind, col_ind = linear_sum_assignment(aug_scores, maximize=True)

    matched_nb_idx: set[int] = set()
    matched_zb_idx: set[int] = set()
    for i, j in zip(row_ind.tolist(), col_ind.tolist()):
        score = raw_scores[i][j]
        # Use match only if score is above threshold (>0.3 recommends good confidence)
        if score <= 0.3:
            continue

        nb_dev = nb_device_list[i]
        zb_dev = zb_device_list[j]
        log.logger.info(
            "Matched: %s (NB) <-> %s (ZB) with score %.2f",
            getattr(nb_dev, "name", ""), getattr(zb_dev, "name", ""), score
        )
        differences: tuple[int, tuple[device_model, device_model], tuple[list[str], list[str]]] = find_differences(nb_dev, zb_dev)
        if differences[0] == 1:
            different_devices.append(
                device_difference_model(
                    nb_dev, zb_dev, differences[2]
                )
            )
        matched_nb_idx.add(i)
        matched_zb_idx.add(j)

    # NetBox devices with no accepted assignment are NB-only.
    for i, nb_dev in enumerate(nb_device_list):
        if i in matched_nb_idx:
            continue
        best_score = max(raw_scores[i])
        if best_score > 0:
            log.logger.info(
                "No match for %s (best score: %.2f)",
                getattr(nb_dev, "name", ""), best_score
            )
        nb_devices.append(nb_dev)

    # Any Zabbix devices with no accepted assignment are ZB-only.
    zb_devices.extend(
        zb_dev for j, zb_dev in enumerate(zb_device_list) if j not in matched_zb_idx
    )

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
    log.logger.debug("Zabbix IP: %s", zb_ip)
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
