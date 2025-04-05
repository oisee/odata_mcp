#!/usr/bin/env python3
"""
Unit tests for OData MCP Wrapper.

This test suite uses the credentials and service URL from the .env file:
- ODATA_URL: URL to an OData v2 service
- ODATA_USER: Basic auth username
- ODATA_PASS: Basic auth password
"""

import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import requests
from io import StringIO

# Import the module to test
import odata_mcp
from odata_mcp import MetadataParser, ODataClient, ODataMCPBridge, ODataMetadata, EntityType, EntityProperty, EntitySet, FunctionImport

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class TestEnvironmentSetup(unittest.TestCase):
    """Test environment variables are properly set."""
    
    def test_environment_variables(self):
        """Verify that required environment variables are set."""
        service_url = os.getenv("ODATA_URL")
        self.assertIsNotNone(service_url, "ODATA_URL environment variable is not set")
        self.assertTrue(service_url.strip(), "ODATA_URL is empty")
        
        # Check if auth credentials are available
        username = os.getenv("ODATA_USER")
        password = os.getenv("ODATA_PASS")
        
        if username or password:
            print(f"Authentication credentials found for user: {username}")
        else:
            print("No authentication credentials found, tests will run without authentication")


class TestMetadataParser(unittest.TestCase):
    """Tests for the MetadataParser class."""
    
    def setUp(self):
        """Set up test environment for each test."""
        self.service_url = os.getenv("ODATA_URL")
        self.username = os.getenv("ODATA_USER")
        self.password = os.getenv("ODATA_PASS")
        
        self.auth = None
        if self.username and self.password:
            self.auth = (self.username, self.password)
    
    @patch('odata_mcp.MetadataParser._parse_entity_types')
    @patch('odata_mcp.MetadataParser._parse_entity_sets')
    @patch('odata_mcp.MetadataParser._parse_function_imports')
    @patch('requests.Session.get')
    def test_parse_metadata_success(self, mock_get, mock_parse_functions, mock_parse_sets, mock_parse_types):
        """Test successful metadata parsing with mocked responses."""
        # Set up mock return values
        mock_parse_types.return_value = {"TestEntity": EntityType(name="TestEntity", properties=[])}
        mock_parse_sets.return_value = {"TestSet": EntitySet(name="TestSet", entity_type="TestEntity")}
        mock_parse_functions.return_value = {"TestFunction": FunctionImport(name="TestFunction")}
        
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"><edmx:DataServices><Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm"></Schema></edmx:DataServices></edmx:Edmx>'
        mock_get.return_value = mock_response
        
        # Create parser and parse metadata
        parser = MetadataParser(self.service_url, self.auth, verbose=True)
        metadata = parser.parse()
        
        # Verify the metadata structure
        # The service_url might have trailing slash removed by the MetadataParser
        self.assertTrue(metadata.service_url.rstrip('/') == self.service_url.rstrip('/'), 
                        f"Expected {self.service_url.rstrip('/')} but got {metadata.service_url.rstrip('/')}")
        self.assertIn("TestEntity", metadata.entity_types)
        self.assertIn("TestSet", metadata.entity_sets)
        self.assertIn("TestFunction", metadata.function_imports)
        
        # Verify that methods were called
        mock_get.assert_called_once()
        mock_parse_types.assert_called_once()
        mock_parse_sets.assert_called_once()
        mock_parse_functions.assert_called_once()


class TestODataClient(unittest.TestCase):
    """Tests for the ODataClient class."""
    
    def setUp(self):
        """Set up test environment for each test."""
        # Create minimal metadata for testing
        self.entity_type = EntityType(
            name="TestEntity",
            properties=[
                EntityProperty(name="ID", type="Edm.String", nullable=False, is_key=True),
                EntityProperty(name="Name", type="Edm.String", nullable=False),
                EntityProperty(name="Description", type="Edm.String"),
            ],
            key_properties=["ID"]
        )
        
        self.entity_set = EntitySet(
            name="TestSet",
            entity_type="TestEntity"
        )
        
        self.service_url = os.getenv("ODATA_URL")
        self.username = os.getenv("ODATA_USER")
        self.password = os.getenv("ODATA_PASS")
        
        self.auth = None
        if self.username and self.password:
            self.auth = (self.username, self.password)
        
        self.metadata = ODataMetadata(
            entity_types={"TestEntity": self.entity_type},
            entity_sets={"TestSet": self.entity_set},
            service_url=self.service_url
        )
        
        self.client = ODataClient(self.metadata, self.auth, verbose=True)
    
    @patch('requests.Session.request')
    def test_list_entities(self, mock_request):
        """Test listing entities."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "d": {
                "results": [
                    {"ID": "1", "Name": "Test 1", "Description": "Description 1"},
                    {"ID": "2", "Name": "Test 2", "Description": "Description 2"}
                ],
                "__count": "2"
            }
        }
        mock_request.return_value = mock_response
        
        # Add request URL for validation
        mock_response.request = MagicMock()
        mock_response.request.url = f"{self.service_url}/TestSet?$format=json&$inlinecount=allpages"
        
        # Call the method
        result = asyncio.run(self.client.list_or_filter_entities("TestSet", {}))
        
        # Verify the result structure
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["ID"], "1")
        self.assertEqual(result["results"][0]["Name"], "Test 1")
        
        # Verify pagination information
        self.assertIn("pagination", result)
        self.assertEqual(result["pagination"]["total_count"], 2)
        self.assertFalse(result["pagination"]["has_more"])
        
        # Verify the request was made with the correct URL and params
        # Headers may vary, so just check that the request was made
        self.assertEqual(mock_request.call_count, 1)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(args[1], f"{self.service_url}/TestSet")
        self.assertEqual(kwargs['params'], {'$format': 'json', '$inlinecount': 'allpages'})
    
    @patch('requests.Session.request')
    def test_get_entity(self, mock_request):
        """Test getting a single entity by key."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "d": {
                "ID": "1", 
                "Name": "Test 1", 
                "Description": "Description 1"
            }
        }
        mock_request.return_value = mock_response
        
        # Add request URL for validation
        mock_response.request = MagicMock()
        mock_response.request.url = f"{self.service_url}/TestSet('1')?$format=json"
        
        # Call the method
        result = asyncio.run(self.client.get_entity("TestSet", {"ID": "1"}))
        
        # Verify the result
        self.assertEqual(result["ID"], "1")
        self.assertEqual(result["Name"], "Test 1")
        self.assertEqual(result["Description"], "Description 1")
        
        # Verify the request was made with the correct URL and params
        # Headers may vary, so just check that the request was made
        self.assertEqual(mock_request.call_count, 1)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(args[1], f"{self.service_url}/TestSet('1')")
        self.assertEqual(kwargs['params'], {'$format': 'json'})


class TestODataMCPBridge(unittest.TestCase):
    """Tests for the ODataMCPBridge class."""
    
    @patch('odata_mcp.MetadataParser.parse')
    @patch('odata_mcp.FastMCP.add_tool')
    def test_tool_registration(self, mock_add_tool, mock_parse):
        """Test that MCP tools are registered correctly."""
        # Create minimal metadata
        entity_type = EntityType(
            name="TestEntity",
            properties=[
                EntityProperty(name="ID", type="Edm.String", nullable=False, is_key=True),
                EntityProperty(name="Name", type="Edm.String", nullable=False)
            ],
            key_properties=["ID"]
        )
        
        entity_set = EntitySet(
            name="TestSet",
            entity_type="TestEntity"
        )
        
        metadata = ODataMetadata(
            entity_types={"TestEntity": entity_type},
            entity_sets={"TestSet": entity_set},
            service_url=os.getenv("ODATA_URL", "https://example.com/odata/")
        )
        
        # Set the mock to return our metadata
        mock_parse.return_value = metadata
        
        # Create the bridge
        username = os.getenv("ODATA_USER")
        password = os.getenv("ODATA_PASS")
        auth = (username, password) if username and password else None
        
        bridge = ODataMCPBridge(
            service_url=os.getenv("ODATA_URL", "https://example.com/odata/"),
            auth=auth,
            verbose=True
        )
        
        # Expected tools that should be registered
        expected_tools = [
            "odata_service_info",
            "filter_TestSet",
            "count_TestSet",
            "search_TestSet",
            "get_TestSet",
            "create_TestSet",
            "update_TestSet",
            "delete_TestSet"
        ]
        
        # Check that the right number of tools were registered
        self.assertGreaterEqual(mock_add_tool.call_count, len(expected_tools))
        
        # Check that each expected tool was registered
        registered_tools = [call[1]['name'] for call in mock_add_tool.call_args_list]
        for expected_tool in expected_tools:
            # Check if any registered tool contains the expected base name
            found = any(expected_tool in registered_tool for registered_tool in registered_tools)
            self.assertTrue(found, f"No tool found containing '{expected_tool}' in registered tools: {registered_tools}")


@unittest.skipIf(not os.getenv("RUN_LIVE_TESTS", "").lower() == "true", 
                 "Skipping live tests. Set RUN_LIVE_TESTS=true to enable")
class TestLiveIntegration(unittest.TestCase):
    """Integration tests using the real OData service.
    
    These tests will only run if RUN_LIVE_TESTS=true is set in the environment.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.service_url = os.getenv("ODATA_URL")
        cls.username = os.getenv("ODATA_USER")
        cls.password = os.getenv("ODATA_PASS")
        
        if not cls.service_url:
            raise unittest.SkipTest("ODATA_URL environment variable is not set")
        
        cls.auth = None
        if cls.username and cls.password:
            cls.auth = (cls.username, cls.password)
        
        # Create parser and parse metadata
        print(f"Connecting to OData service: {cls.service_url}")
        cls.parser = MetadataParser(cls.service_url, cls.auth, verbose=True)
        cls.metadata = cls.parser.parse()
        
        # Create client
        cls.client = ODataClient(cls.metadata, cls.auth, verbose=True)
    
    def test_metadata_structure(self):
        """Test that metadata was parsed successfully."""
        # Basic validation of metadata structure
        self.assertIsNotNone(self.metadata)
        self.assertIsInstance(self.metadata.entity_sets, dict)
        self.assertIsInstance(self.metadata.entity_types, dict)
        
        # There should be at least one entity set
        self.assertTrue(len(self.metadata.entity_sets) > 0)
        
        # Print some metadata for debugging
        print(f"Found {len(self.metadata.entity_sets)} entity sets")
        print(f"Found {len(self.metadata.entity_types)} entity types")
        print(f"Found {len(self.metadata.function_imports)} function imports")
        
        # Print first entity set and type for reference
        if self.metadata.entity_sets:
            first_set_name = next(iter(self.metadata.entity_sets.keys()))
            first_set = self.metadata.entity_sets[first_set_name]
            print(f"First entity set: {first_set_name} (type: {first_set.entity_type})")
            
            if first_set.entity_type in self.metadata.entity_types:
                entity_type = self.metadata.entity_types[first_set.entity_type]
                print(f"Properties of {entity_type.name}: {[p.name for p in entity_type.properties]}")
    
    def test_list_entities(self):
        """Test listing entities from the first available entity set."""
        if not self.metadata.entity_sets:
            self.skipTest("No entity sets found in metadata")
        
        # Get the first entity set
        entity_set_name = next(iter(self.metadata.entity_sets.keys()))
        print(f"Testing list_entities with entity set: {entity_set_name}")
        
        # List entities with a limit
        params = {"$top": 5}
        result = asyncio.run(self.client.list_or_filter_entities(entity_set_name, params))
        
        # Validate response
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIsInstance(result["results"], list)
        
        # Log results for debugging
        print(f"Retrieved {len(result['results'])} entities from {entity_set_name}")
        if result["results"]:
            print(f"First entity keys: {list(result['results'][0].keys())}")


if __name__ == "__main__":
    print("OData MCP Wrapper Test Suite")
    print(f"Service URL: {os.getenv('ODATA_URL')}")
    
    # Set RUN_LIVE_TESTS in environment to control live tests
    if not os.getenv("RUN_LIVE_TESTS"):
        print("\nℹ️ Live integration tests are disabled by default.")
        print("To enable live tests, run with: RUN_LIVE_TESTS=true python test_odata_mcp.py")
    
    unittest.main()