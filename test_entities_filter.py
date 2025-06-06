#!/usr/bin/env python3
"""Test script to verify --entities filtering functionality."""

import subprocess
import sys
import json
import time

def test_entities_filter():
    """Test the --entities parameter functionality."""
    
    # Test with Northwind service (known entities: Products, Categories, Orders, etc.)
    service_url = "https://services.odata.org/V4/Northwind/Northwind.svc"
    
    print("Testing --entities parameter with Northwind OData service")
    print("=" * 60)
    
    # Test 1: No filter (should generate tools for all entities)
    print("\nTest 1: No entity filter (all entities)")
    print("-" * 40)
    
    cmd1 = [
        sys.executable, 
        "odata_mcp.py",
        "--service", service_url,
        "--verbose"
    ]
    
    result1 = run_and_get_tools(cmd1)
    if result1:
        print(f"Found {len(result1)} tools without filter")
        print("Sample tools:", [t['name'] for t in result1[:5]])
    
    # Test 2: Filter to specific entities
    print("\nTest 2: Entity filter for Products and Categories only")
    print("-" * 40)
    
    cmd2 = [
        sys.executable, 
        "odata_mcp.py", 
        "--service", service_url,
        "--entities", "Products,Categories",
        "--verbose"
    ]
    
    result2 = run_and_get_tools(cmd2)
    if result2:
        print(f"Found {len(result2)} tools with filter")
        print("Filtered tools:", [t['name'] for t in result2])
        
        # Verify only Products and Categories tools exist
        product_tools = [t for t in result2 if 'Products' in t['name']]
        category_tools = [t for t in result2 if 'Categories' in t['name']]
        other_tools = [t for t in result2 if 'Products' not in t['name'] and 'Categories' not in t['name'] and 'service_info' not in t['name']]
        
        print(f"\nProducts tools: {len(product_tools)}")
        print(f"Categories tools: {len(category_tools)}")
        print(f"Other entity tools: {len(other_tools)}")
        
        if len(other_tools) == 0:
            print("✅ SUCCESS: Filter working correctly - only Products and Categories tools generated")
        else:
            print("❌ FAILED: Filter not working - found unexpected tools:", [t['name'] for t in other_tools])
    
    # Test 3: Invalid entity (should generate no tools for that entity)
    print("\nTest 3: Invalid entity filter")
    print("-" * 40)
    
    cmd3 = [
        sys.executable, 
        "odata_mcp.py",
        "--service", service_url,
        "--entities", "NonExistentEntity",
        "--verbose"
    ]
    
    result3 = run_and_get_tools(cmd3)
    if result3:
        print(f"Found {len(result3)} tools with invalid entity filter")
        # Should only have service_info tool
        if len(result3) == 1 and 'service_info' in result3[0]['name']:
            print("✅ SUCCESS: Invalid entity correctly filtered out - only service_info tool remains")
        else:
            print("❌ Unexpected result with invalid entity")

def run_and_get_tools(cmd):
    """Run the command and extract tools from MCP response."""
    try:
        print(f"Running: {' '.join(cmd)}")
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send tools/list request
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        stdout, stderr = process.communicate(
            input=json.dumps(request) + "\n",
            timeout=30
        )
        
        # Print verbose output
        if stderr.strip():
            print("STDERR:", stderr.strip())
        
        # Parse response
        for line in stdout.strip().split('\n'):
            if line.strip():
                try:
                    response = json.loads(line)
                    if 'result' in response and 'tools' in response['result']:
                        return response['result']['tools']
                except json.JSONDecodeError:
                    continue
        
        return None
        
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        process.kill()
        return None
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return None

if __name__ == "__main__":
    test_entities_filter()