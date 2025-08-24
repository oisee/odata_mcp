#!/usr/bin/env python3
"""
Test OAuth functionality with Microsoft Graph API.

This script tests OAuth 2.0 authentication with the OData MCP wrapper
using Microsoft Graph as the test endpoint.

Prerequisites:
1. Register an app in Azure Portal (portal.azure.com)
2. Get Client ID and Client Secret  
3. Configure app permissions for Microsoft Graph
4. Set environment variables or provide via CLI

Usage:
    export OAUTH_CLIENT_ID="your-client-id"
    export OAUTH_CLIENT_SECRET="your-client-secret"
    python test_oauth.py

    # Or with CLI args:
    python test_oauth.py --client-id CLIENT_ID --client-secret CLIENT_SECRET
"""

import os
import sys
import argparse
from odata_mcp_lib.oauth_handler import OAuthTokenManager, OAuthConfig
from odata_mcp_lib import MetadataParser


def test_oauth_token_fetch():
    """Test OAuth token acquisition."""
    print("🔧 Testing OAuth token fetch...")
    
    # Microsoft Graph configuration
    graph_config = OAuthConfig.microsoft_graph()
    
    # Get credentials from environment or CLI
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET") 
    
    if not client_id or not client_secret:
        print("❌ ERROR: Missing OAuth credentials")
        print("Set OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET environment variables")
        print("Or register an app at https://portal.azure.com")
        return False
        
    oauth_manager = OAuthTokenManager(
        client_id=client_id,
        client_secret=client_secret, 
        token_url=graph_config['token_url'],
        scope=graph_config['scope'],
        verbose=True
    )
    
    try:
        # Test token acquisition
        headers = oauth_manager.get_authorization_header()
        print(f"✅ OAuth token acquired successfully!")
        print(f"   Authorization header: {headers['Authorization'][:50]}...")
        return True
    except Exception as e:
        print(f"❌ OAuth token fetch failed: {e}")
        return False


def test_graph_metadata():
    """Test fetching Microsoft Graph metadata with OAuth."""
    print("\n🔧 Testing Microsoft Graph metadata fetch with OAuth...")
    
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ ERROR: Missing OAuth credentials") 
        return False
    
    graph_config = OAuthConfig.microsoft_graph()
    oauth_manager = OAuthTokenManager(
        client_id=client_id,
        client_secret=client_secret,
        token_url=graph_config['token_url'],
        scope=graph_config['scope'],
        verbose=True
    )
    
    try:
        # Test metadata parsing with OAuth
        graph_service_url = "https://graph.microsoft.com/v1.0/"
        parser = MetadataParser(
            graph_service_url,
            auth=None,
            oauth_manager=oauth_manager,
            verbose=True
        )
        
        metadata = parser.parse()
        print(f"✅ Graph metadata parsed successfully!")
        print(f"   Service URL: {metadata.service_url}")
        print(f"   Entity Types: {len(metadata.entity_types)}")
        print(f"   Entity Sets: {len(metadata.entity_sets)}")
        print(f"   Functions: {len(metadata.function_imports)}")
        
        # Show some entity sets
        if metadata.entity_sets:
            print(f"   Sample Entity Sets: {list(metadata.entity_sets.keys())[:5]}")
        
        return True
    except Exception as e:
        print(f"❌ Graph metadata fetch failed: {e}")
        return False


def test_northwind_oauth():
    """Test OAuth with public Northwind service (should fail gracefully)."""
    print("\n🔧 Testing OAuth with public Northwind service (expect graceful failure)...")
    
    fake_oauth = OAuthTokenManager(
        client_id="fake-client",
        client_secret="fake-secret",
        token_url="https://fake.example.com/oauth/token",
        verbose=True
    )
    
    try:
        # This should fail at the OAuth level, not crash
        headers = fake_oauth.get_authorization_header()
        print("❌ Unexpected success with fake OAuth")
        return False
    except Exception as e:
        print(f"✅ OAuth properly failed as expected: {type(e).__name__}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Test OAuth functionality")
    parser.add_argument("--client-id", help="OAuth Client ID")
    parser.add_argument("--client-secret", help="OAuth Client Secret")
    parser.add_argument("--skip-graph", action="store_true", help="Skip Graph API tests")
    args = parser.parse_args()
    
    if args.client_id:
        os.environ["OAUTH_CLIENT_ID"] = args.client_id
    if args.client_secret:
        os.environ["OAUTH_CLIENT_SECRET"] = args.client_secret
    
    print("🚀 OAuth Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Basic OAuth token fetch
    if not args.skip_graph:
        total_tests += 1
        if test_oauth_token_fetch():
            tests_passed += 1
    else:
        print("⏭️  Skipping Graph API tests")
    
    # Test 2: Graph metadata with OAuth  
    if not args.skip_graph:
        total_tests += 1
        if test_graph_metadata():
            tests_passed += 1
    
    # Test 3: Graceful failure handling
    total_tests += 1
    if test_northwind_oauth():
        tests_passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! OAuth implementation is working.")
        return 0
    else:
        print("❌ Some tests failed. Check OAuth configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())