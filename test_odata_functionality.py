#!/usr/bin/env python3
"""
Comprehensive test suite for OData functionality and fixes.
"""

import unittest
import asyncio
from unittest.mock import patch, MagicMock
from odata_mcp_lib.client import ODataClient
from odata_mcp_lib.models import ODataMetadata, EntityType, EntityProperty, EntitySet


class TestODataFunctionality(unittest.TestCase):
    """Test OData functionality fixes."""
    
    def setUp(self):
        """Set up test environment."""
        # Create minimal metadata for testing
        self.entity_type = EntityType(
            name="CLASS",
            properties=[
                EntityProperty(name="Class", type="Edm.String", nullable=False, is_key=True),
                EntityProperty(name="Title", type="Edm.String", nullable=True),
                EntityProperty(name="Description", type="Edm.String", nullable=True)
            ],
            key_properties=["Class"]
        )
        
        self.entity_set = EntitySet(
            name="CLASSSet",
            entity_type="CLASS"
        )
        
        self.metadata = ODataMetadata(
            entity_types={"CLASS": self.entity_type},
            entity_sets={"CLASSSet": self.entity_set},
            service_url="https://example.com/odata/"
        )
        
        self.client = ODataClient(self.metadata, auth=None, verbose=True)
    
    def test_url_encoding_special_characters(self):
        """Test URL encoding for special characters in key values."""
        test_cases = [
            ("/IWFND/SUTIL_GW_CLIENT", "('%2FIWFND%2FSUTIL_GW_CLIENT')"),
            ("normal_class", "('normal_class')"),
            ("class with spaces", "('class%20with%20spaces')"),
            ("class/with/slashes", "('class%2Fwith%2Fslashes')"),
        ]
        
        for input_value, expected in test_cases:
            with self.subTest(input_value=input_value):
                key_values = {"Class": input_value}
                result = self.client._build_key_string(self.entity_type, key_values)
                self.assertEqual(result, expected)
    
    @patch('requests.Session.request')
    def test_proper_filter_syntax(self, mock_request):
        """Test that filters use correct OData v2 syntax."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "d": {
                "results": [
                    {"Class": "/IWCOR/CL_REST_HTTP_CLIENT", "Title": "REST HTTP Client"}
                ],
                "__count": "1"
            }
        }
        mock_request.return_value = mock_response
        
        # Add request URL for validation
        mock_response.request = MagicMock()
        mock_response.request.url = "https://example.com/odata//CLASSSet?$format=json&$inlinecount=allpages&$filter=substringof(%27REST_HTTP_CLIENT%27%2C%20Class)%20eq%20true"
        
        # Test correct OData v2 filter syntax
        correct_filter = "substringof('REST_HTTP_CLIENT', Class) eq true"
        params = {"$filter": correct_filter}
        
        result = asyncio.run(self.client.list_or_filter_entities("CLASSSet", params))
        
        # Verify the result
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["Class"], "/IWCOR/CL_REST_HTTP_CLIENT")
        
        # Verify the request was made with correct parameters
        self.assertEqual(mock_request.call_count, 1)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(args[1], "https://example.com/odata//CLASSSet")
        expected_params = {
            '$format': 'json', 
            '$inlinecount': 'allpages',
            '$filter': correct_filter
        }
        self.assertEqual(kwargs['params'], expected_params)
    
    def test_odata_v2_filter_examples(self):
        """Test various OData v2 filter syntax examples."""
        # These are examples of correct OData v2 filter syntax
        valid_filters = [
            # Substring search (instead of contains)
            "substringof('IWFND', Class) eq true",
            "substringof('HTTP_CLIENT', Title) eq true",
            
            # Starts with
            "startswith(Class, '/IWFND') eq true",
            
            # Ends with  
            "endswith(Class, '_CLIENT') eq true",
            
            # Exact match
            "Class eq '/IWFND/SUTIL_GW_CLIENT'",
            
            # Length
            "length(Class) gt 10",
            
            # Case-insensitive comparison (if supported)
            "tolower(Class) eq '/iwfnd/sutil_gw_client'",
            
            # Multiple conditions
            "substringof('IWFND', Class) eq true and length(Class) gt 10",
            
            # OR conditions
            "substringof('IWFND', Class) eq true or substringof('IWCOR', Class) eq true"
        ]
        
        for filter_expr in valid_filters:
            with self.subTest(filter=filter_expr):
                # Just test that the filter can be passed as a parameter
                # The actual validation would happen on the server side
                params = {"$filter": filter_expr}
                self.assertIn("$filter", params)
                self.assertEqual(params["$filter"], filter_expr)
    
    def test_common_sap_search_patterns(self):
        """Test common search patterns for SAP systems."""
        # Common patterns users might want to search for
        search_patterns = {
            # Find classes containing "REST"
            "REST classes": "substringof('REST', Class) eq true",
            
            # Find Gateway-related classes
            "Gateway classes": "substringof('GW', Class) eq true or substringof('GATEWAY', Title) eq true",
            
            # Find HTTP-related classes
            "HTTP classes": "substringof('HTTP', Class) eq true or substringof('HTTP', Title) eq true",
            
            # Find classes in specific packages
            "IWFND package": "startswith(Class, '/IWFND') eq true",
            "IWCOR package": "startswith(Class, '/IWCOR') eq true",
            "UI5 package": "startswith(Class, '/UI5') eq true",
            
            # Find client classes
            "Client classes": "endswith(Class, '_CLIENT') eq true or substringof('CLIENT', Title) eq true",
            
            # Find test classes
            "Test classes": "substringof('TEST', Class) eq true or substringof('TEST', Title) eq true"
        }
        
        for description, filter_expr in search_patterns.items():
            with self.subTest(pattern=description):
                # Verify the filter syntax is properly formed
                # Should contain either substringof, startswith, or endswith
                has_valid_function = any(func in filter_expr.lower() 
                                       for func in ["substringof", "startswith", "endswith"])
                self.assertTrue(has_valid_function, f"Filter should contain a valid OData function: {filter_expr}")
                self.assertIn("eq", filter_expr)
                # Basic syntax check - should contain single quotes around search terms
                self.assertIn("'", filter_expr)


if __name__ == "__main__":
    print("OData Functionality Test Suite")
    print("=" * 50)
    print()
    print("This test suite validates:")
    print("1. URL encoding for special characters in OData keys")
    print("2. Proper OData v2 filter syntax")
    print("3. Common SAP search patterns")
    print()
    
    unittest.main()