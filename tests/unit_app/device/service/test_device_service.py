"""Unit tests for device service API helpers and formatters."""

import unittest
import json
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
        self.assertEqual(ds.uniform_port_type("2"), "SNMP")
        self.assertEqual(ds.uniform_port_type("SNMP"), "SNMP")

    def test_split_snmp_port_type(self):
        """SNMPv2/SNMPv3 should resolve to generic SNMP + version; SNMP (bare) is dropped."""
        self.assertEqual(ds.split_snmp_port_type("SNMPv2"), ("SNMP", "2"))
        self.assertEqual(ds.split_snmp_port_type("SNMPv3"), ("SNMP", "3"))
        self.assertEqual(ds.split_snmp_port_type("Agent"), ("Agent", ""))
        self.assertEqual(ds.split_snmp_port_type("1"), ("Agent", ""))
        self.assertEqual(ds.split_snmp_port_type("IPMI"), ("IPMI", ""))
        self.assertEqual(ds.split_snmp_port_type("JMX"), ("JMX", ""))
        self.assertIsNone(ds.split_snmp_port_type("SNMP"))
        self.assertIsNone(ds.split_snmp_port_type("2"))
        self.assertIsNone(ds.split_snmp_port_type("bogus"))

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
    def test_get_zabbix_device_reads_hostgroups(self, post_mock):
        """Regression test: get_zabbix_device must request selectHostGroups and
        read the "hostgroups" key. Zabbix >= 6.0 doesn't populate "groups" from
        the pre-6.0 selectGroups param, so using the old names silently made
        every webhook-triggered device come back with hostgroup == []."""
        response = Mock(status_code=200)
        response.json.return_value = {
            "result": [
                {
                    "hostid": "10795",
                    "host": "veeam",
                    "description": "",
                    "status": "0",
                    "interfaces": [],
                    "hostgroups": [{"groupid": "2", "name": "Linux servers"}],
                    "parentTemplates": [{"name": "APC UPS by SNMP"}],
                }
            ]
        }
        post_mock.return_value = response

        device = ds.get_zabbix_device("veeam")

        self.assertIsNotNone(device)
        self.assertEqual(device.hostgroup, ["Linux servers"])
        sent_params = post_mock.call_args.kwargs["json"]["params"]
        self.assertIn("selectHostGroups", sent_params)
        self.assertNotIn("selectGroups", sent_params)

    @patch("app.device.service.device_service.requests.get")
    @patch.dict("os.environ", {"NETBOX_IP": "http://nb", "NETBOX_KEY": "k"}, clear=False)
    def test_find_nb_identifiers(self, get_mock):
        """NetBox site/type/role helper lookups should return resource IDs."""
        response = Mock(status_code=200)
        response.text = json.dumps({"count": 1, "results": [{"id": 7}]})
        get_mock.return_value = response

        self.assertEqual(ds.find_nb_site_id("S1"), 7)
        self.assertEqual(ds.find_nb_device_type_id("C9300"), 7)
        self.assertEqual(ds.find_nb_device_role_id("Switch"), 7)
        self.assertEqual(ds.find_nb_device_id("sw1"), 7)

    @patch("app.device.service.device_service.requests.get")
    @patch.dict("os.environ", {"NETBOX_IP": "http://nb", "NETBOX_KEY": "k"}, clear=False)
    def test_find_nb_device_id_not_found(self, get_mock):
        """A device name with no matching NetBox device should return -1."""
        response = Mock(status_code=200)
        response.text = json.dumps({"count": 0, "results": []})
        get_mock.return_value = response

        self.assertEqual(ds.find_nb_device_id("missing"), -1)

    @patch("app.device.service.device_service.requests.post")
    def test_get_nb_devices_success(self, post_mock):
        """NetBox device retrieval should map API JSON into device models."""
        response = Mock(status_code=200)
        response.request = Mock(method="POST", url="http://nb/graphql", headers={}, body="{}")
        response.text = json.dumps({
            "data": {
                "device_list": [
                    {
                        "name": "sw1",
                        "description": "d",
                        "status": "active",
                        "config_context": {"zabbix": {"templates": ["tpl"], "port_type": ["SNMPv2"]}},
                        "custom_fields": {"zabbix_hostgroups": None, "zabbix_templates": None, "zabbix_port_type": None},
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
                        "role": None,
                    }
                ],
                "device_role_list": []
            }
        })
        post_mock.return_value = response

        result = ds.get_nb_devices("k", "http://nb/graphql")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0].name, "sw1")
        self.assertEqual(result[0].interfaces[0].addresses[0].address, "10.0.0.1")
        self.assertEqual(result[0].interfaces[0].port_type, "SNMP")
        self.assertEqual(result[0].interfaces[0].snmp_version, "2")

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
        response.text = json.dumps({
            "result": [
                {
                    "host": "zb1",
                    "description": "d",
                    "parentTemplates": [{"name": "tpl"}],
                    "status": "0",
                    "hostgroups": [{"groupid": "1", "name": "HG"}],
                    "interfaces": [
                        {"dns": "zb1.local", "ip": "10.0.0.2", "type": "2"},
                        {
                            "dns": "zb1-v3.local",
                            "ip": "10.0.0.3",
                            "type": "2",
                            "details": {"version": "3"},
                        },
                    ],
                }
            ]
        })
        post_mock.return_value = response

        result = ds.get_zb_devices("k", "http://zb")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0].name, "zb1")
        self.assertEqual(result[0].interfaces[0].snmp_version, "2")  # no details -> defaults to v2
        self.assertEqual(result[0].interfaces[1].snmp_version, "3")

    @patch("app.device.service.device_service.requests.post")
    def test_get_zb_devices_api_error(self, post_mock):
        """Zabbix device retrieval should return error string on API error field."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = json.dumps({"error": "bad"})
        post_mock.return_value = response

        result = ds.get_zb_devices("k", "http://zb")
        self.assertIsInstance(result, str)
        self.assertIn("Error in Zabbix API response", result)

    @patch.dict("os.environ", {"EXCLUDED_HOSTGROUPS": "Servers"}, clear=False)
    @patch("app.device.service.device_service.requests.post")
    def test_get_zb_devices_hostgroup_filter_excludes_matching_hosts(self, post_mock):
        """Hosts belonging to the excluded hostgroup should be dropped client-side."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = json.dumps({
            "result": [
                {
                    "host": "zb1",
                    "description": "d",
                    "parentTemplates": [{"name": "tpl"}],
                    "status": "0",
                    "hostgroups": [{"groupid": "1", "name": "Servers"}],
                    "interfaces": [{"dns": "zb1.local", "ip": "10.0.0.2", "type": "2"}],
                },
                {
                    "host": "zb2",
                    "description": "d",
                    "parentTemplates": [{"name": "tpl"}],
                    "status": "0",
                    "hostgroups": [{"groupid": "2", "name": "Network"}],
                    "interfaces": [{"dns": "zb2.local", "ip": "10.0.0.3", "type": "2"}],
                },
            ]
        })
        post_mock.return_value = response

        result = ds.get_zb_devices("k", "http://zb")

        self.assertEqual(post_mock.call_count, 1)
        self.assertIsInstance(result, list)
        self.assertEqual([device.name for device in result], ["zb2"])
        params = post_mock.call_args.kwargs["json"]["params"]
        self.assertNotIn("groupids", params)

    @patch.dict("os.environ", {"EXCLUDED_HOSTGROUPS": ""}, clear=False)
    @patch("app.device.service.device_service.requests.post")
    def test_get_zb_devices_no_hostgroup_filter_keeps_all_hosts(self, post_mock):
        """An empty hostgroup filter should exclude nothing."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = json.dumps({
            "result": [
                {
                    "host": "zb1",
                    "description": "d",
                    "parentTemplates": [{"name": "tpl"}],
                    "status": "0",
                    "hostgroups": [{"groupid": "1", "name": "Servers"}],
                    "interfaces": [{"dns": "zb1.local", "ip": "10.0.0.2", "type": "2"}],
                },
            ]
        })
        post_mock.return_value = response

        result = ds.get_zb_devices("k", "http://zb")
        self.assertEqual([device.name for device in result], ["zb1"])


    def test_get_nb_hostgroups_priority(self):
        """Hostgroups resolve device custom field > device role > config context."""
        device = {
            "name": "sw1",
            "role": {"name": "Switch"},
            "config_context": {"zabbix": {"hostgroups": ["CtxGroup"]}},
        }
        role_map = {"Switch": ["RoleGroup"]}

        self.assertEqual(
            ds.get_nb_hostgroups(device, {"zabbix_hostgroups": ["DevGroup"]}, role_map),
            ["DevGroup"],
        )
        self.assertEqual(
            ds.get_nb_hostgroups(device, {"zabbix_hostgroups": None}, role_map),
            ["RoleGroup"],
        )
        self.assertEqual(
            ds.get_nb_hostgroups(device, {"zabbix_hostgroups": []}, {"Switch": []}),
            ["CtxGroup"],
        )
        self.assertEqual(
            ds.get_nb_hostgroups(
                {"name": "sw1", "role": None, "config_context": None}, {}, role_map
            ),
            [],
        )

    def test_get_device_role_hostgroup_map(self):
        """Role hostgroup map should tolerate missing/empty custom fields."""
        result = ds.get_device_role_hostgroup_map([
            {"name": "Switch", "custom_fields": {"zabbix_hostgroups": ["RoleGroup"]}},
            {"name": "Router", "custom_fields": {"zabbix_hostgroups": None}},
            {"name": "Server", "custom_fields": None},
        ])
        self.assertEqual(result, {"Switch": ["RoleGroup"], "Router": [], "Server": []})

    @patch("app.device.service.device_service.requests.post")
    def test_get_nb_devices_hostgroups_from_role(self, post_mock):
        """A device without zabbix_hostgroups should inherit hostgroups from its role."""
        response = Mock(status_code=200)
        response.request = Mock(method="POST", url="http://nb/graphql", headers={}, body="{}")
        response.text = json.dumps({
            "data": {
                "device_list": [
                    {
                        "name": "sw1",
                        "description": "d",
                        "status": "active",
                        "config_context": {},
                        "custom_fields": {"zabbix_hostgroups": None, "zabbix_templates": None, "zabbix_port_type": None},
                        "primary_ip4": {"address": "10.0.0.1/24", "dns_name": "sw1.local"},
                        "interfaces": [],
                        "role": {"name": "Switch"},
                    }
                ],
                "device_role_list": [
                    {
                        "name": "Switch",
                        "custom_fields": {
                            "zabbix_hostgroups": ["RoleGroup"],
                            "zabbix_templates": ["tpl"],
                            "zabbix_port_type": ["Agent"],
                        },
                    }
                ],
            }
        })
        post_mock.return_value = response

        result = ds.get_nb_devices("k", "http://nb/graphql")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0].hostgroup, ["RoleGroup"])
        self.assertEqual(result[0].templates, ["tpl"])

    @patch("app.device.service.device_service.get_primary_interface", return_value=None)
    @patch("app.device.service.device_service.query_netbox_role_custom_fields")
    def test_parse_webhook_update_hostgroups_from_role(self, role_mock, _iface_mock):
        """Webhook update should fall back to role hostgroups/templates in one role lookup."""
        role_mock.return_value = {
            "zabbix_hostgroups": ["RoleGroup"],
            "zabbix_templates": ["RoleTpl"],
        }
        data = {
            "data": {"name": "sw1", "role": {"name": "Switch"}, "config_context": {}},
            "snapshots": {
                "postchange": {
                    "name": "sw1",
                    "custom_fields": {"zabbix_hostgroups": [], "zabbix_templates": []},
                }
            },
        }

        result = ds.parse_webhook_update(data)
        role_mock.assert_called_once_with("Switch")
        self.assertEqual(result.hostgroup, ["RoleGroup"])
        self.assertEqual(result.templates, ["RoleTpl"])

    @patch("app.device.service.device_service.get_primary_interface", return_value=None)
    @patch("app.device.service.device_service.query_netbox_role_custom_fields")
    def test_parse_webhook_update_device_fields_skip_role_lookup(self, role_mock, _iface_mock):
        """When the device sets both hostgroups and templates, NetBox isn't queried for the role."""
        data = {
            "data": {"name": "sw1", "role": {"name": "Switch"}, "config_context": {}},
            "snapshots": {
                "postchange": {
                    "name": "sw1",
                    "custom_fields": {"zabbix_hostgroups": ["DevGroup"], "zabbix_templates": ["DevTpl"]},
                }
            },
        }

        result = ds.parse_webhook_update(data)
        role_mock.assert_not_called()
        self.assertEqual(result.hostgroup, ["DevGroup"])
        self.assertEqual(result.templates, ["DevTpl"])

    @patch("app.device.service.device_service.query_netbox_role_custom_fields")
    def test_parse_webhook_create_hostgroups_from_role(self, role_mock):
        """Webhook create should fall back to role hostgroups when the device has none."""
        role_mock.return_value = {"zabbix_hostgroups": ["RoleGroup"]}
        data = {
            "data": {
                "name": "sw1",
                "role": {"name": "Switch"},
                "custom_fields": {"zabbix_hostgroups": []},
                "status": {"value": "active"},
            }
        }

        result = ds.parse_webhook_create(data)
        role_mock.assert_called_once_with("Switch")
        self.assertEqual(result.name, "sw1")
        self.assertEqual(result.hostgroup, ["RoleGroup"])

    @patch("app.device.service.device_service.query_netbox_role_custom_fields")
    def test_parse_webhook_create_device_hostgroups_skip_role_lookup(self, role_mock):
        """Webhook create shouldn't query the role when the device sets its own hostgroups."""
        data = {
            "data": {
                "name": "sw1",
                "role": {"name": "Switch"},
                "custom_fields": {"zabbix_hostgroups": ["DevGroup"]},
            }
        }

        result = ds.parse_webhook_create(data)
        role_mock.assert_not_called()
        self.assertEqual(result.hostgroup, ["DevGroup"])

    def test_custom_field_value_unwraps_netbox_47_objects(self):
        """NetBox >= 4.7 {value, label} selection objects should unwrap to the raw value."""
        self.assertEqual(ds.custom_field_value({"value": "SNMPv3", "label": "SNMPv3"}), "SNMPv3")
        self.assertEqual(
            ds.custom_field_value([{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]),
            ["a", "b"],
        )

    def test_custom_field_value_passes_through_raw_values(self):
        """Pre-4.7 raw values (strings, lists of strings, None) should be unchanged."""
        self.assertEqual(ds.custom_field_value("SNMPv3"), "SNMPv3")
        self.assertEqual(ds.custom_field_value(["a", "b"]), ["a", "b"])
        self.assertIsNone(ds.custom_field_value(None))

    def test_normalize_custom_fields_handles_empty(self):
        """Missing custom fields should normalize to an empty dict."""
        self.assertEqual(ds.normalize_custom_fields(None), {})
        self.assertEqual(ds.normalize_custom_fields({}), {})

    @patch("app.device.service.device_service.requests.post")
    def test_get_nb_devices_netbox_47_selection_objects(self, post_mock):
        """NetBox >= 4.7 {value, label} custom fields (device and role) should map to raw values."""
        response = Mock(status_code=200)
        response.request = Mock(method="POST", url="http://nb/graphql", headers={}, body="{}")
        response.text = json.dumps({
            "data": {
                "device_list": [
                    {
                        "name": "sw1",
                        "description": "",
                        "status": "active",
                        "config_context": {},
                        "custom_fields": {
                            "zabbix_hostgroups": [{"value": "Netbox", "label": "Netbox"}],
                            "zabbix_templates": [
                                {"value": "Ping test", "label": "Ping test"},
                                {"value": "Cisco IOS by SNMP", "label": "Cisco IOS by SNMP"},
                            ],
                            "zabbix_port_type": [{"value": "SNMPv3", "label": "SNMPv3"}],
                        },
                        "primary_ip4": {"address": "10.0.0.1/24", "dns_name": ""},
                        "interfaces": [],
                        "role": {"name": "Switch"},
                    },
                    {
                        "name": "sw2",
                        "description": "",
                        "status": "active",
                        "config_context": {},
                        "custom_fields": {
                            "zabbix_hostgroups": None,
                            "zabbix_templates": None,
                            "zabbix_port_type": None,
                        },
                        "primary_ip4": {"address": "10.0.0.2/24", "dns_name": ""},
                        "interfaces": [],
                        "role": {"name": "Switch"},
                    },
                ],
                "device_role_list": [
                    {
                        "name": "Switch",
                        "custom_fields": {
                            "zabbix_hostgroups": [{"value": "RoleGroup", "label": "RoleGroup"}],
                            "zabbix_templates": [{"value": "RoleTpl", "label": "RoleTpl"}],
                            "zabbix_port_type": [{"value": "Agent", "label": "Agent"}],
                        },
                    }
                ],
            }
        })
        post_mock.return_value = response

        result = ds.get_nb_devices("k", "http://nb/graphql")
        self.assertIsInstance(result, list)
        sw1, sw2 = result
        self.assertEqual(sw1.hostgroup, ["Netbox"])
        self.assertEqual(sw1.templates, ["Cisco IOS by SNMP", "Ping test"])
        self.assertEqual(len(sw1.interfaces), 1)
        self.assertEqual(sw1.interfaces[0].port_type, "SNMP")
        self.assertEqual(sw1.interfaces[0].snmp_version, "3")
        self.assertEqual(sw2.hostgroup, ["RoleGroup"])
        self.assertEqual(sw2.templates, ["RoleTpl"])
        self.assertEqual(sw2.interfaces[0].port_type, "Agent")

    @patch("app.device.service.device_service.get_primary_interface", return_value=None)
    @patch("app.device.service.device_service.query_netbox_role_custom_fields")
    def test_parse_webhook_update_netbox_47_selection_objects(self, role_mock, iface_mock):
        """Webhook update should unwrap NetBox >= 4.7 {value, label} custom fields."""
        data = {
            "data": {"name": "sw1", "role": {"name": "Switch"}, "config_context": {}},
            "snapshots": {
                "postchange": {
                    "name": "sw1",
                    "custom_fields": {
                        "zabbix_hostgroups": [{"value": "DevGroup", "label": "DevGroup"}],
                        "zabbix_templates": [{"value": "DevTpl", "label": "DevTpl"}],
                        "zabbix_port_type": [{"value": "SNMPv3", "label": "SNMPv3"}],
                    },
                }
            },
        }

        result = ds.parse_webhook_update(data)
        role_mock.assert_not_called()
        iface_mock.assert_called_once_with(data["data"], "SNMP", "3")
        self.assertEqual(result.hostgroup, ["DevGroup"])
        self.assertEqual(result.templates, ["DevTpl"])

    @patch("app.device.service.device_service.query_netbox_role_custom_fields")
    def test_parse_webhook_create_netbox_47_selection_objects(self, role_mock):
        """Webhook create should unwrap NetBox >= 4.7 {value, label} hostgroups."""
        data = {
            "data": {
                "name": "sw1",
                "role": {"name": "Switch"},
                "custom_fields": {"zabbix_hostgroups": [{"value": "DevGroup", "label": "DevGroup"}]},
                "status": {"value": "active"},
            }
        }

        result = ds.parse_webhook_create(data)
        role_mock.assert_not_called()
        self.assertEqual(result.hostgroup, ["DevGroup"])

if __name__ == "__main__":
    unittest.main()
