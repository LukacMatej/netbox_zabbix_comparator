"""Unit tests for address model behavior."""

import unittest

from app.device.models.address_model import Address


class AddressModelTests(unittest.TestCase):
    """Tests for string and dictionary conversion of Address."""

    def test_str_and_to_dict(self):
        """Address should format correctly in `str` and `to_dict` output."""
        address = Address("10.0.0.1", "switch.local")
        self.assertEqual(str(address), "10.0.0.1 switch.local")
        self.assertEqual(address.to_dict(), {"address": "10.0.0.1", "dns_name": "switch.local"})


if __name__ == "__main__":
    unittest.main()
