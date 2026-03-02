"""Unit tests for compare service diff and orchestration logic."""

import unittest
from unittest.mock import patch

from app.compare.service import compare_service as cs
from app.device.models.address_model import Address
from app.device.models.device_model import Device
from app.device.models.interface_model import Interface


def _device(name: str, address: str, dns: str, port_type: str = "1") -> Device:
    return Device(
        name=name,
        interfaces=[Interface("eth0", [Address(address, dns)], "aa", port_type)],
        hostgroup="g",
        description="d",
        templates=["t"],
        status="Active",
    )


class CompareServiceTests(unittest.TestCase):
    """Tests for difference detection and compare flow."""

    def test_find_differences_identical(self):
        """Identical devices should return equal tag and no differences list."""
        nb = _device("r1", "10.0.0.1", "r1.local")
        zb = _device("r1", "10.0.0.1", "r1.local")

        tag, _, (different, same) = cs.find_differences(nb, zb)
        self.assertEqual(tag, 2)
        self.assertEqual(different, [])
        self.assertGreater(len(same), 0)

    def test_find_differences_name_and_address(self):
        """Different name/address should be listed in difference output."""
        nb = _device("r1", "10.0.0.1", "r1.local")
        zb = _device("r2", "10.0.0.2", "r2.local")

        tag, _, (different, _) = cs.find_differences(nb, zb)
        self.assertEqual(tag, 0)
        self.assertTrue(any("name (r1 != r2)" in item for item in different))
        self.assertTrue(any("address" in item for item in different))

    def test_compare_devices_lists(self):
        """Unmatched devices should be reported in source-specific lists."""
        nb1 = _device("n1", "10.0.0.1", "n1.local")
        nb2 = _device("n2", "10.0.0.2", "n2.local")
        zb1 = _device("z1", "10.0.0.9", "z1.local")

        different, nb_only, zb_only = cs.compare_devices([nb1, nb2], [zb1])
        self.assertEqual(different, [])
        self.assertEqual(len(nb_only), 2)
        self.assertEqual(len(zb_only), 1)
        self.assertIsInstance(zb_only, list)

    @patch("app.compare.service.compare_service.compare_devices", return_value=([], [], []))
    @patch("app.compare.service.compare_service.ds.map_port_type_device")
    @patch("app.compare.service.compare_service.ds.get_zb_devices")
    @patch("app.compare.service.compare_service.ds.get_nb_devices")
    def test_compare_success(self, get_nb_mock, get_zb_mock, map_mock, compare_devices_mock):
        """Compare orchestrator should map port types and delegate to compare_devices."""
        nb = [_device("n1", "10.0.0.1", "n1.local")]
        zb = [_device("z1", "10.0.0.2", "z1.local")]
        get_nb_mock.return_value = nb
        get_zb_mock.return_value = zb

        result = cs.compare("http://nb", "nk", "http://zb", "zk")
        self.assertEqual(result, ([], [], []))
        map_mock.assert_called_once_with(nb, zb)
        compare_devices_mock.assert_called_once_with(nb, zb)

    @patch("app.compare.service.compare_service.ds.get_nb_devices", return_value="boom")
    def test_compare_nb_error(self, _get_nb):
        """Compare should return Exception when NetBox retrieval returns an error string."""
        result = cs.compare("http://nb", "nk", "http://zb", "zk")
        self.assertIsInstance(result, Exception)


if __name__ == "__main__":
    unittest.main()
