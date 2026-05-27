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
        """Should return None when ZABBIX_KEY or ZABBIX_URL not in environment."""
        result = vs.query_zabbix_for_host("test-host")

        self.assertIsNone(result)

    @patch("app.device.service.validator_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_URL": "http://zabbix"})
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
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_URL": "http://zabbix"})
    def test_returns_none_when_empty_result(self, post_mock):
        """Should return None when no hosts found."""
        response = Mock()
        response.json.return_value = {"result": []}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        result = vs.query_zabbix_for_host("nonexistent-host")

        self.assertIsNone(result)

    @patch("app.device.service.validator_service.requests.post")
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_URL": "http://zabbix"})
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
    @patch.dict("os.environ", {"ZABBIX_KEY": "key", "ZABBIX_URL": "http://zabbix"})
    def test_returns_none_on_request_exception(self, post_mock):
        """Should return None when network request fails."""
        post_mock.side_effect = requests.RequestException("Connection failed")

        result = vs.query_zabbix_for_host("test-host")

        self.assertIsNone(result)


class CheckItemsDependencyTests(unittest.TestCase):
    """Tests for check_items_dependency function."""

    def test_returns_true_when_no_host_result(self):
        """Should return True (safe) when no host result provided."""
        result = vs.check_items_dependency(None, {})

        self.assertTrue(result)

    def test_returns_true_when_not_dict(self):
        """Should return True (safe) when host result is not a dict."""
        result = vs.check_items_dependency("string", {})

        self.assertTrue(result)

    def test_returns_true_when_no_items(self):
        """Should return True (safe) when host has no items."""
        host = {"interfaces": [{"type": "1"}], "selectItems": []}

        result = vs.check_items_dependency(host, {})

        self.assertTrue(result)

    def test_returns_true_when_items_dont_require_interface(self):
        """Should return True (safe) when all items are interface-independent."""
        host = {
            "interfaces": [{"type": "1"}],
            "selectItems": [
                {"type": str(ItemTypes.ZABBIX_TRAPPER.value), "interfaceid": "1"},
                {"type": str(ItemTypes.CALCULATED.value)},
            ],
        }

        result = vs.check_items_dependency(host, {})

        self.assertTrue(result)

    def test_returns_false_when_snmp_item_bound_but_no_snmp_interface(self):
        """Should return False (unsafe) when SNMP item exists but no SNMP interface."""
        host = {
            "interfaces": [{"type": "1"}],  # Only Agent interface
            "selectItems": [
                {"type": str(ItemTypes.SNMP_AGENT.value), "interfaceid": "1"},
            ],
        }

        result = vs.check_items_dependency(host, {})

        self.assertFalse(result)

    def test_returns_false_when_ipmi_item_bound_but_no_ipmi_interface(self):
        """Should return False (unsafe) when IPMI item exists but no IPMI interface."""
        host = {
            "interfaces": [{"type": "2"}],  # Only SNMP interface
            "selectItems": [
                {"type": str(ItemTypes.IPMI_AGENT.value), "interfaceid": "1"},
            ],
        }

        result = vs.check_items_dependency(host, {})

        self.assertFalse(result)

    def test_returns_true_when_jmx_item_and_jmx_interface_present(self):
        """Should return True (safe) when required interface type is available."""
        host = {
            "interfaces": [{"type": "1"}, {"type": "4"}],  # Agent and JMX
            "selectItems": [
                {"type": str(ItemTypes.JMX_AGENT.value), "interfaceid": "1"},
            ],
        }

        result = vs.check_items_dependency(host, {})

        self.assertTrue(result)

    def test_returns_true_when_agent_item_no_interfaceid(self):
        """Should return True (safe) when item doesn't have interfaceid bound."""
        host = {
            "interfaces": [{"type": "2"}],  # Only SNMP interface
            "selectItems": [
                {"type": str(ItemTypes.ZABBIX_AGENT.value)},  # No interfaceid
            ],
        }

        result = vs.check_items_dependency(host, {})

        self.assertTrue(result)

    def test_mixed_items_with_dependencies(self):
        """Should handle mixed items with and without dependencies correctly."""
        host = {
            "interfaces": [{"type": "1"}],  # Only Agent interface
            "selectItems": [
                {"type": str(ItemTypes.ZABBIX_AGENT.value), "interfaceid": "1"},
                {"type": str(ItemTypes.CALCULATED.value)},  # No interface needed
                {"type": str(ItemTypes.DEPENDENT_ITEM.value)},  # No interface needed
            ],
        }

        result = vs.check_items_dependency(host, {})

        self.assertTrue(result)


class FindZabbixHostTests(unittest.TestCase):
    """Tests for find_zabbix_host function."""

    def test_returns_none_when_no_device_name(self):
        """Should return None when device name not in data."""
        data = {"data": {}}

        result = vs.find_zabbix_host(data)

        self.assertIsNone(result)

    def test_returns_none_when_query_fails(self):
        """Should return None when query_zabbix_for_host returns None."""
        data = {"data": {"name": "test-host"}}

        with patch("app.device.service.validator_service.query_zabbix_for_host", return_value=None):
            result = vs.find_zabbix_host(data)

        self.assertIsNone(result)

    def test_returns_none_when_items_depend_on_old_port(self):
        """Should return None when check_items_dependency returns False."""
        data = {"data": {"name": "test-host"}}
        zabbix_result = {
            "hostid": "10001",
            "interfaces": [{"type": "1"}],
            "selectItems": [{"type": str(ItemTypes.SNMP_AGENT.value), "interfaceid": "1"}],
        }

        with patch("app.device.service.validator_service.query_zabbix_for_host", return_value=zabbix_result):
            result = vs.find_zabbix_host(data)

        self.assertIsNone(result)

    def test_returns_validator_on_success(self):
        """Should return DeviceModelValidator instance on success."""
        data = {"data": {"name": "test-host"}}
        zabbix_result = {
            "hostid": "10001",
            "groups": [{"groupid": "10"}, {"groupid": "20"}],
            "parentTemplates": [{"templateid": "100"}],
            "interfaces": [{"type": "1", "interfaceid": "1"}],
            "selectItems": [{"type": "0", "interfaceid": "1"}],
        }

        with patch("app.device.service.validator_service.query_zabbix_for_host", return_value=zabbix_result):
            result = vs.find_zabbix_host(data)

        self.assertIsInstance(result, vs.DeviceModelValidator)
        self.assertEqual(result.hostid, "10001")
        self.assertEqual(result.groupids, ["10", "20"])
        self.assertEqual(result.templateids, ["100"])
        self.assertEqual(len(result.interfaces), 1)
        self.assertEqual(len(result.items), 1)


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

        with patch("app.device.service.validator_service.find_zabbix_host", return_value=None):
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

        with patch("app.device.service.validator_service.find_zabbix_host", return_value=validator):
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

        with patch("app.device.service.validator_service.find_zabbix_host", return_value=validator):
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

        with patch("app.device.service.validator_service.find_zabbix_host", return_value=validator):
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

        with patch("app.device.service.validator_service.find_zabbix_host", return_value=validator):
            result = vs.can_update_device(data)

        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()
