import unittest

from app.device.models.address_model import Address


class AddressModelTests(unittest.TestCase):
    def test_str_and_to_dict(self):
        address = Address("10.0.0.1", "switch.local")
        self.assertEqual(str(address), "10.0.0.1 switch.local")
        self.assertEqual(address.to_dict(), {"address": "10.0.0.1", "dns_name": "switch.local"})


if __name__ == "__main__":
    unittest.main()
