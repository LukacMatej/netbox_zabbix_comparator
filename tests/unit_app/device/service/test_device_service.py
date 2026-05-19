"""Unit tests for device service API helpers and formatters."""

import unittest
from unittest.mock import Mock, patch
import requests

from app.device.models.address_model import Address
from app.device.models.device_model import Device
from app.device.models.difference_model import DeviceDifference
from app.device.models.interface_model import Interface
from app.device.service import device_service as ds


class DeviceServiceTests(unittest.TestCase):
    """Tests for utility functions and external API handling in device service."""

    def _device(self, name: str, ip: str = "10.0.0.1", port_type: str = "1") -> Device:
        return Device(
            name=name,
            interfaces=[Interface("eth0", [Address(ip, f"{name}.local")], "aa", port_type)],
            hostgroup=[{"name": "HG"}],
            description="desc",
            templates=["T1"],
            status="Active",
        )

    def test_format_helpers(self):
        """Formatting helpers should map addresses, status, MAC and port types correctly."""
        self.assertEqual(ds.format_address("1.2.3.4/24"), "1.2.3.4")
        self.assertEqual(ds.format_status("active"), "Active")
        self.assertEqual(ds.format_status("offline"), "Disabled")
        self.assertEqual(ds.format_status("other"), "other")
        self.assertEqual(ds.format_mac("AA:BB:CC:DD:EE:FF"), "aabb.ccdd.eeff")
        self.assertEqual(ds.format_port_type("SNMP"), "2")
        self.assertEqual(ds.uniform_port_type("2"), "SNMP")

    def test_map_port_type_device_and_uniform_output_text(self):
        """Port type mapping and output text normalization should update list values."""
        nb = [self._device("nb", port_type="1")]
        zb = [self._device("zb", port_type="SNMP")]
        ds.map_port_type_device(nb, zb)
        self.assertEqual(nb[0].interfaces[0].port_type, "Agent")
        self.assertEqual(zb[0].interfaces[0].port_type, "SNMP")

        diff = [DeviceDifference(nb[0], zb[0], (["name"], ["status"]))]
        _, display_nb, _ = ds.uniform_output_text(diff, nb, zb)
        self.assertEqual(nb[0].hostgroup, [{"name": "HG"}])
        self.assertEqual(nb[0].templates, ["T1"])
        self.assertEqual(display_nb[0].hostgroup, "HG")
        self.assertEqual(display_nb[0].templates, "T1")

    def test_uniform_output_text_handles_string_hostgroups(self):
        """Hostgroup lists made of strings should be rendered without errors."""
        nb = [
            Device(
                name="nb",
                interfaces=[Interface("eth0", [Address("10.0.0.1", "nb.local")], "aa", "1")],
                hostgroup=["HG-A", "HG-B"],
                description="desc",
                templates=["T1"],
                status="Active",
            )
        ]
        zb = [
            Device(
                name="zb",
                interfaces=[Interface("eth0", [Address("10.0.0.1", "zb.local")], "aa", "1")],
                hostgroup=[{"name": "HG-A"}, {"name": "HG-B"}],
                description="desc",
                templates=["T1"],
                status="Active",
            )
        ]
        diff = [DeviceDifference(nb[0], zb[0], ([], []))]

        _, display_nb, display_zb = ds.uniform_output_text(diff, nb, zb)

        self.assertEqual(display_nb[0].hostgroup, "HG-A, HG-B")
        self.assertEqual(display_zb[0].hostgroup, "HG-A, HG-B")

    @patch("app.device.service.device_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb", "ZABBIX_KEY": "k"}, clear=False)
    def test_find_hostinterface_id_success(self, post_mock):
        """Host interface lookup should return parsed interface ID on success."""
        response = Mock()
        response.json.return_value = {"result": [{"interfaceid": "55"}]}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        self.assertEqual(ds.find_hostinterface_id("10"), 55)

    @patch("app.device.service.device_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb", "ZABBIX_KEY": "k"}, clear=False)
    def test_find_hostinterface_id_request_error(self, post_mock):
        """Host interface lookup should return -1 on request exception."""
        post_mock.side_effect = requests.exceptions.RequestException("network")
        self.assertEqual(ds.find_hostinterface_id("10"), -1)

    @patch("app.device.service.device_service.requests.get")
    @patch.dict("os.environ", {"NETBOX_IP": "http://nb", "NETBOX_KEY": "k"}, clear=False)
    def test_find_nb_identifiers(self, get_mock):
        """NetBox site/type/role helper lookups should return resource IDs."""
        response = Mock(status_code=200)
        response.json.return_value = {"count": 1, "results": [{"id": 7}]}
        get_mock.return_value = response

        self.assertEqual(ds.find_nb_site_id("S1"), 7)
        self.assertEqual(ds.find_nb_device_type_id("C9300"), 7)
        self.assertEqual(ds.find_nb_device_role_id("Switch"), 7)

    @patch("app.device.service.device_service.requests.post")
    def test_get_nb_devices_success(self, post_mock):
        """NetBox device retrieval should map API JSON into device models."""
        response = Mock(status_code=200)
        response.request = Mock(method="POST", url="http://nb/graphql", headers={}, body="{}")
        response.json.return_value = {
            "data": {
                "device_list": [
                    {
                        "name": "sw1",
                        "description": "d",
                        "status": "active",
                        "config_context": {"zabbix": {"templates": ["tpl"], "port_type": "SNMP"}},
                        "primary_ip4": {"address": "10.0.0.1/24", "dns_name": "sw1.local"},
                        "interfaces": [
                            {
                                "name": "eth0",
                                "mac_addresses": [{"mac_address": "aa:bb:cc:dd:ee:ff"}],
                                "ip_addresses": [
                                    {"address": "10.0.0.1/24", "dns_name": "sw1.local"}
                                ],
                            }
                        ],
                    }
                ]
            }
        }
        post_mock.return_value = response

        result = ds.get_nb_devices("k", "http://nb/graphql")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0].name, "sw1")
        self.assertEqual(result[0].interfaces[0].addresses[0].address, "10.0.0.1")

    @patch("app.device.service.device_service.requests.post")
    def test_get_nb_devices_error_status(self, post_mock):
        """NetBox device retrieval should return an error string on non-200 response."""
        response = Mock(status_code=500, text="boom")
        response.request = Mock(method="POST", url="u", headers={}, body="{}")
        post_mock.return_value = response

        result = ds.get_nb_devices("k", "http://nb/graphql")
        self.assertIsInstance(result, str)
        self.assertIn("Failed to fetch", result)

    @patch("app.device.service.device_service.requests.post")
    def test_get_zb_devices_success(self, post_mock):
        """Zabbix device retrieval should parse successful host payload."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": [
                {
                    "host": "zb1",
                    "description": "d",
                    "parentTemplates": [{"name": "tpl"}],
                    "status": "0",
                    "hostgroups": [{"groupid": "1", "name": "HG"}],
                    "interfaces": [{"dns": "zb1.local", "ip": "10.0.0.2", "type": "2"}],
                }
            ]
        }
        post_mock.return_value = response

        result = ds.get_zb_devices("k", "http://zb")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0].name, "zb1")

    @patch("app.device.service.device_service.requests.post")
    def test_get_zb_devices_api_error(self, post_mock):
        """Zabbix device retrieval should return error string on API error field."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"error": "bad"}
        post_mock.return_value = response

        result = ds.get_zb_devices("k", "http://zb")
        self.assertIsInstance(result, str)
        self.assertIn("Error in Zabbix API response", result)


if __name__ == "__main__":
    unittest.main()
