#!/usr/bin/env python3
"""Test the ACTIVATE_PROGRAM function with the fixed string parameter formatting."""

import asyncio
import json
from odata_mcp_lib.client import ODataClient
from odata_mcp_lib.metadata_parser import MetadataParser

async def test_activate_program():
    """Test the ACTIVATE_PROGRAM function."""
    # Use the IP address directly since vhcala4hci is in /etc/hosts
    service_url = "http://192.168.192.110:50000/sap/opu/odata/sap/ZODD_000_SRV"
    
    # Add your authentication if needed
    auth = None  # or auth = ("username", "password")
    
    try:
        print("Parsing metadata...")
        parser = MetadataParser(service_url, auth, verbose=False)
        metadata = parser.parse()
        
        print("Creating OData client...")
        client = ODataClient(metadata, auth, verbose=True)
        
        print("\nInvoking ACTIVATE_PROGRAM with Program='ZLOCAL_7777_CL'...")
        result = await client.invoke_function(
            "ACTIVATE_PROGRAM",
            {"Program": "ZLOCAL_7777_CL"}
        )
        
        print("\n✅ Success! Function called with properly formatted string parameter.")
        print("Result:", json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if "401" in str(e):
            print("   → Authentication required. Please add auth = (username, password)")
        elif "404" in str(e):
            print("   → Service not found. Check the URL and service name.")
        elif "connection" in str(e).lower():
            print("   → Connection failed. Check if SAP server is accessible.")

if __name__ == "__main__":
    print("Testing ACTIVATE_PROGRAM function with fixed string parameter formatting\n")
    print("The fix ensures that string parameters are properly quoted in the URL:")
    print("  Before fix: ?Program=ZLOCAL_7777_CL")
    print("  After fix:  ?Program='ZLOCAL_7777_CL'\n")
    
    asyncio.run(test_activate_program())