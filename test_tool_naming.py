#!/usr/bin/env python3
"""
Test script to demonstrate the new tool naming patterns.
"""

from odata_mcp import ODataMCPBridge

def test_naming_patterns():
    """Test different tool naming patterns."""
    
    print("=== Tool Naming Pattern Examples ===\n")
    
    # Test service identification patterns
    test_urls = [
        "http://vhcala4hci:50000/sap/opu/odata/sap/ZMCP_002_SRV/",
        "https://services.odata.org/V2/Northwind/Northwind.svc/",
        "https://services.odata.org/V3/Northwind/Northwind.svc/",
        "https://services.odata.org/V4/Northwind/Northwind.svc/",
        "https://services.odata.org/V2/OData/OData.svc/",
        "https://services.odata.org/TripPinRESTierService/"
    ]
    
    for url in test_urls:
        bridge = ODataMCPBridge.__new__(ODataMCPBridge)  # Create without calling __init__
        service_id = bridge._generate_service_identifier(url)
        
        # Test postfix pattern (default)
        bridge.use_postfix = True
        bridge.tool_prefix = ""
        bridge.tool_postfix = f"_for_{service_id}"
        postfix_name = bridge._make_tool_name("odata_service_info")
        
        # Test prefix pattern
        bridge.use_postfix = False
        bridge.tool_prefix = f"{service_id}_"
        bridge.tool_postfix = ""
        prefix_name = bridge._make_tool_name("odata_service_info")
        
        print(f"URL: {url}")
        print(f"  Service ID: {service_id}")
        print(f"  Postfix pattern: {postfix_name}")
        print(f"  Prefix pattern:  {prefix_name}")
        print()

if __name__ == "__main__":
    test_naming_patterns()