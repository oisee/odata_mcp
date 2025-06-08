#!/usr/bin/env python3
"""
Test to verify URL encoding fix for special characters in OData key values.
"""

import unittest
from odata_mcp_lib.client import ODataClient
from odata_mcp_lib.models import ODataMetadata, EntityType, EntityProperty, EntitySet


class TestURLEncoding(unittest.TestCase):
    """Test URL encoding for special characters in key values."""
    
    def setUp(self):
        """Set up test environment."""
        # Create minimal metadata for testing
        self.entity_type = EntityType(
            name="PROGRAM",
            properties=[
                EntityProperty(name="Program", type="Edm.String", nullable=False, is_key=True),
                EntityProperty(name="Title", type="Edm.String", nullable=True),
                EntityProperty(name="SourceCode", type="Edm.String", nullable=True)
            ],
            key_properties=["Program"]
        )
        
        self.entity_set = EntitySet(
            name="PROGRAMSet",
            entity_type="PROGRAM"
        )
        
        self.metadata = ODataMetadata(
            entity_types={"PROGRAM": self.entity_type},
            entity_sets={"PROGRAMSet": self.entity_set},
            service_url="https://example.com/odata/"
        )
        
        self.client = ODataClient(self.metadata, auth=None, verbose=True)
    
    def test_url_encoding_in_key_string(self):
        """Test that special characters in key values are properly URL encoded."""
        # Test the _build_key_string method directly
        test_cases = [
            # (input_key_value, expected_output)
            ("/IWFND/SUTIL_GW_CLIENT", "('%2FIWFND%2FSUTIL_GW_CLIENT')"),
            ("normal_program", "('normal_program')"),
            ("program with spaces", "('program%20with%20spaces')"),
            ("program/with/slashes", "('program%2Fwith%2Fslashes')"),
            ("program'with'quotes", "('program%27with%27quotes')"),  # Note: quotes are first escaped, then encoded
        ]
        
        for input_value, expected in test_cases:
            with self.subTest(input_value=input_value):
                key_values = {"Program": input_value}
                result = self.client._build_key_string(self.entity_type, key_values)
                self.assertEqual(result, expected, 
                    f"Failed for input '{input_value}': expected '{expected}', got '{result}'")
    
    def test_special_sap_program_names(self):
        """Test specific SAP program names that contain special characters."""
        sap_programs = [
            "/IWFND/SUTIL_GW_CLIENT",
            "/UI2/FLP_LAUNCHER",
            "/SAP/BC/REST/DEMO",
            "/IWBEP/CP_MGW_PUSH",
            "/IWCOR/CL_REST_HTTP_CLIENT"
        ]
        
        for program_name in sap_programs:
            with self.subTest(program_name=program_name):
                key_values = {"Program": program_name}
                result = self.client._build_key_string(self.entity_type, key_values)
                
                # The result should contain URL-encoded forward slashes
                self.assertIn("%2F", result, 
                    f"Forward slashes should be URL encoded in result: {result}")
                
                # The result should be properly quoted
                self.assertTrue(result.startswith("('") and result.endswith("')"),
                    f"Result should be properly quoted: {result}")


if __name__ == "__main__":
    unittest.main()