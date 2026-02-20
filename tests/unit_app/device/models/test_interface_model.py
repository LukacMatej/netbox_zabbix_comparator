"""Unit tests for interface model representation."""

import unittest

from app.device.models.address_model import Address
from app.device.models.interface_model import Interface


class InterfaceModelTests(unittest.TestCase):
    """Tests for interface string formatting."""

    def test_str_contains_core_values(self):
        """Interface string should include name, MAC and port type."""
        interface = Interface("eth0", [Address("10.0.0.2", "host")], "aa:bb:cc:dd:ee:ff", "2")
        text = str(interface)
        self.assertIn("eth0", text)
        self.assertIn("aa:bb:cc:dd:ee:ff", text)
        self.assertIn("2", text)


if __name__ == "__main__":
    unittest.main()
