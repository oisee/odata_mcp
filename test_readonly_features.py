#!/usr/bin/env python3
"""
Test script for new read-only and hints features in OData MCP Python implementation.
"""

import subprocess
import sys
import os

def run_command(cmd, capture_output=True):
    """Run a command and return the result."""
    print(f"\n🔹 Running: {' '.join(cmd)}")
    if capture_output:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
    else:
        return subprocess.run(cmd)

def test_read_only_mode():
    """Test --read-only mode."""
    print("\n🧪 Testing --read-only mode...")
    
    # Set a dummy service URL for testing
    os.environ['ODATA_URL'] = 'https://services.odata.org/V2/Northwind/Northwind.svc'
    
    # Test with --trace to see registered tools
    result = run_command(['python', 'odata_mcp.py', '--read-only', '--trace'])
    
    if result.returncode == 0:
        output = result.stdout
        # Check that create/update/delete tools are not present
        if 'create_' in output or 'update_' in output or 'delete_' in output:
            print("❌ FAILED: Found modifying operations in read-only mode")
            return False
        
        # Check that filter/get/count tools are still present
        if 'filter_' not in output or 'get_' not in output:
            print("❌ FAILED: Read operations missing in read-only mode")
            return False
            
        print("✅ PASSED: Read-only mode correctly hides modifying operations")
        return True
    else:
        print(f"❌ FAILED: Command failed with error: {result.stderr}")
        return False

def test_read_only_but_functions_mode():
    """Test --read-only-but-functions mode."""
    print("\n🧪 Testing --read-only-but-functions mode...")
    
    os.environ['ODATA_URL'] = 'https://services.odata.org/V2/Northwind/Northwind.svc'
    
    # Test with --trace to see registered tools
    result = run_command(['python', 'odata_mcp.py', '--read-only-but-functions', '--trace'])
    
    if result.returncode == 0:
        output = result.stdout
        # Check that create/update/delete tools are not present
        if 'create_' in output or 'update_' in output or 'delete_' in output:
            print("❌ FAILED: Found CRUD operations in read-only-but-functions mode")
            return False
        
        # Note: Northwind service might not have function imports, so we just check the mode is accepted
        print("✅ PASSED: Read-only-but-functions mode accepted (CRUD operations hidden)")
        return True
    else:
        print(f"❌ FAILED: Command failed with error: {result.stderr}")
        return False

def test_mutual_exclusivity():
    """Test that --read-only and --read-only-but-functions are mutually exclusive."""
    print("\n🧪 Testing mutual exclusivity of read-only flags...")
    
    os.environ['ODATA_URL'] = 'https://services.odata.org/V2/Northwind/Northwind.svc'
    
    result = run_command(['python', 'odata_mcp.py', '--read-only', '--read-only-but-functions', '--trace'])
    
    if result.returncode != 0 and ('not allowed with' in result.stderr or 'mutually exclusive' in result.stderr):
        print("✅ PASSED: Correctly rejected mutually exclusive flags")
        return True
    else:
        print("❌ FAILED: Should reject mutually exclusive flags")
        return False

def test_trace_mcp_flag():
    """Test that --trace-mcp flag is accepted."""
    print("\n🧪 Testing --trace-mcp flag...")
    
    os.environ['ODATA_URL'] = 'https://services.odata.org/V2/Northwind/Northwind.svc'
    
    # Just test that the flag is accepted
    result = run_command(['python', 'odata_mcp.py', '--trace-mcp', '--trace'])
    
    if result.returncode == 0:
        print("✅ PASSED: --trace-mcp flag accepted")
        return True
    else:
        print(f"❌ FAILED: Command failed with error: {result.stderr}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing new features in OData MCP Python implementation")
    print("=" * 60)
    
    tests = [
        test_read_only_mode,
        test_read_only_but_functions_mode,
        test_mutual_exclusivity,
        test_trace_mcp_flag
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())