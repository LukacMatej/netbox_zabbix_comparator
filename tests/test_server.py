"""Tests for FastAPI routes and parser initialization in `server.py`."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from app.device.models.device_model import Device
from app.device.models.interface_model import Interface
from app.device.models.address_model import Address
from app.device.models.difference_model import DeviceDifference


def _device(name: str) -> Device:
    return Device(
        name=name,
        interfaces=[Interface("eth0", [Address("10.0.0.1", "host.local")], "", "1")],
        hostgroup="group",
        description="desc",
        templates=["tpl"],
        status="Active",
    )


class ServerRoutesTests(unittest.TestCase):
    """Route-level tests for compare and synchronization endpoints."""

    def setUp(self) -> None:
        """Create FastAPI test client."""
        self.client = TestClient(server.app)

    def test_root_route(self):
        """Root route returns success and renders template."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("NetBox and Zabbix", response.text)

    @patch("server.ct.compare", return_value=Exception("boom"))
    def test_run_compare_error(self, _compare):
        """Compare route returns 500 when compare service raises error output."""
        response = self.client.get("/RunCompare")
        self.assertEqual(response.status_code, 500)
        self.assertIn("boom", response.text)

    @patch("server.ds.uniform_output_text")
    @patch("server.ct.compare")
    def test_run_compare_success(self, compare_mock, uniform_mock):
        """Compare route returns rendered output for successful comparison."""
        nb = _device("nb")
        zb = _device("zb")
        diff = DeviceDifference(nb, zb, (["name"], ["status"]))
        compare_mock.return_value = ([diff], [nb], [zb])

        response = self.client.get("/RunCompare")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Differences", response.text)
        uniform_mock.assert_called_once()

    @patch("server.ds.uniform_output_text")
    @patch("server.ss.sync_netbox_zabbix_devices")
    @patch("server.ct.compare")
    def test_run_compare_sync_success(self, compare_mock, sync_mock, uniform_mock):
        """Sync route renders result and triggers synchronization service."""
        nb = _device("nb")
        zb = _device("zb")
        diff = DeviceDifference(nb, zb, (["name"], ["status"]))
        compare_mock.return_value = ([diff], [nb], [zb])
        sync_mock.return_value = type(
            "SyncOutputStub",
            (),
            {
                "synchronization_output_zabbix": ["zabbix"],
                "synchronization_output_differences": ["differences"],
                "synchronization_output_netbox": ["netbox"],
            },
        )()

        response = self.client.get("/RunCompareSync")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Synchronization output", response.text)
        sync_mock.assert_called_once()
        uniform_mock.assert_called_once()

    def test_parser_init_has_flags(self):
        """Parser exposes development/debug flags."""
        parser = server.parser_init()
        args = parser.parse_args(["--development", "--debug"])
        self.assertTrue(args.development)
        self.assertTrue(args.debug)


if __name__ == "__main__":
    unittest.main()
