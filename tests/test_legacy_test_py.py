"""Regression tests for legacy helpers in `test.py`."""

from importlib import util
from pathlib import Path
import unittest


def _load_legacy_module():
    module_path = Path(__file__).resolve().parents[1] / "test.py"
    spec = util.spec_from_file_location("legacy_test_module", module_path)
    module = util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


legacy = _load_legacy_module()


class LegacyTestPyCoverage(unittest.TestCase):
    """Coverage tests for legacy utility and payload builders."""

    def test_core_helpers(self):
        """Validate status and port-type helper outputs."""
        self.assertEqual(legacy.format_nb_status("Active"), "active")
        self.assertEqual(legacy.map_port_type("SNMP"), "2")
        self.assertEqual(legacy.normalize_status("0"), "Active")

    def test_device_payload_builders(self):
        """Ensure legacy device payload builders generate expected structures."""
        address = legacy.Address("10.0.0.1/24", "r1.local")
        interface = legacy.Interface("eth0", [address], "", "SNMP")
        device = legacy.Device("r1", [interface], ["g1"], "desc", ["tpl1"], "Active")

        create_payload = device.create_data_zabbix([1], [10])
        update_payload = device.update_data_zabbix("99", "88", [1], [10])

        self.assertEqual(create_payload["method"], "host.create")
        self.assertEqual(update_payload["method"], "host.update")
        self.assertEqual(update_payload["params"]["hostid"], "99")


if __name__ == "__main__":
    unittest.main()
