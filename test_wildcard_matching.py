#!/usr/bin/env python3
"""Unit tests for wildcard entity matching functionality."""

import unittest
from odata_mcp_lib.bridge import ODataMCPBridge

class TestWildcardMatching(unittest.TestCase):
    """Test the wildcard matching functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create a minimal bridge instance just to test the method
        # We'll use a dummy URL and no auth since we're only testing the matching logic
        self.bridge = ODataMCPBridge.__new__(ODataMCPBridge)
        
    def test_exact_match(self):
        """Test exact entity name matching."""
        patterns = ["Products", "Categories", "Orders"]
        
        self.assertTrue(self.bridge._matches_entity_filter("Products", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Categories", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Orders", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Customers", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Product", patterns))
        
    def test_wildcard_suffix(self):
        """Test wildcard matching with * at the end."""
        patterns = ["Product*", "Order*"]
        
        self.assertTrue(self.bridge._matches_entity_filter("Products", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("ProductCategories", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Product", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Orders", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("OrderDetails", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Categories", patterns))
        
    def test_wildcard_prefix(self):
        """Test wildcard matching with * at the beginning."""
        patterns = ["*Service", "*Data"]
        
        self.assertTrue(self.bridge._matches_entity_filter("UserService", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("OrderService", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Service", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("CustomerData", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Users", patterns))
        
    def test_wildcard_middle(self):
        """Test wildcard matching with * in the middle."""
        patterns = ["User*Service", "Order*Details"]
        
        self.assertTrue(self.bridge._matches_entity_filter("UserService", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("UserAuthService", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("OrderDetails", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("OrderItemDetails", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Service", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("UserAuth", patterns))
        
    def test_multiple_wildcards(self):
        """Test patterns with multiple wildcards."""
        patterns = ["*User*", "*Order*"]
        
        self.assertTrue(self.bridge._matches_entity_filter("Users", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("UserService", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("SystemUsers", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Orders", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("CustomerOrders", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Products", patterns))
        
    def test_mixed_patterns(self):
        """Test mix of exact and wildcard patterns."""
        patterns = ["Products", "Order*", "*Service"]
        
        self.assertTrue(self.bridge._matches_entity_filter("Products", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Orders", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("OrderDetails", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("UserService", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Service", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Product", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Categories", patterns))
        
    def test_empty_patterns(self):
        """Test with empty pattern list."""
        patterns = []
        
        self.assertFalse(self.bridge._matches_entity_filter("Products", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("Orders", patterns))
        
    def test_case_sensitivity(self):
        """Test case sensitivity in matching."""
        patterns = ["Products", "Order*"]
        
        # fnmatch is case-sensitive by default
        self.assertTrue(self.bridge._matches_entity_filter("Products", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("products", patterns))
        self.assertTrue(self.bridge._matches_entity_filter("Orders", patterns))
        self.assertFalse(self.bridge._matches_entity_filter("orders", patterns))

if __name__ == "__main__":
    unittest.main()