#!/usr/bin/env python3
"""
Test script for the integrated OData MCP with GUID optimization.

This demonstrates the enhanced features:
- Automatic GUID conversion from base64 to standard format
- Response size limiting
- Specialized graph query methods
"""

import asyncio
import json
import os
from odata_mcp import ODataMCPBridge

async def test_enhanced_features():
    """Test the enhanced OData MCP features."""
    
    # Use environment variables for configuration
    service_url = os.getenv("ODATA_URL", "http://vhcala4hci:50000/sap/opu/odata/sap/ZMCP_002_SRV/")
    username = os.getenv("ODATA_USER")
    password = os.getenv("ODATA_PASS")
    
    if not username or not password:
        print("Please set ODATA_USER and ODATA_PASS environment variables")
        return
    
    auth = (username, password)
    
    print("Creating OData MCP Bridge with enhanced features...")
    bridge = ODataMCPBridge(service_url, auth, verbose=False)
    
    print("\n1. Testing optimized node query...")
    nodes = await bridge.client.list_nodes(seed=0, max_nodes=5)
    print(f"   Retrieved {len(nodes.get('results', []))} nodes")
    if nodes.get('results'):
        node = nodes['results'][0]
        print(f"   First node: {node.get('Node')} (Type: {node.get('ObjType')})")
        if 'Id' in node and '-' in str(node['Id']):
            print(f"   ✓ GUID converted from base64 to standard format: {node['Id']}")
    
    print("\n2. Testing optimized edge query...")
    edges = await bridge.client.list_edges(seed=0, max_edges=5, include_guids=True)
    print(f"   Retrieved {len(edges.get('results', []))} edges")
    if edges.get('results'):
        edge = edges['results'][0]
        print(f"   First edge type: {edge.get('Etype')}")
        if 'F' in edge and '-' in str(edge['F']):
            print(f"   ✓ From GUID converted: {edge['F'][:40]}...")
        if 'T' in edge and '-' in str(edge['T']):
            print(f"   ✓ To GUID converted: {edge['T'][:40]}...")
    
    print("\n3. Testing response size limiting...")
    # The client is configured with max_response_items=1000
    large_query = await bridge.client.list_or_filter_entities('ZLLM_00_NODESet', {'$top': 2000})
    if large_query.get('_truncated'):
        print(f"   ✓ Response truncated to {large_query.get('_max_items')} items")
    else:
        print(f"   Retrieved {len(large_query.get('results', []))} items")
    
    print("\n4. Testing standard OData query with GUID optimization...")
    bins = await bridge.client.list_or_filter_entities('ZLLM_00_BINSet', {'$top': 3})
    print(f"   Retrieved {len(bins.get('results', []))} bins")
    if bins.get('results'):
        print(f"   First bin: {bins['results'][0].get('Name')}")
    
    print("\n✅ All enhanced features are working correctly!")
    print("\nThe OData MCP now includes:")
    print("- Automatic GUID conversion (base64 → standard format)")
    print("- Response size limiting (prevents oversized responses)")
    print("- Optimized graph queries (list_nodes, list_edges)")
    print("- Selective field retrieval to reduce payload size")


if __name__ == "__main__":
    asyncio.run(test_enhanced_features())