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
    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_hostgroup_id_success(self, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {"result": [{"groupid": "24"}]}
        post_mock.return_value = response
        self.assertEqual(ss.find_hostgroup_id("HG"), 24)

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_template_ids_success(self, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {"result": [{"templateid": "101"}]}
        post_mock.return_value = response
        self.assertEqual(ss.find_template_ids("TPL"), 101)

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_find_zabbix_hostgroup_ids_create_if_missing(self, post_mock):
        first = Mock(status_code=200)
        first.text = "not found"
        first.json.return_value = {"result": []}
        second = Mock(status_code=200)
        second.text = "created"
        second.json.return_value = {"result": {"groupids": ["50"]}}
        post_mock.side_effect = [first, second]

        result = ss.find_zabbix_hostgroup_ids(["new-group"])
        self.assertEqual(result, [50])

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.find_zabbix_hostgroup_ids", return_value=[-1])
    def test_create_zabbix_device_hostgroup_error(self, _hostgroup_mock):
        out = SyncOutput()
        ss.create_zabbix_device(_device("r1"), out)
        self.assertTrue(any("not found" in item for item in out.synchronization_output_zabbix))

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    @patch("app.compare.service.synchronization_service.find_template_ids", return_value=200)
    @patch("app.compare.service.synchronization_service.find_zabbix_hostgroup_ids", return_value=[24])
    def test_create_zabbix_device_success(self, _hg_mock, _tpl_mock, post_mock):
        response = Mock(status_code=200)
        response.json.return_value = {"result": {"hostids": ["1"]}}
        post_mock.return_value = response

        out = SyncOutput()
        ss.create_zabbix_device(_device("r1"), out)
        self.assertTrue(any("created successfully" in item for item in out.synchronization_output_zabbix))

    @patch.dict("os.environ", {"ZABBIX_IP": "http://zb/", "ZABBIX_KEY": "k"}, clear=False)
    @patch("app.compare.service.synchronization_service.requests.post")
    def test_apply_differences_missing_hostid(self, post_mock):
        host_get = Mock(status_code=200)
        host_get.json.return_value = {"result": []}
        post_mock.return_value = host_get

        nb = _device("nb", "10.0.0.1", "nb.local")
        zb = _device("zb", "10.0.0.2", "zb.local")
        diff = DeviceDifference(nb, zb, (["name", "address"], []))
        out = SyncOutput()

        ss.apply_differences(diff, out)
        self.assertTrue(any("cannot update device" in item for item in out.synchronization_output_differences))

    @patch("app.compare.service.synchronization_service.apply_differences")
    @patch("app.compare.service.synchronization_service.create_zabbix_device")
    def test_sync_netbox_zabbix_devices(self, create_mock, apply_mock):
        nb = [_device("only-in-nb")]
        zb = [_device("different-name")]
        diff = [DeviceDifference(nb[0], zb[0], (["name"], []))]

        out = ss.sync_netbox_zabbix_devices(diff, nb, zb)
        self.assertIsInstance(out, SyncOutput)
        create_mock.assert_called_once()
        apply_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
