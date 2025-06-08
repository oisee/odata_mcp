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
from odata_mcp_lib import (
    MetadataParser, 
    ODataClient, 
    ODataMCPBridge, 
    ODataMetadata, 
    EntityType, 
    EntityProperty, 
    EntitySet, 
    FunctionImport
)
from odata_mcp import load_cookies_from_file, parse_cookie_string

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
    
    @patch('odata_mcp_lib.metadata_parser.MetadataParser._parse_entity_types')
    @patch('odata_mcp_lib.metadata_parser.MetadataParser._parse_entity_sets')
    @patch('odata_mcp_lib.metadata_parser.MetadataParser._parse_function_imports')
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


class TestCookieAuthentication(unittest.TestCase):
    """Tests for cookie authentication functionality."""
    
    def test_parse_cookie_string(self):
        """Test parsing cookie strings."""
        # Test simple cookie string
        cookies = parse_cookie_string("session=abc123; user=john")
        self.assertEqual(cookies["session"], "abc123")
        self.assertEqual(cookies["user"], "john")
        
        # Test with spaces and semicolons
        cookies = parse_cookie_string("session=abc123;user=john;token=xyz789")
        self.assertEqual(len(cookies), 3)
        self.assertEqual(cookies["token"], "xyz789")
        
        # Test empty string
        cookies = parse_cookie_string("")
        self.assertEqual(len(cookies), 0)
        
        # Test with equals in value
        cookies = parse_cookie_string("data=key=value; session=123")
        self.assertEqual(cookies["data"], "key=value")
        self.assertEqual(cookies["session"], "123")
    
    def test_load_cookies_from_file(self):
        """Test loading cookies from a file."""
        # Create a temporary cookie file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This is a comment\n")
            f.write(".example.com\tTRUE\t/\tFALSE\t0\tsession\tabc123\n")
            f.write(".example.com\tTRUE\t/\tFALSE\t0\tuser\tjohn\n")
            f.write("# Another comment\n")
            f.write(".test.com\tTRUE\t/\tTRUE\t1234567890\ttoken\txyz789\n")
            temp_file = f.name
        
        try:
            # Load cookies from file
            cookies = load_cookies_from_file(temp_file)
            self.assertIsNotNone(cookies)
            self.assertEqual(cookies["session"], "abc123")
            self.assertEqual(cookies["user"], "john")
            self.assertEqual(cookies["token"], "xyz789")
            
            # Test with simple format
            with open(temp_file, 'w') as f:
                f.write("session=def456\n")
                f.write("user=jane\n")
                f.write("# Comment line\n")
                f.write("token=uvw321\n")
            
            cookies = load_cookies_from_file(temp_file)
            self.assertEqual(cookies["session"], "def456")
            self.assertEqual(cookies["user"], "jane")
            self.assertEqual(cookies["token"], "uvw321")
            
        finally:
            # Clean up
            os.unlink(temp_file)
    
    def test_cookie_auth_in_client(self):
        """Test that ODataClient accepts cookie authentication."""
        # Create minimal metadata
        entity_type = EntityType(
            name="TestEntity",
            properties=[
                EntityProperty(name="ID", type="Edm.String", nullable=False, is_key=True)
            ],
            key_properties=["ID"]
        )
        
        metadata = ODataMetadata(
            entity_types={"TestEntity": entity_type},
            entity_sets={"TestSet": EntitySet(name="TestSet", entity_type="TestEntity")},
            service_url="https://example.com/odata/"
        )
        
        # Test with cookie dict
        cookies = {"session": "abc123", "user": "john"}
        client = ODataClient(metadata, auth=cookies)
        self.assertEqual(client.auth_type, "cookie")
        self.assertFalse(client.session.verify)  # SSL verification should be disabled
        
        # Test with basic auth tuple
        client = ODataClient(metadata, auth=("user", "pass"))
        self.assertEqual(client.auth_type, "basic")
        
        # Test with no auth
        client = ODataClient(metadata, auth=None)
        self.assertEqual(client.auth_type, "none")
    
    def test_cookie_auth_in_metadata_parser(self):
        """Test that MetadataParser accepts cookie authentication."""
        # Test with cookie dict
        cookies = {"session": "abc123", "user": "john"}
        parser = MetadataParser("https://example.com/odata/", auth=cookies)
        self.assertEqual(parser.auth_type, "cookie")
        self.assertFalse(parser.session.verify)  # SSL verification should be disabled
        
        # Test with basic auth tuple
        parser = MetadataParser("https://example.com/odata/", auth=("user", "pass"))
        self.assertEqual(parser.auth_type, "basic")
        
        # Test with no auth
        parser = MetadataParser("https://example.com/odata/", auth=None)
        self.assertEqual(parser.auth_type, "none")


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
    
    @patch('odata_mcp_lib.metadata_parser.MetadataParser.parse')
    @patch('fastmcp.FastMCP.add_tool')
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
            entity_type="TestEntity",
            searchable=True  # Enable search for this test
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
    
    @patch('odata_mcp_lib.bridge.FastMCP')
    @patch('odata_mcp_lib.bridge.ODataClient') 
    @patch.object(MetadataParser, 'parse')
    def test_searchable_property_respected(self, mock_parse, mock_client_class, mock_mcp_class):
        """Test that search tools are only registered when searchable=True"""
        # Create mock instances
        mock_client = MagicMock()
        mock_mcp = MagicMock()
        
        mock_client_class.return_value = mock_client
        mock_mcp_class.return_value = mock_mcp
        
        # Create test metadata with searchable and non-searchable entities
        entity_type = EntityType(
            name="TestEntity",
            properties=[
                EntityProperty(name="ID", type="Edm.String", nullable=False, is_key=True),
                EntityProperty(name="Name", type="Edm.String", nullable=False)
            ],
            key_properties=["ID"]
        )
        
        searchable_set = EntitySet(
            name="SearchableEntity",
            entity_type="TestEntity",
            searchable=True
        )
        
        non_searchable_set = EntitySet(
            name="NonSearchableEntity",
            entity_type="TestEntity",
            searchable=False  # Explicitly not searchable
        )
        
        metadata = ODataMetadata(
            entity_types={"TestEntity": entity_type},
            entity_sets={
                "SearchableEntity": searchable_set,
                "NonSearchableEntity": non_searchable_set
            },
            service_url="https://example.com/odata/"
        )
        
        # Set the mock to return our metadata
        mock_parse.return_value = metadata
        
        # Create the bridge
        bridge = ODataMCPBridge(
            service_url="https://example.com/odata/",
            verbose=False
        )
        
        # Get all registered tool names from the 'name' parameter
        registered_tools = []
        for call in mock_mcp.add_tool.call_args_list:
            if 'name' in call[1]:
                registered_tools.append(call[1]['name'])
        
        # Check that search tool exists for searchable entity
        searchable_search_tools = [t for t in registered_tools if 'search_SearchableEntity' in t]
        self.assertEqual(len(searchable_search_tools), 1, 
                        f"Expected 1 search tool for SearchableEntity, found {len(searchable_search_tools)}")
        
        # Check that search tool does NOT exist for non-searchable entity
        non_searchable_search_tools = [t for t in registered_tools if 'search_NonSearchableEntity' in t]
        self.assertEqual(len(non_searchable_search_tools), 0, 
                        f"Expected 0 search tools for NonSearchableEntity, found {len(non_searchable_search_tools)}")


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