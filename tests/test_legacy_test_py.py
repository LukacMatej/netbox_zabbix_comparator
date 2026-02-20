import unittest

import test as legacy


class LegacyTestPyCoverage(unittest.TestCase):
    def test_core_helpers(self):
        self.assertEqual(legacy.format_nb_status("Active"), "active")
        self.assertEqual(legacy.map_port_type("SNMP"), "2")
        self.assertEqual(legacy.normalize_status("0"), "Active")

    def test_device_payload_builders(self):
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
