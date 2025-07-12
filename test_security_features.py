#!/usr/bin/env python3
"""
Test to verify security features for HTTP transport.
"""

import unittest
import sys
from io import StringIO
from unittest.mock import patch
from odata_mcp import is_localhost_addr


class TestSecurityFeatures(unittest.TestCase):
    """Test security features for HTTP transport."""
    
    def test_is_localhost_addr_function(self):
        """Test the is_localhost_addr validation function."""
        test_cases = [
            # (input_addr, expected_result)
            ("localhost:8080", True),
            ("127.0.0.1:8080", True),
            ("::1:8080", True),
            ("[::1]:8080", True),
            (":8080", False),  # Binds to all interfaces
            ("0.0.0.0:8080", False),
            ("192.168.1.100:8080", False),
            ("example.com:8080", False),
            ("", True),  # Empty host defaults to localhost
            ("localhost", True),  # No port
            ("127.0.0.1", True),  # No port
        ]
        
        for input_addr, expected in test_cases:
            with self.subTest(input_addr=input_addr):
                result = is_localhost_addr(input_addr)
                self.assertEqual(result, expected, 
                    f"Failed for input '{input_addr}': expected {expected}, got {result}")
    
    def test_localhost_addresses_allowed(self):
        """Test that localhost addresses are considered safe."""
        safe_addresses = [
            "localhost:8080",
            "127.0.0.1:8080", 
            "::1:8080",
            "[::1]:8080",
        ]
        
        for addr in safe_addresses:
            with self.subTest(addr=addr):
                self.assertTrue(is_localhost_addr(addr), 
                    f"Address '{addr}' should be considered localhost")
    
    def test_non_localhost_addresses_blocked(self):
        """Test that non-localhost addresses are blocked."""
        unsafe_addresses = [
            ":8080",  # Binds to all interfaces
            "0.0.0.0:8080",
            "192.168.1.100:8080",
            "10.0.0.1:8080",
            "example.com:8080",
            "8.8.8.8:8080",
        ]
        
        for addr in unsafe_addresses:
            with self.subTest(addr=addr):
                self.assertFalse(is_localhost_addr(addr), 
                    f"Address '{addr}' should be blocked for security")


if __name__ == "__main__":
    unittest.main()