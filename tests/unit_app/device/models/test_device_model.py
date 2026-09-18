"""Unit tests for device model helper and payload methods."""

import unittest
from unittest.mock import patch

from app.device.models.address_model import Address
from app.device.models.device_model import (
    Device,
    build_snmp_details,
    dict_interfaces_zb,
    dict_interfaces_zb_id,
    format_nb_status,
    map_port_type_default_port,
    normalize_status,
)
from app.device.models.interface_model import Interface


class DeviceModelTests(unittest.TestCase):
    """Tests for status helpers, interface mapping, and payload generation."""

    def _iface(self, port_type: str = "1", snmp_version: str = "") -> Interface:
        return Interface(
            "eth0", [Address("10.10.10.1/24", "host.local")], "aa", port_type, snmp_version
        )

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
        self.assertEqual(create_payload[1]["details"]["version"], "2")
        self.assertNotIn("details", create_payload[0])  # Agent has no SNMP details
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

    def test_dict_interfaces_zb_no_details_for_ipmi_and_jmx(self):
        """IPMI/JMX interfaces should never get an SNMP `details` object."""
        interfaces = [self._iface("3"), self._iface("4")]
        create_payload = dict_interfaces_zb(interfaces)

        self.assertNotIn("details", create_payload[0])  # IPMI
        self.assertNotIn("details", create_payload[1])  # JMX

    def test_dict_interfaces_zb_snmpv3_details(self):
        """An interface with snmp_version '3' should build SNMPv3 details."""
        interfaces = [self._iface("2", snmp_version="3")]
        create_payload = dict_interfaces_zb(interfaces)

        details = create_payload[0]["details"]
        self.assertEqual(details["version"], "3")
        self.assertIn("securityname", details)
        self.assertNotIn("community", details)

    def test_build_snmp_details_defaults_to_v2(self):
        """An empty/unrecognized snmp_version should default to SNMPv2."""
        details = build_snmp_details("")
        self.assertEqual(details["version"], "2")
        self.assertEqual(details["community"], "{$SNMP_COMMUNITY}")

    @patch.dict("os.environ", {"SNMPV2_MACRO": "{$MY_COMMUNITY}"}, clear=False)
    def test_build_snmp_details_v2_reads_env(self):
        """SNMPv2 community should come from the SNMPV2_MACRO env var."""
        details = build_snmp_details("2")
        self.assertEqual(details["community"], "{$MY_COMMUNITY}")

    @patch.dict(
        "os.environ",
        {
            "ZABBIX_SNMPV3_SECURITY_NAME": "myuser",
            "ZABBIX_SNMPV3_AUTH_PASSPHRASE": "authpass",
            "ZABBIX_SNMPV3_PRIV_PASSPHRASE": "privpass",
        },
        clear=False,
    )
    def test_build_snmp_details_v3_reads_env(self):
        """SNMPv3 security details should come from env vars."""
        details = build_snmp_details("3")
        self.assertEqual(details["securityname"], "myuser")
        self.assertEqual(details["authpassphrase"], "authpass")
        self.assertEqual(details["privpassphrase"], "privpass")

    def test_map_port_type_default_port_uses_hardcoded_defaults(self):
        """Ports should default to today's values when no env vars are set."""
        self.assertEqual(map_port_type_default_port("Agent"), "10050")
        self.assertEqual(map_port_type_default_port("SNMP"), "161")
        self.assertEqual(map_port_type_default_port("IPMI"), "623")
        self.assertEqual(map_port_type_default_port("JMX"), "12345")

    @patch.dict("os.environ", {"ZABBIX_SNMP_PORT": "1161"}, clear=False)
    def test_map_port_type_default_port_reads_env(self):
        """Ports should be overridable via environment variables."""
        self.assertEqual(map_port_type_default_port("SNMP"), "1161")
        self.assertEqual(map_port_type_default_port("2"), "1161")


if __name__ == "__main__":
    unittest.main()
