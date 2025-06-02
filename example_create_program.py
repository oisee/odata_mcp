#!/usr/bin/env python3
"""
Example script showing how to enable create/delete operations for ABAP programs
by overriding the metadata restrictions.

This demonstrates a workaround without modifying the core library.
"""

import asyncio
import json
import os
from typing import Optional, Dict, Any
from odata_mcp import MetadataParser, ODataClient


async def create_abap_program(
    service_url: str,
    auth: Optional[tuple] = None,
    program_name: str = "ZVIBE_002_TEST",
    program_content: str = None
):
    """Create an ABAP program using OData with metadata override."""
    
    # Default program content if not provided
    if program_content is None:
        program_content = f"""*&---------------------------------------------------------------------*
*& Report {program_name}
*&---------------------------------------------------------------------*
*&
*&---------------------------------------------------------------------*
REPORT {program_name}.

WRITE :/ 'Hello from {program_name}'."""
    
    print(f"Initializing OData client for {service_url}...")
    
    # Parse metadata
    parser = MetadataParser(service_url, auth, verbose=True)
    metadata = parser.parse()
    
    # Override metadata restrictions for PROGRAMSet
    if "PROGRAMSet" in metadata.entity_sets:
        print("Overriding PROGRAMSet metadata to enable create/update/delete...")
        metadata.entity_sets["PROGRAMSet"].creatable = True
        metadata.entity_sets["PROGRAMSet"].updatable = True
        metadata.entity_sets["PROGRAMSet"].deletable = True
    else:
        print("ERROR: PROGRAMSet not found in metadata!")
        return None
    
    # Similarly for other development objects if needed
    for entity_set_name in ["CLASSSet", "INTERFACESet", "PACKAGESet"]:
        if entity_set_name in metadata.entity_sets:
            metadata.entity_sets[entity_set_name].creatable = True
            metadata.entity_sets[entity_set_name].updatable = True
            metadata.entity_sets[entity_set_name].deletable = True
    
    # Create client with modified metadata
    client = ODataClient(metadata, auth, verbose=True)
    
    # Prepare program data
    program_data = {
        "Program": program_name,
        "Title": f"Program {program_name}",
        "SourceCode": program_content,
        "Package": "$TMP",  # Local package
        "ProgramType": "1"  # Executable program
    }
    
    print(f"\nCreating program {program_name}...")
    print(f"Data: {json.dumps(program_data, indent=2)}")
    
    try:
        # Create the program
        result = await client.create_entity("PROGRAMSet", program_data)
        print(f"\nSuccess! Program created:")
        print(json.dumps(result, indent=2, default=str))
        
        # Try to activate it
        print(f"\nAttempting to activate {program_name}...")
        try:
            # Note: This requires ACTIVATE_PROGRAM function import to be available
            activation_result = await client.invoke_function(
                "ACTIVATE_PROGRAM", 
                {"Program": program_name}
            )
            print(f"Activation result: {json.dumps(activation_result, indent=2, default=str)}")
        except Exception as e:
            print(f"Activation failed (this might be expected): {e}")
        
        return result
        
    except Exception as e:
        print(f"\nERROR creating program: {e}")
        return None


async def delete_abap_program(
    service_url: str,
    auth: Optional[tuple] = None,
    program_name: str = "ZVIBE_002_TEST"
):
    """Delete an ABAP program using OData with metadata override."""
    
    print(f"Initializing OData client for {service_url}...")
    
    # Parse metadata
    parser = MetadataParser(service_url, auth, verbose=True)
    metadata = parser.parse()
    
    # Override metadata restrictions for PROGRAMSet
    if "PROGRAMSet" in metadata.entity_sets:
        print("Overriding PROGRAMSet metadata to enable delete...")
        metadata.entity_sets["PROGRAMSet"].deletable = True
    else:
        print("ERROR: PROGRAMSet not found in metadata!")
        return None
    
    # Create client with modified metadata
    client = ODataClient(metadata, auth, verbose=True)
    
    print(f"\nDeleting program {program_name}...")
    
    try:
        # Delete the program
        result = await client.delete_entity("PROGRAMSet", {"Program": program_name})
        print(f"\nSuccess! Program deleted:")
        print(json.dumps(result, indent=2, default=str))
        return result
        
    except Exception as e:
        print(f"\nERROR deleting program: {e}")
        return None


async def list_programs(
    service_url: str,
    auth: Optional[tuple] = None,
    filter_pattern: str = "ZVIBE_"
):
    """List ABAP programs matching a pattern."""
    
    print(f"Initializing OData client for {service_url}...")
    
    # Parse metadata
    parser = MetadataParser(service_url, auth, verbose=False)
    metadata = parser.parse()
    
    # Create client
    client = ODataClient(metadata, auth, verbose=False)
    
    print(f"\nListing programs matching '{filter_pattern}'...")
    
    try:
        # List programs with filter
        params = {
            "$filter": f"startswith(Program, '{filter_pattern}')",
            "$top": 10,
            "$select": "Program,Title,Package,CreatedBy,CreatedDate"
        }
        
        result = await client.list_or_filter_entities("PROGRAMSet", params)
        
        if result.get("results"):
            print(f"\nFound {len(result['results'])} programs:")
            for prog in result["results"]:
                print(f"  - {prog['Program']}: {prog.get('Title', 'No title')}")
                print(f"    Package: {prog.get('Package', 'N/A')}, Created by: {prog.get('CreatedBy', 'N/A')}")
        else:
            print(f"\nNo programs found matching '{filter_pattern}'")
        
        return result
        
    except Exception as e:
        print(f"\nERROR listing programs: {e}")
        return None


async def main():
    """Main example function."""
    
    # Get configuration from environment
    service_url = os.environ.get('ODATA_SERVICE_URL', 'http://vhcala4hci:50000/sap/opu/odata/sap/ZODD_000_SRV')
    username = os.environ.get('ODATA_USERNAME')
    password = os.environ.get('ODATA_PASSWORD')
    
    if not username or not password:
        print("Please set ODATA_USERNAME and ODATA_PASSWORD environment variables")
        return
    
    auth = (username, password)
    
    # Example workflow
    print("=" * 60)
    print("ABAP Program CRUD Example")
    print("=" * 60)
    
    # 1. List existing programs
    await list_programs(service_url, auth)
    
    # 2. Create a new program
    print("\n" + "=" * 60)
    program_name = "ZVIBE_002_TEST"
    result = await create_abap_program(service_url, auth, program_name)
    
    if result:
        # 3. List programs again to confirm creation
        print("\n" + "=" * 60)
        await list_programs(service_url, auth)
        
        # 4. Optionally delete the program
        print("\n" + "=" * 60)
        response = input(f"\nDelete program {program_name}? (y/N): ")
        if response.lower() == 'y':
            await delete_abap_program(service_url, auth, program_name)
            
            # 5. List programs one more time
            print("\n" + "=" * 60)
            await list_programs(service_url, auth)


if __name__ == "__main__":
    asyncio.run(main())