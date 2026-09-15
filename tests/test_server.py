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
        self.assertIn("NetBox Zabbix Comparison", response.text)

    @patch("server.ss.list_zabbix_hostgroups", return_value=["Netbox", "Servers"])
    def test_zabbix_hostgroups_success(self, _list_mock):
        """Hostgroups route renders the returned names into the dropdown partial."""
        response = self.client.get("/zabbix_hostgroups")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Netbox", response.text)
        self.assertIn("Servers", response.text)

    @patch("server.ss.list_zabbix_hostgroups", return_value="Zabbix IP or API key not set")
    def test_zabbix_hostgroups_error(self, _list_mock):
        """Hostgroups route renders the error message when the service call fails."""
        response = self.client.get("/zabbix_hostgroups")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Zabbix IP or API key not set", response.text)

    def test_select_hostgroup_success(self):
        """Selecting a hostgroup is accepted and acknowledged."""
        response = self.client.post("/select_hostgroup", json={"hostgroup": "Servers"})
        self.assertEqual(response.status_code, 200)

    def test_select_hostgroup_invalid_json(self):
        """A malformed body is rejected with a 400, matching the other POST routes."""
        response = self.client.post(
            "/select_hostgroup", content=b"not json", headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 400)

    @patch("server.ct.compare", return_value=Exception("boom"))
    def test_run_compare_error(self, _compare):
        """Compare route returns 500 when compare service raises error output."""
        response = self.client.get("/run_comparison")
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

        response = self.client.get("/run_comparison")
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

        response = self.client.get("/run_comparison_sync")
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


class DiffHtmlTests(unittest.TestCase):
    """Tests for the vim-diff-style character highlighting helper."""

    def test_identical_values_have_no_spans(self):
        """No highlighting is produced when both sides match."""
        old_html = server.diff_html("router-01", "router-01", "old")
        new_html = server.diff_html("router-01", "router-01", "new")
        self.assertEqual(old_html, "router-01")
        self.assertEqual(new_html, "router-01")
        self.assertNotIn("<span", old_html)
        self.assertNotIn("<span", new_html)

    def test_single_character_change_is_highlighted(self):
        """Only the differing character is wrapped, unchanged text stays bare."""
        old_html = server.diff_html("router-01A", "router-01B", "old")
        new_html = server.diff_html("router-01A", "router-01B", "new")
        self.assertEqual(old_html, 'router-01<span class="diff-old">A</span>')
        self.assertEqual(new_html, 'router-01<span class="diff-new">B</span>')

    def test_none_and_empty_inputs_do_not_error(self):
        """None is treated as an empty string on either side."""
        self.assertEqual(server.diff_html(None, "new-value", "new"),
                          '<span class="diff-new">new-value</span>')
        self.assertEqual(server.diff_html("old-value", None, "old"),
                          '<span class="diff-old">old-value</span>')
        self.assertEqual(server.diff_html(None, None, "old"), "")

    def test_values_are_html_escaped(self):
        """Special HTML characters in the values don't break the markup."""
        html = server.diff_html("A & <B>", "A & <B>!", "new")
        self.assertIn("&amp;", html)
        self.assertIn("&lt;B&gt;", html)
        self.assertNotIn("<B>", html)


class SafeIndexTests(unittest.TestCase):
    """Tests for the bounds-safe list accessor used for interface pairing."""

    def test_returns_item_in_range(self):
        self.assertEqual(server.safe_index(["a", "b"], 1), "b")

    def test_returns_none_out_of_range(self):
        self.assertIsNone(server.safe_index(["a"], 5))

    def test_returns_none_for_falsy_or_wrong_type_input(self):
        self.assertIsNone(server.safe_index([], 0))
        self.assertIsNone(server.safe_index(None, 0))


if __name__ == "__main__":
    unittest.main()
