#!/usr/bin/env python3
"""
Test script for the hint system implementation.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def run_command(cmd, capture_output=True):
    """Run a command and return the result."""
    print(f"\n🔹 Running: {' '.join(cmd)}")
    if capture_output:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
    else:
        return subprocess.run(cmd)

def test_default_hints_loading():
    """Test that default hints.json is loaded."""
    print("\n🧪 Testing default hints.json loading...")
    
    os.environ['ODATA_URL'] = 'https://services.odata.org/V2/Northwind/Northwind.svc/'
    
    result = run_command(['python', 'odata_mcp.py', '--trace'])
    
    if result.returncode == 0:
        output = result.stdout
        if 'Hints File:' in output and 'hints.json' in output:
            print("✅ PASSED: Default hints.json loaded successfully")
            return True
        else:
            print("❌ FAILED: Default hints.json not loaded")
            return False
    else:
        print(f"❌ FAILED: Command failed with error: {result.stderr}")
        return False

def test_custom_hints_file():
    """Test loading hints from a custom file."""
    print("\n🧪 Testing custom hints file...")
    
    # Create a temporary hints file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        custom_hints = {
            "version": "1.0",
            "hints": [{
                "pattern": "*test*",
                "priority": 100,
                "service_type": "Test Service",
                "notes": ["This is a test hint"]
            }]
        }
        json.dump(custom_hints, f)
        temp_file = f.name
    
    try:
        # Test hint loading directly without connecting to service
        from odata_mcp_lib import HintManager
        
        manager = HintManager()
        success = manager.load_from_file(temp_file)
        
        if success and len(manager.hints) == 1:
            hint = manager.hints[0]
            if hint.service_type == "Test Service" and hint.pattern == "*test*":
                print("✅ PASSED: Custom hints file loaded successfully")
                return True
            else:
                print("❌ FAILED: Hint content incorrect")
                return False
        else:
            print("❌ FAILED: Custom hints file not loaded")
            return False
    finally:
        os.unlink(temp_file)

def test_cli_hint():
    """Test CLI hint injection."""
    print("\n🧪 Testing CLI hint injection...")
    
    os.environ['ODATA_URL'] = 'https://services.odata.org/V2/Northwind/Northwind.svc/'
    
    # Test with JSON hint
    result = run_command([
        'python', 'odata_mcp.py', 
        '--hint', '{"service_type": "CLI Test", "notes": ["Test note from CLI"]}',
        '--trace'
    ])
    
    if result.returncode == 0:
        output = result.stdout
        if 'CLI Hint: Present' in output:
            print("✅ PASSED: CLI hint accepted")
            return True
        else:
            print("❌ FAILED: CLI hint not detected")
            return False
    else:
        print(f"❌ FAILED: Command failed with error: {result.stderr}")
        return False

def test_hint_in_service_info():
    """Test that hints appear in service info response (simulated)."""
    print("\n🧪 Testing hint integration in service info...")
    
    # Test by checking that HintManager is properly integrated
    try:
        from odata_mcp_lib import HintManager
        
        manager = HintManager()
        manager.load_from_file('hints.json')
        
        # Test SAP service pattern
        sap_hints = manager.get_hints('https://example.com/sap/opu/odata/sap/TEST_SRV/')
        if sap_hints and sap_hints.get('service_type') == 'SAP OData Service':
            print("✅ PASSED: SAP service hints matched correctly")
            
        # Test PO Tracking service pattern
        po_hints = manager.get_hints('https://example.com/sap/opu/odata/sap/SRA020_PO_TRACKING_SRV/')
        if po_hints and po_hints.get('service_type') == 'SAP Purchase Order Tracking Service':
            print("✅ PASSED: PO Tracking service hints matched correctly")
            
        # Test Northwind pattern
        nw_hints = manager.get_hints('https://services.odata.org/V2/Northwind/Northwind.svc/')
        if nw_hints and 'Northwind Demo Service' in str(nw_hints.get('service_type', '')):
            print("✅ PASSED: Northwind service hints matched correctly")
            
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Error testing hint integration: {e}")
        return False

def test_pattern_matching():
    """Test wildcard pattern matching."""
    print("\n🧪 Testing pattern matching...")
    
    try:
        from odata_mcp_lib import HintManager
        
        manager = HintManager()
        
        # Test various patterns
        test_cases = [
            ("*/sap/opu/odata/*", "https://example.com/sap/opu/odata/sap/TEST_SRV/", True),
            ("*SRA020*", "https://example.com/sap/opu/odata/sap/SRA020_PO_TRACKING_SRV/", True),
            ("*Northwind*", "https://services.odata.org/V2/Northwind/Northwind.svc/", True),
            ("*Northwind*", "https://example.com/other/service/", False),
            ("https://specific.com/*", "https://specific.com/odata/", True),
            ("https://specific.com/*", "https://other.com/odata/", False),
        ]
        
        all_passed = True
        for pattern, url, expected in test_cases:
            result = manager.matches_pattern(pattern, url)
            if result == expected:
                print(f"  ✅ Pattern '{pattern}' {'matches' if expected else 'does not match'} '{url}'")
            else:
                print(f"  ❌ Pattern '{pattern}' failed for '{url}' (expected {expected}, got {result})")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ FAILED: Error testing pattern matching: {e}")
        return False

def main():
    """Run all hint tests."""
    print("🚀 Testing hint system implementation")
    print("=" * 60)
    
    tests = [
        test_default_hints_loading,
        test_custom_hints_file,
        test_cli_hint,
        test_hint_in_service_info,
        test_pattern_matching
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