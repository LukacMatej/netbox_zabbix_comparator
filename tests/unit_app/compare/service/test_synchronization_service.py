"""Unit tests for synchronization service helper and sync routines."""

import unittest
from unittest.mock import Mock, patch

from app.compare.service import synchronization_service as ss
from app.device.models.address_model import Address
from app.device.models.device_model import Device
from app.device.models.difference_model import DeviceDifference
from app.device.models.interface_model import Interface
from app.device.models.synchonization_output_model import SyncOutput


def _device(name: str, address: str = "10.0.0.1", dns: str = "host.local") -> Device:
    return Device(
        name=name,
        interfaces=[Interface("eth0", [Address(address, dns)], "", "1")],
        hostgroup=[{"name": "HG"}],
        description="desc",
        templates=["TPL"],
        status="Active",
    )


class SynchronizationServiceTests(unittest.TestCase):
    """Behavior tests for hostgroup/template lookup and sync operations."""

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_hostgroup_id_success(self, post_mock):
        """Hostgroup ID should be parsed from successful API response."""
        response = Mock(status_code=200)
        response.json.return_value = {"result": [{"groupid": "24"}]}
        post_mock.return_value = response
        self.assertEqual(ss.find_hostgroup_id("HG"), 24)

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_template_ids_success(self, post_mock):
        """Template ID should be parsed from successful API response."""
        response = Mock(status_code=200)
        response.json.return_value = {"result": [{"templateid": "101"}]}
        post_mock.return_value = response
        self.assertEqual(ss.find_template_ids("TPL"), 101)

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_zabbix_hostgroup_ids_create_if_missing(self, post_mock):
        """Missing hostgroup should trigger create call and return new ID."""
        first = Mock(status_code=200)
        first.text = "not found"
        first.json.return_value = {"result": []}
        second = Mock(status_code=200)
        second.text = "created"
        second.json.return_value = {"result": {"groupids": ["50"]}}
        post_mock.side_effect = [first, second]

        result = ss.find_zabbix_hostgroup_ids(["new-group"])
        self.assertEqual(result, [50])

    @patch.dict(
        "os.environ",
        {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k", "ZABBIX_DEFAULT_HOSTGROUP": "DefaultHG"},
        clear=False,
    )
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_zabbix_hostgroup_ids_none_uses_default_hostgroup(self, post_mock):
        """None hostgroup input should resolve to env default hostgroup."""
        response = Mock(status_code=200)
        response.text = "found"
        response.json.return_value = {"result": [{"groupid": "24"}]}
        post_mock.return_value = response

        result = ss.find_zabbix_hostgroup_ids(None)
        self.assertEqual(result, [24])
        called_json = post_mock.call_args.kwargs["json"]
        self.assertEqual(called_json["params"]["filter"]["name"], ["DefaultHG"])

    @patch.dict(
        "os.environ",
        {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k", "ZABBIX_DEFAULT_HOSTGROUP": "DefaultHG"},
        clear=False,
    )
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_zabbix_hostgroup_ids_empty_list_uses_default_hostgroup(self, post_mock):
        """Empty hostgroup input should resolve to env default hostgroup."""
        response = Mock(status_code=200)
        response.text = "found"
        response.json.return_value = {"result": [{"groupid": "24"}]}
        post_mock.return_value = response

        result = ss.find_zabbix_hostgroup_ids([])
        self.assertEqual(result, [24])
        called_json = post_mock.call_args.kwargs["json"]
        self.assertEqual(called_json["params"]["filter"]["name"], ["DefaultHG"])

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_zabbix_hostgroup_ids_single_dict(self, post_mock):
        """Single hostgroup dictionary input should be accepted and resolved."""
        response = Mock(status_code=200)
        response.text = "found"
        response.json.return_value = {"result": [{"groupid": "24"}]}
        post_mock.return_value = response

        result = ss.find_zabbix_hostgroup_ids({"name": "HG"})
        self.assertEqual(result, [24])

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch(
        "app.compare.service.synchronization_service.find_zabbix_hostgroup_ids", return_value=[-1]
    )
    def test_create_zabbix_device_hostgroup_error(self, _hostgroup_mock):
        """Hostgroup lookup failure should append zabbix output error."""
        out = SyncOutput()
        ss.create_zabbix_device(_device("r1"), out)
        self.assertTrue(any("not found" in item for item in out.synchronization_output_zabbix))

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    @patch("app.compare.service.synchronization_service.find_template_ids", return_value=200)
    @patch(
        "app.compare.service.synchronization_service.find_zabbix_hostgroup_ids", return_value=[24]
    )
    def test_create_zabbix_device_success(self, _hg_mock, _tpl_mock, post_mock):
        """Successful create should append success message to zabbix output."""
        response = Mock(status_code=200)
        response.json.return_value = {"result": {"hostids": ["1"]}}
        post_mock.return_value = response

        out = SyncOutput()
        ss.create_zabbix_device(_device("r1"), out)
        self.assertTrue(
            any("created successfully" in item for item in out.synchronization_output_zabbix)
        )

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_apply_differences_missing_hostid(self, post_mock):
        """Missing hostid should prevent update and append difference output error."""
        host_get = Mock(status_code=200)
        host_get.json.return_value = {"result": []}
        post_mock.return_value = host_get

        nb = _device("nb", "10.0.0.1", "nb.local")
        zb = _device("zb", "10.0.0.2", "zb.local")
        diff = DeviceDifference(nb, zb, (["name", "address"], []))
        out = SyncOutput()

        ss.apply_differences(diff, out)
        self.assertTrue(
            any("cannot update device" in item for item in out.synchronization_output_differences)
        )

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.device_service.find_hostinterface_ids")
    @patch("app.compare.service.synchronization_service.find_template_ids", return_value=101)
    @patch(
        "app.compare.service.synchronization_service.find_zabbix_hostgroup_ids", return_value=[24]
    )
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_apply_differences_splits_host_and_interface_update(
        self, post_mock, _hostgroup_mock, _template_mock, interface_ids_mock
    ):
        """Host basic fields and interfaces should be updated via separate API methods."""
        host_get = Mock(status_code=200)
        host_get.json.return_value = {"result": [{"hostid": "9001"}]}

        # clear_templates = Mock(status_code=200)
        # clear_templates.json.return_value = {"result": {"hostids": ["9001"]}}

        interface_update = Mock(status_code=200)
        interface_update.json.return_value = {"result": {"interfaceids": ["77"]}}

        host_update = Mock(status_code=200)
        host_update.json.return_value = {"result": {"hostids": ["9001"]}}

        # post_mock.side_effect = [host_get, clear_templates, interface_update, host_update]
        post_mock.side_effect = [host_get, interface_update, host_update]
        interface_ids_mock.return_value = [77]

        nb = _device("nb", "10.0.0.1", "nb.local")
        zb = _device("zb", "10.0.0.2", "zb.local")
        diff = DeviceDifference(nb, zb, (["name", "address", "port_type"], []))
        out = SyncOutput()

        ss.apply_differences(diff, out)

        self.assertEqual(post_mock.call_count, 3)
        # clear_templates_payload = post_mock.call_args_list[1].kwargs["json"]
        interface_update_payload = post_mock.call_args_list[1].kwargs["json"]
        host_update_payload = post_mock.call_args_list[2].kwargs["json"]

        # self.assertEqual(clear_templates_payload["method"], "host.update")
        # self.assertIn("templates_clear", clear_templates_payload["params"])
        self.assertEqual(host_update_payload["method"], "host.update")
        self.assertNotIn("interfaces", host_update_payload["params"])
        self.assertEqual(interface_update_payload["method"], "hostinterface.update")
        self.assertEqual(interface_update_payload["params"][0]["interfaceid"], 77)
        self.assertTrue(
            any("updated successfully" in item for item in out.synchronization_output_differences)
        )

    @patch("app.compare.service.synchronization_service.apply_differences")
    @patch("app.compare.service.synchronization_service.create_zabbix_device")
    def test_sync_netbox_zabbix_devices(self, create_mock, apply_mock):
        """Sync routine should call create and apply functions when appropriate."""
        nb = [_device("only-in-nb")]
        zb = [_device("different-name")]
        diff = [DeviceDifference(nb[0], zb[0], (["name"], []))]

        out = ss.sync_netbox_zabbix_devices(diff, nb, zb)
        self.assertIsInstance(out, SyncOutput)
        create_mock.assert_called_once()
        apply_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
