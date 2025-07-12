#!/usr/bin/env python3
"""
Test to verify query parameter encoding fix for OData compatibility.
Specifically testing that spaces are encoded as %20 instead of + in filter parameters.
"""

import unittest
from unittest.mock import MagicMock, patch
from odata_mcp_lib.client import ODataClient, encode_query_params
from odata_mcp_lib.models import ODataMetadata, EntityType, EntityProperty, EntitySet


class TestQueryParamEncoding(unittest.TestCase):
    """Test query parameter encoding for OData compatibility."""
    
    def test_encode_query_params_function(self):
        """Test the encode_query_params helper function."""
        test_cases = [
            # (input_params, expected_output)
            ({"$filter": "Program eq 'TEST'"}, "$filter=Program%20eq%20%27TEST%27"),
            ({"$filter": "substringof('REST', Class) eq true"}, 
             "$filter=substringof%28%27REST%27%2C%20Class%29%20eq%20true"),
            ({"$top": 10}, "$top=10"),
            ({"$filter": "Program eq 'TEST'", "$top": 10}, 
             "$filter=Program%20eq%20%27TEST%27&$top=10"),
        ]
        
        for input_params, expected in test_cases:
            with self.subTest(input_params=input_params):
                result = encode_query_params(input_params)
                self.assertEqual(result, expected, 
                    f"Failed for input {input_params}: expected '{expected}', got '{result}'")
    
    def test_spaces_encoded_as_percent20(self):
        """Test that spaces are encoded as %20, not +."""
        params = {"$filter": "Program eq 'TEST PROGRAM'"}
        result = encode_query_params(params)
        
        # Should contain %20 for spaces
        self.assertIn("%20", result)
        # Should NOT contain + for spaces
        self.assertNotIn("+", result.replace("$top=", "").replace("$filter=", ""))
    
    def test_odata_filter_expressions(self):
        """Test encoding of common OData filter expressions."""
        test_filters = [
            "Program eq 'TEST PROGRAM'",
            "substringof('REST HTTP CLIENT', Class) eq true",
            "startswith(Program, '/IWFND/') eq true",
            "Program eq '/SAP/BC/REST/DEMO'",
            "contains(Title, 'Test Program') eq true"
        ]
        
        for filter_expr in test_filters:
            with self.subTest(filter_expr=filter_expr):
                params = {"$filter": filter_expr}
                result = encode_query_params(params)
                
                # Verify spaces are encoded as %20
                if " " in filter_expr:
                    self.assertIn("%20", result, 
                        f"Spaces should be encoded as %20 in: {result}")
                
                # Verify no + characters in the encoded result (except in parameter names)
                encoded_value = result.split("=", 1)[1] if "=" in result else result
                self.assertNotIn("+", encoded_value, 
                    f"Should not contain + characters in encoded value: {encoded_value}")


if __name__ == "__main__":
    unittest.main()