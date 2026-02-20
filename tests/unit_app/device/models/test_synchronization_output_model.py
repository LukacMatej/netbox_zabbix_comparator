import unittest

from app.device.models.synchonization_output_model import SyncOutput


class SyncOutputModelTests(unittest.TestCase):
    def test_add_methods_and_str(self):
        out = SyncOutput()
        out.add_difference_output("d1")
        out.add_netbox_output("n1")
        out.add_zabbix_output("z1")

        self.assertEqual(out.synchronization_output_differences, ["d1"])
        self.assertEqual(out.synchronization_output_netbox, ["n1"])
        self.assertEqual(out.synchronization_output_zabbix, ["z1"])
        self.assertIn("d1", str(out))


if __name__ == "__main__":
    unittest.main()
