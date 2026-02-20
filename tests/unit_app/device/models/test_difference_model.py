import unittest

from app.device.models.address_model import Address
from app.device.models.device_model import Device
from app.device.models.difference_model import DeviceDifference
from app.device.models.interface_model import Interface


class DifferenceModelTests(unittest.TestCase):
    def test_init_and_str(self):
        nb = Device(
            "nb", [Interface("eth0", [Address("1.1.1.1", "nb")], "", "1")], "g", "", [], "Active"
        )
        zb = Device(
            "zb", [Interface("eth0", [Address("1.1.1.2", "zb")], "", "2")], "g", "", [], "Active"
        )
        diff = DeviceDifference(nb, zb, (["address"], ["name"]))

        self.assertEqual(diff.nb_device, nb)
        self.assertEqual(diff.zb_device, zb)
        self.assertEqual(diff.differences[0], ["address"])
        self.assertIn("address", str(diff))


if __name__ == "__main__":
    unittest.main()
