#!/usr/bin/env python3
"""
Test script for the updated hints.json from Go implementation.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from odata_mcp_lib import HintManager

def test_hints_loading():
    """Test that the updated hints.json loads correctly."""
    print("🧪 Testing hints.json loading...")
    
    manager = HintManager(verbose=True)
    success = manager.load_from_file('hints.json')
    
    if not success:
        print("❌ FAILED: Could not load hints.json")
        return False
    
    print(f"✅ Loaded {len(manager.hints)} hint patterns")
    
    # Verify each hint loaded correctly
    for i, hint in enumerate(manager.hints):
        print(f"\n📋 Hint {i+1}:")
        print(f"  Pattern: {hint.pattern}")
        print(f"  Priority: {hint.priority}")
        print(f"  Service Type: {hint.service_type}")
        print(f"  Known Issues: {len(hint.known_issues)}")
        print(f"  Workarounds: {len(hint.workarounds)}")
        print(f"  Field Hints: {list(hint.field_hints.keys())}")
        print(f"  Entity Hints: {list(hint.entity_hints.keys())}")
        print(f"  Examples: {len(hint.examples)}")
        print(f"  Notes: {len(hint.notes)}")
    
    return True

def test_sap_service_matching():
    """Test SAP service pattern matching."""
    print("\n🧪 Testing SAP service pattern matching...")
    
    manager = HintManager()
    manager.load_from_file('hints.json')
    
    test_urls = [
        "https://example.com/sap/opu/odata/sap/MY_SERVICE/",
        "https://sap.company.com/sap/opu/odata/SAP/SERVICE_NAME/",
        "http://dev.local/sap/opu/odata/sap/test/"
    ]
    
    for url in test_urls:
        hints = manager.get_hints(url)
        if hints and hints.get('service_type') == 'SAP OData Service':
            print(f"✅ {url} -> Matched SAP service hints")
        else:
            print(f"❌ {url} -> Did not match SAP service hints")
            return False
    
    return True

def test_po_tracking_service():
    """Test SAP PO Tracking service hints."""
    print("\n🧪 Testing SAP PO Tracking service hints...")
    
    manager = HintManager()
    manager.load_from_file('hints.json')
    
    url = "https://sap.company.com/sap/opu/odata/sap/SRA020_PO_TRACKING_SRV/"
    hints = manager.get_hints(url)
    
    if not hints:
        print("❌ No hints found for PO Tracking service")
        return False
    
    print(f"✅ Service Type: {hints.get('service_type')}")
    
    # Check field hints
    field_hints = hints.get('field_hints', {})
    if 'PONumber' in field_hints:
        po_hint = field_hints['PONumber']
        print(f"✅ PONumber field hint found:")
        print(f"   Type: {po_hint.get('type')}")
        print(f"   Format: {po_hint.get('format')}")
        print(f"   Example: {po_hint.get('example')}")
        print(f"   Description: {po_hint.get('description')}")
    else:
        print("❌ PONumber field hint missing")
        return False
    
    # Check entity hints
    entity_hints = hints.get('entity_hints', {})
    if 'PODetailedDatas' in entity_hints:
        po_entity = entity_hints['PODetailedDatas']
        print(f"✅ PODetailedDatas entity hint found:")
        print(f"   Description: {po_entity.get('description')}")
        print(f"   Notes: {len(po_entity.get('notes', []))}")
        print(f"   Examples: {len(po_entity.get('examples', []))}")
    else:
        print("❌ PODetailedDatas entity hint missing")
        return False
    
    if 'POItemDetailDatas' in entity_hints:
        item_entity = entity_hints['POItemDetailDatas']
        print(f"✅ POItemDetailDatas entity hint found:")
        print(f"   Navigation paths: {len(item_entity.get('navigation_paths', []))}")
        if item_entity.get('navigation_paths'):
            for path in item_entity['navigation_paths'][:3]:  # Show first 3
                print(f"     - {path}")
    
    # Check examples
    examples = hints.get('examples', [])
    print(f"✅ Found {len(examples)} example queries")
    for i, example in enumerate(examples):
        print(f"\n   Example {i+1}: {example.get('description')}")
        print(f"   Query: {example.get('query')[:100]}...")
        print(f"   Note: {example.get('note')}")
    
    return True

def test_northwind_service():
    """Test Northwind service hints."""
    print("\n🧪 Testing Northwind service hints...")
    
    manager = HintManager()
    manager.load_from_file('hints.json')
    
    urls = [
        "https://services.odata.org/V2/Northwind/Northwind.svc/",
        "https://services.odata.org/V4/Northwind/Northwind.svc/",
        "https://example.com/Northwind/api/"
    ]
    
    for url in urls:
        hints = manager.get_hints(url)
        if hints and 'Northwind Demo Service' in str(hints.get('service_type', '')):
            print(f"✅ {url} -> Matched Northwind hints")
            print(f"   Notes: {hints.get('notes', [])}")
        else:
            print(f"❌ {url} -> Did not match Northwind hints")
    
    return True

def test_priority_merging():
    """Test that higher priority hints override lower ones."""
    print("\n🧪 Testing priority-based hint merging...")
    
    manager = HintManager()
    manager.load_from_file('hints.json')
    
    # Test URL that matches both SAP general and PO tracking patterns
    url = "https://sap.company.com/sap/opu/odata/sap/SRA020_PO_TRACKING_SRV/"
    hints = manager.get_hints(url)
    
    if not hints:
        print("❌ No hints found")
        return False
    
    # PO Tracking (priority 50) should override SAP general (priority 10)
    if hints.get('service_type') == 'SAP Purchase Order Tracking Service':
        print("✅ Higher priority PO Tracking hints took precedence")
    else:
        print("❌ Priority merging failed")
        return False
    
    # Should have merged notes from both
    all_notes = hints.get('notes', [])
    po_specific = any('backend implementation' in note.lower() for note in all_notes)
    sap_general = any('implementation quirks' in note.lower() for note in all_notes)
    
    if po_specific and sap_general:
        print("✅ Notes merged from both hint sets")
    else:
        print("⚠️  Notes may not have merged correctly")
    
    return True

def test_hint_to_dict():
    """Test that hints serialize correctly to dictionary."""
    print("\n🧪 Testing hint serialization...")
    
    manager = HintManager()
    manager.load_from_file('hints.json')
    
    url = "https://sap.company.com/sap/opu/odata/sap/SRA020_PO_TRACKING_SRV/"
    hints = manager.get_hints(url)
    
    if not hints:
        print("❌ No hints to test")
        return False
    
    # Try to serialize to JSON
    try:
        json_str = json.dumps(hints, indent=2)
        print("✅ Hints serialized to JSON successfully")
        print(f"   JSON size: {len(json_str)} bytes")
        
        # Verify key fields are present
        parsed = json.loads(json_str)
        required_fields = ['service_type', 'known_issues', 'workarounds', 'hint_source']
        for field in required_fields:
            if field in parsed:
                print(f"   ✅ {field}: present")
            else:
                print(f"   ❌ {field}: missing")
        
        return True
    except Exception as e:
        print(f"❌ Failed to serialize hints: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing updated hints.json from Go implementation")
    print("=" * 60)
    
    tests = [
        test_hints_loading,
        test_sap_service_matching,
        test_po_tracking_service,
        test_northwind_service,
        test_priority_merging,
        test_hint_to_dict
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
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The updated hints.json works correctly.")
        return 0
    else:
        print("⚠️  Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())