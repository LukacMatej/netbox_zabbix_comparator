"""Unit tests for device validator service."""

import unittest
import json
from unittest.mock import Mock, patch
import requests

from app.device.service import validator_service as vs
from app.enums.item_types import ItemTypes


class DeviceModelValidatorTests(unittest.TestCase):
    """Tests for DeviceModelValidator class."""

    def test_init_with_all_parameters(self):
        """DeviceModelValidator should initialize with all parameters correctly."""
        groupids = ["10", "20"]
        templateids = ["100", "200"]
        interfaces = [{"type": "1", "interfaceid": "1"}]
        items = [{"type": "0", "interfaceid": "1"}]

        validator = vs.DeviceModelValidator("hostid1", groupids, templateids, interfaces, items)

        self.assertEqual(validator.hostid, "hostid1")
        self.assertEqual(validator.groupids, groupids)
        self.assertEqual(validator.templateids, templateids)
        self.assertEqual(validator.interfaces, interfaces)
        self.assertEqual(validator.items, items)

    def test_init_with_none_interfaces_and_items(self):
        """DeviceModelValidator should handle None interfaces and items gracefully."""
        validator = vs.DeviceModelValidator("hostid1", ["10"], ["100"], None, None)

        self.assertEqual(validator.interfaces, [])
        self.assertEqual(validator.items, [])

    def test_get_interface_types(self):
        """get_interface_types should return all unique interface types."""
        interfaces = [
            {"type": "1", "interfaceid": "1"},
            {"type": "2", "interfaceid": "2"},
            {"type": "1", "interfaceid": "3"},
        ]
        validator = vs.DeviceModelValidator("hostid1", [], [], interfaces)

        result = validator.get_interface_types()

        self.assertEqual(result, {"1", "2"})

    def test_get_interface_types_empty(self):
        """get_interface_types should return empty set when no interfaces."""
        validator = vs.DeviceModelValidator("hostid1", [], [], [])

        result = validator.get_interface_types()

        self.assertEqual(result, set())

    def test_get_item_types(self):
        """get_item_types should return all unique item type IDs."""
        items = [
            {"type": "0", "interfaceid": "1"},  # ZABBIX_AGENT
            {"type": "2", "interfaceid": "2"},  # SNMP_TRAP
            {"type": "0", "interfaceid": "3"},  # ZABBIX_AGENT
        ]
        validator = vs.DeviceModelValidator("hostid1", [], [], [], items)

        result = validator.get_item_types()

        self.assertEqual(result, {0, 2})

    def test_get_item_types_empty(self):
        """get_item_types should return empty set when no items."""
        validator = vs.DeviceModelValidator("hostid1", [], [], [])

        result = validator.get_item_types()

        self.assertEqual(result, set())


class QueryZabbixForHostTests(unittest.TestCase):
    """Tests for query_zabbix_for_host function."""

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_when_no_env_variables(self):
        """Should return None when ZABBIX_KEY or ZABBIX_IP not in environment."""
        result = vs.query_zabbix_for_host("test-host")

        self.assertIsNone(result)

    @patch("app.device.service.validator_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_IP": "http://zabbix"})
    def test_returns_first_result_on_success(self, post_mock):
        """Should return the first host result when API call succeeds."""
        response = Mock()
        response.json.return_value = {
            "result": [
                {"hostid": "10001", "host": "test-host"},
                {"hostid": "10002", "host": "other-host"},
            ]
        }
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        result = vs.query_zabbix_for_host("test-host")

        self.assertEqual(result["hostid"], "10001")
        self.assertEqual(result["host"], "test-host")

    @patch("app.device.service.validator_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_IP": "http://zabbix"})
    def test_returns_none_when_empty_result(self, post_mock):
        """Should return None when no hosts found."""
        response = Mock()
        response.json.return_value = {"result": []}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        result = vs.query_zabbix_for_host("nonexistent-host")

        self.assertIsNone(result)

    @patch("app.device.service.validator_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_IP": "http://zabbix"})
    def test_returns_none_on_error_in_response(self, post_mock):
        """Should return None when API returns an error."""
        response = Mock()
        response.json.return_value = {
            "error": "Invalid method",
            "result": [],
        }
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        result = vs.query_zabbix_for_host("test-host")

        self.assertIsNone(result)

    @patch("app.device.service.validator_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_IP": "http://zabbix"})
    def test_returns_none_on_request_exception(self, post_mock):
        """Should return None when network request fails."""
        post_mock.side_effect = requests.RequestException("Connection failed")

        result = vs.query_zabbix_for_host("test-host")

        self.assertIsNone(result)


class MapPortTypesTests(unittest.TestCase):
    """Tests for map_port_types."""

    def test_maps_names_and_codes(self):
        """Both port type names and their numeric codes should map to the same set."""
        self.assertEqual(vs.map_port_types(["Agent", "2"]), {"1", "2"})

    def test_returns_none_for_unknown_port_type(self):
        """An unrecognized port type should make the whole mapping fail."""
        self.assertIsNone(vs.map_port_types(["Agent", "bogus"]))


class QueryZabbixTemplateItemsTests(unittest.TestCase):
    """Tests for query_zabbix_template_items."""

    def test_returns_empty_list_for_no_template_names(self):
        """No template names means nothing to look up."""
        self.assertEqual(vs.query_zabbix_template_items([]), [])

    def test_resolves_template_names_to_items(self):
        """Should resolve template names to IDs, then fetch their items."""
        with patch(
            "app.device.service.validator_service._zabbix_post",
            side_effect=[
                [{"templateid": "500", "host": "APC UPS by SNMP"}],
                [{"itemid": "1", "name": "SNMP item", "type": "20"}],
            ],
        ) as post_mock:
            result = vs.query_zabbix_template_items(["APC UPS by SNMP"])

        self.assertEqual(result, [{"itemid": "1", "name": "SNMP item", "type": "20"}])
        self.assertEqual(post_mock.call_args_list[0].args[0], "template.get")
        self.assertEqual(post_mock.call_args_list[1].args[0], "item.get")
        self.assertEqual(post_mock.call_args_list[1].args[1]["templateids"], ["500"])

    def test_returns_empty_list_when_template_not_found(self):
        """Should return [] when no matching template exists in Zabbix."""
        with patch("app.device.service.validator_service._zabbix_post", return_value=[]):
            result = vs.query_zabbix_template_items(["Nonexistent Template"])

        self.assertEqual(result, [])


class CheckNewPortTypeCompatibilityTests(unittest.TestCase):
    """Tests for check_new_port_type_compatibility function."""

    def test_returns_true_when_no_host_result(self):
        """Should return True when no host result is provided."""
        result = vs.check_new_port_type_compatibility(None, ["Agent"])

        self.assertTrue(result)

    def test_returns_true_when_items_do_not_require_interfaces(self):
        """Should return True when all existing items are interface-independent."""
        host = {
            "items": [
                {"type": str(ItemTypes.ZABBIX_TRAPPER.value)},
                {"type": str(ItemTypes.CALCULATED.value)},
            ],
        }

        result = vs.check_new_port_type_compatibility(host, ["SNMP"])

        self.assertTrue(result)

    def test_returns_false_when_required_interface_missing_from_new_port_types(self):
        """Should return False when an existing item needs an interface not in the new types."""
        host = {
            "items": [
                {"type": str(ItemTypes.SNMP_AGENT.value), "name": "SNMP Item"},
            ],
        }

        result = vs.check_new_port_type_compatibility(host, ["Agent"])

        self.assertFalse(result)

    def test_returns_true_when_all_required_interfaces_are_present(self):
        """Should return True when the new port types include every required interface."""
        host = {
            "items": [
                {"type": str(ItemTypes.JMX_AGENT.value), "name": "JMX Item"},
                {"type": str(ItemTypes.ZABBIX_AGENT.value), "name": "Agent Item"},
            ],
        }

        result = vs.check_new_port_type_compatibility(host, ["Agent", "JMX"])

        self.assertTrue(result)


class FindZabbixHostTests(unittest.TestCase):
    """Tests for find_zabbix_host function."""

    def test_returns_none_when_no_device_name(self):
        """Should return None when device name not in data."""
        data = {"data": {}}

        result = vs.find_zabbix_host(data)

        self.assertEqual(result, (None, None))

    def test_returns_none_when_query_fails(self):
        """Should return None when query_zabbix_for_host returns None."""
        data = {"data": {"name": "test-host"}}

        with patch("app.device.service.validator_service.query_zabbix_for_host", return_value=None):
            result = vs.find_zabbix_host(data)

        self.assertEqual(result, (None, None))

    def test_returns_validator_when_host_found(self):
        """Should return the validator even when items exist on the host."""
        data = {"data": {"name": "test-host"}}
        zabbix_result = {
            "hostid": "10001",
            "interfaces": [{"type": "1"}],
            "items": [{"type": str(ItemTypes.SNMP_AGENT.value), "interfaceid": "1"}],
        }

        with patch("app.device.service.validator_service.query_zabbix_for_host", return_value=zabbix_result):
            result = vs.find_zabbix_host(data)

        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], vs.DeviceModelValidator)
        self.assertEqual(result[1], zabbix_result)

    def test_returns_validator_on_success(self):
        """Should return DeviceModelValidator instance on success."""
        data = {"data": {"name": "test-host"}}
        zabbix_result = {
            "hostid": "10001",
            "hostgroups": [{"groupid": "10"}, {"groupid": "20"}],
            "parentTemplates": [{"templateid": "100"}],
            "interfaces": [{"type": "1", "interfaceid": "1"}],
            "items": [{"type": "0", "interfaceid": "1"}],
        }

        with patch("app.device.service.validator_service.query_zabbix_for_host", return_value=zabbix_result):
            result: tuple[vs.DeviceModelValidator | None, dict | None] = vs.find_zabbix_host(data)

        device_model: vs.DeviceModelValidator | None = result[0]
        zabbix_data: dict | None = result[1]
        self.assertIsNotNone(result)
        self.assertIsInstance(result, tuple)
        self.assertIsInstance(device_model, vs.DeviceModelValidator)
        self.assertIsInstance(zabbix_data, dict)
        self.assertEqual(device_model.hostid, "10001")
        self.assertEqual(device_model.groupids, ["10", "20"])
        self.assertEqual(device_model.templateids, ["100"])
        self.assertEqual(device_model.interfaces, [{"type": "1", "interfaceid": "1"}])
        self.assertEqual(device_model.items, [{"type": "0", "interfaceid": "1"}])
        self.assertEqual(zabbix_data, zabbix_result)


class CanUpdateDeviceTests(unittest.TestCase):
    """Tests for can_update_device function."""

    def test_returns_valid_when_no_custom_fields(self):
        """Should return valid when no custom fields in update."""
        data = {"data": {}}

        result = vs.can_update_device(data)

        self.assertTrue(result["valid"])
        self.assertIn("No custom fields", result["message"])

    def test_returns_valid_when_updating_templates(self):
        """Should return valid when update includes templates."""
        data = {
            "data": {
                "custom_fields": {
                    "zabbix_templates": ["template1", "template2"],
                    "zabbix_port_type": "Agent",
                }
            }
        }

        result = vs.can_update_device(data)

        self.assertTrue(result["valid"])

    def test_returns_valid_when_updating_hostgroups(self):
        """Should return valid when update includes hostgroups."""
        data = {
            "data": {
                "custom_fields": {
                    "zabbix_hostgroups": ["group1", "group2"],
                    "zabbix_port_type": "Agent",
                }
            }
        }

        result = vs.can_update_device(data)

        self.assertTrue(result["valid"])

    def test_returns_valid_when_no_port_type_change(self):
        """Should return valid when no port type in update."""
        data = {
            "data": {
                "custom_fields": {
                    "zabbix_port_type": None,
                }
            }
        }

        result = vs.can_update_device(data)

        self.assertTrue(result["valid"])

    def test_returns_valid_when_zabbix_host_not_found(self):
        """Should return valid when Zabbix host not found."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": "SNMP"},
            }
        }

        with patch("app.device.service.validator_service.find_zabbix_host", return_value=(None, None)):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])
        self.assertIn("not found", result["message"])

    def test_returns_valid_when_port_type_not_changing(self):
        """Should return valid when port type is not actually changing."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": "Agent"},
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}],  # Agent interface already exists
            [],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])
        self.assertIn("not changing", result["message"])

    def test_returns_valid_when_port_type_change_safe(self):
        """Should return valid when port type change has no dependent items."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": "SNMP"},
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}],  # Only Agent interface
            [
                {"type": str(ItemTypes.ZABBIX_TRAPPER.value)},  # No interface required
                {"type": str(ItemTypes.CALCULATED.value)},  # No interface required
            ],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])
        self.assertIn("safe", result["message"])

    def test_port_type_mapping_agent(self):
        """Should correctly map 'Agent' port type to '1'."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": "Agent"},
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "2"}],  # SNMP interface
            [],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])

    def test_port_type_mapping_numeric_snmp(self):
        """Should correctly map numeric '2' port type to SNMP."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": "2"},
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "2"}],  # SNMP interface
            [],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])

    def test_returns_invalid_when_new_port_types_do_not_cover_existing_item_interfaces(self):
        """Should return invalid when existing items need interfaces not in the new port types."""
        data = {
            "data": {
                "name": "apc",
                "custom_fields": {"zabbix_port_type": "Agent"},
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}, {"type": "2"}],
            [
                {
                    "itemid": "100",
                    "name": "SNMP Item",
                    "type": str(ItemTypes.SNMP_AGENT.value),
                }
            ],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        self.assertFalse(result["valid"])
        self.assertIn("incompatible", result["message"].lower())

    def test_handles_port_type_as_list_from_netbox(self):
        """Should extract port type from list sent by Netbox custom field.

        Netbox sends custom field values as lists (even single values).
        This test ensures the validator handles ['2'] correctly.
        """
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": ["2"]},  # List from Netbox
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}],  # Only Agent interface
            [
                {"type": str(ItemTypes.ZABBIX_TRAPPER.value)},  # No interface required
            ],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        # Should extract '2' from ['2'] and validate it as SNMP port type change
        self.assertTrue(result["valid"])
        self.assertIn("port type", result["message"].lower())

    def test_handles_empty_port_type_list(self):
        """Should handle empty port type list from Netbox."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": []},  # Empty list
            }
        }

        result = vs.can_update_device(data)

        # Empty list means no port type change
        self.assertTrue(result["valid"])
        self.assertIn("no port type", result["message"].lower())

    def test_handles_multiple_port_types_validates_all(self):
        """Should validate all port types when list has multiple items.

        When Netbox sends multiple port types like ['1', '2'], we should validate
        that atleast one of the existing interfaces matches each required type.
        """
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": ["1", "2"]},  # Multiple items: Agent and SNMP
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "3"}],  # Only IPMI interface exists
            [
                {"type": str(ItemTypes.ZABBIX_TRAPPER.value)},
                {"type": str(ItemTypes.SIMPLE_CHECK.value)},
            ],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        # Should validate both port types and report success for all
        self.assertTrue(result["valid"])
        self.assertIn("all", result["message"].lower())
        self.assertIn("2", result["message"])  # Should mention 2 port types

    def test_rejects_when_one_port_type_incompatible(self):
        """Should reject if ANY of the port types is incompatible with existing items.

        When validating multiple port types like ['1', '2'], if one (e.g., '2' for SNMP)
        is incompatible with items requiring interface '1' (Agent), the entire update
        should be rejected.
        """
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_port_type": ["2", "3"]},  # SNMP and IPMI
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}, {"type": "2"}],
            [
                {"type": str(ItemTypes.ZABBIX_AGENT.value), "name": "Agent Item"},
            ],
        )

        with patch(
            "app.device.service.validator_service.find_zabbix_host", return_value=(validator, {"items": validator.items})
        ):
            result = vs.can_update_device(data)

        # Should reject because the new types do not include interface 1
        self.assertFalse(result["valid"])
        self.assertIn("incompatible", result["message"].lower())

    def test_rejects_template_change_needing_interface_host_lacks(self):
        """Regression test for the veeam incident: a template-only change
        (zabbix_port_type absent from the update) must still be checked
        against the host's *current* interfaces. Previously any update with
        zabbix_templates but no zabbix_port_type was approved unconditionally,
        letting an SNMP-only template through onto an Agent-only host, which
        Zabbix then rejected at actual sync time."""
        data = {
            "data": {
                "name": "veeam",
                "custom_fields": {"zabbix_templates": ["APC UPS by SNMP"]},
            }
        }
        validator = vs.DeviceModelValidator(
            "10795",
            ["10"],
            ["100"],
            [{"type": "1"}],  # host only has an Agent interface
            [],
        )
        new_items = [
            {"name": "SNMP item", "type": str(ItemTypes.SNMP_AGENT.value)},
        ]

        with patch(
            "app.device.service.validator_service.find_zabbix_host",
            return_value=(validator, {"items": validator.items, "interfaces": validator.interfaces}),
        ), patch(
            "app.device.service.validator_service.query_zabbix_template_items",
            return_value=new_items,
        ):
            result = vs.can_update_device(data)

        self.assertFalse(result["valid"])
        self.assertIn("interface", result["message"].lower())

    def test_allows_template_change_compatible_with_existing_interfaces(self):
        """A template-only change should be approved when the new template's
        items are satisfied by the host's existing interfaces."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_templates": ["Remote Zabbix server health"]},
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}],  # Agent interface
            [],
        )
        new_items = [
            {"name": "Agent item", "type": str(ItemTypes.ZABBIX_AGENT.value)},
        ]

        with patch(
            "app.device.service.validator_service.find_zabbix_host",
            return_value=(validator, {"items": validator.items, "interfaces": validator.interfaces}),
        ), patch(
            "app.device.service.validator_service.query_zabbix_template_items",
            return_value=new_items,
        ):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])

    def test_hostgroups_only_change_skips_validation(self):
        """A hostgroups-only change (no port type, no templates) should never
        trigger a Zabbix compatibility check."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {"zabbix_hostgroups": ["group1", "group2"]},
            }
        }

        result = vs.can_update_device(data)

        self.assertTrue(result["valid"])
        self.assertIn("no port type", result["message"].lower())

    def test_combined_port_type_and_template_change_checks_both(self):
        """When both zabbix_port_type and zabbix_templates change together,
        the new template's items must be satisfied by the *new* port types,
        not the host's old ones."""
        data = {
            "data": {
                "name": "test-host",
                "custom_fields": {
                    "zabbix_port_type": ["2"],  # switching to SNMP
                    "zabbix_templates": ["SNMP Template"],
                },
            }
        }
        validator = vs.DeviceModelValidator(
            "10001",
            ["10"],
            ["100"],
            [{"type": "1"}],  # currently Agent only
            [],
        )
        new_items = [
            {"name": "SNMP item", "type": str(ItemTypes.SNMP_AGENT.value)},
        ]

        with patch(
            "app.device.service.validator_service.find_zabbix_host",
            return_value=(validator, {"items": validator.items, "interfaces": validator.interfaces}),
        ), patch(
            "app.device.service.validator_service.query_zabbix_template_items",
            return_value=new_items,
        ):
            result = vs.can_update_device(data)

        # New port types (SNMP) satisfy the new template's item, so this
        # should be valid even though the host's *current* interface is Agent.
        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()
