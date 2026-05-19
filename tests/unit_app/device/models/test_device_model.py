"""Unit tests for device model helper and payload methods."""

import unittest

from app.device.models.address_model import Address
from app.device.models.device_model import (
    Device,
    dict_interfaces_zb,
    dict_interfaces_zb_id,
    format_nb_status,
    normalize_status,
)
from app.device.models.interface_model import Interface


class DeviceModelTests(unittest.TestCase):
    """Tests for status helpers, interface mapping, and payload generation."""

    def _iface(self, port_type: str = "1") -> Interface:
        return Interface("eth0", [Address("10.10.10.1/24", "host.local")], "aa", port_type)

    def test_status_and_port_type_helpers(self):
        """Status and port-type helper functions should map expected values."""
        self.assertEqual(format_nb_status("Active"), "active")
        self.assertEqual(format_nb_status("Unknown"), "offline")
        # map_port_type is commented out in implementation, using map_port_type_device instead
        self.assertEqual(normalize_status(0), "Active")
        self.assertEqual(normalize_status("other"), "Inactive")

    def test_dict_interfaces_helpers(self):
        """Interface conversion helpers should include expected keys and values."""
        interfaces = [self._iface("1"), self._iface("2")]
        create_payload = dict_interfaces_zb(interfaces)
        update_payload = dict_interfaces_zb_id(interfaces, interface_id=99)

        self.assertEqual(create_payload[0]["main"], 1)  # First interface of port_type "1"
        self.assertEqual(create_payload[1]["main"], 1)  # First interface of port_type "2"
        self.assertEqual(create_payload[1]["details"]["version"], 3)
        self.assertEqual(update_payload[0]["interfaceid"], 99)

    def test_dict_interfaces_helpers_multiple_same_type(self):
        """Multiple interfaces of same type should mark only first as main."""
        interfaces = [self._iface("1"), self._iface("1"), self._iface("2")]
        create_payload = dict_interfaces_zb(interfaces)

        self.assertEqual(create_payload[0]["main"], 1)  # First interface of port_type "1"
        self.assertEqual(create_payload[1]["main"], 0)  # Second interface of port_type "1"
        self.assertEqual(create_payload[2]["main"], 1)  # First interface of port_type "2"

    def test_create_and_update_data_zabbix(self):
        """Device should produce valid Zabbix create and update payloads."""
        device = Device(
            "r1",
            [self._iface("SNMP")],
            ["g1"],
            "desc",
            ["tpl1"],
            "Active",
        )

        create_data = device.create_data_zabbix(
            hostgroupids=[1, "2", ["3"], {"groupid": "4"}, None, -1], templateids=[10, None]
        )
        update_data = device.update_data_zabbix(
            hostid="101", interface_ids=[77], hostgroupids=[1], templateids=[10], name="r1-new"
        )
        update_data_no_interfaces = device.update_data_zabbix(
            hostid="101",
            interface_ids=[77],
            hostgroupids=[1],
            templateids=[10],
            name="r1-new",
            include_interfaces=False,
        )
        interface_update_data = device.update_interface_data_zabbix(interface_ids=[77])

        self.assertEqual(create_data["method"], "host.create")
        self.assertEqual(len(create_data["params"]["groups"]), 4)
        self.assertEqual(update_data["method"], "host.update")
        self.assertEqual(update_data["params"]["hostid"], "101")
        self.assertEqual(update_data["params"]["name"], "r1-new")
        self.assertNotIn("interfaces", update_data_no_interfaces["params"])
        self.assertEqual(interface_update_data["method"], "hostinterface.update")
        self.assertEqual(interface_update_data["params"][0]["interfaceid"], 77)


if __name__ == "__main__":
    unittest.main()
