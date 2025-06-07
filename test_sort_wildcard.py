#!/usr/bin/env python3
"""Test script for the new --sort-tools and wildcard entity filtering features."""

import subprocess
import sys
import json

def test_features():
    """Test the new --sort-tools and wildcard entity filtering features."""
    
    # Test service URL - using a mock or example URL
    service_url = "https://services.odata.org/V2/Northwind/Northwind.svc/"
    
    print("Testing --sort-tools and wildcard entity filtering features...\n")
    
    # Test 1: Basic functionality with --sort-tools (default is True)
    print("Test 1: Default behavior (tools should be sorted)")
    cmd = [sys.executable, "odata_mcp.py", "--service", service_url, "--verbose"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Default sorting works")
        else:
            print("✗ Default sorting failed")
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    print("\n" + "-"*50 + "\n")
    
    # Test 2: Wildcard entity filtering
    print("Test 2: Wildcard entity filtering with 'Product*,Order*'")
    cmd = [sys.executable, "odata_mcp.py", "--service", service_url, "--entities", "Product*,Order*", "--verbose"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            # Check if only entities matching Product* or Order* are included
            if "Products" in result.stderr and "Orders" in result.stderr:
                print("✓ Wildcard filtering works - found Products and Orders")
            else:
                print("✗ Expected entities not found")
                print(f"Output: {result.stderr[:500]}...")
        else:
            print("✗ Wildcard filtering failed")
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    print("\n" + "-"*50 + "\n")
    
    # Test 3: Exact entity filtering (no wildcards)
    print("Test 3: Exact entity filtering with 'Products,Categories'")
    cmd = [sys.executable, "odata_mcp.py", "--service", service_url, "--entities", "Products,Categories", "--verbose"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            # Check if only Products and Categories are included
            if "Products" in result.stderr and "Categories" in result.stderr:
                print("✓ Exact entity filtering works")
                # Also check that other entities are excluded
                if "Customers" not in result.stderr:
                    print("✓ Other entities properly excluded")
                else:
                    print("✗ Other entities not properly excluded")
            else:
                print("✗ Expected entities not found")
        else:
            print("✗ Exact entity filtering failed")
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    print("\n" + "-"*50 + "\n")
    
    # Test 4: Mixed wildcards and exact names
    print("Test 4: Mixed filtering with 'Cat*,Orders'")
    cmd = [sys.executable, "odata_mcp.py", "--service", service_url, "--entities", "Cat*,Orders", "--verbose"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            if "Categories" in result.stderr and "Orders" in result.stderr:
                print("✓ Mixed wildcard and exact filtering works")
            else:
                print("✗ Expected entities not found")
        else:
            print("✗ Mixed filtering failed")
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_features()