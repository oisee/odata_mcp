#!/usr/bin/env python3
"""
OData Graph Query Tool

This script provides an easy way to query graph data from the OData service
with automatic GUID optimization and response size management.
"""

import asyncio
import json
import os
import sys
from typing import Optional, List, Dict, Any
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odata_mcp import MetadataParser, ODataMetadata
from odata_mcp_enhanced import EnhancedODataClient
from odata_guid_fix import ODataGUIDHandler


class GraphQueryTool:
    """Tool for querying graph data from OData service."""
    
    def __init__(self, service_url: str, username: str, password: str, verbose: bool = False):
        """Initialize the graph query tool."""
        self.service_url = service_url
        self.auth = (username, password) if username and password else None
        self.verbose = verbose
        self.guid_handler = ODataGUIDHandler()
        
        # Parse metadata
        parser = MetadataParser(service_url, self.auth, verbose=verbose)
        self.metadata = parser.parse()
        
        # Create enhanced client
        self.client = EnhancedODataClient(
            metadata=self.metadata,
            auth=self.auth,
            verbose=verbose,
            optimize_guids=True,
            max_response_items=1000
        )
    
    async def query_nodes(self, seed: Optional[int] = None, 
                         limit: int = 10,
                         show_guids: bool = False) -> List[Dict[str, Any]]:
        """Query nodes with optimization."""
        print(f"\nQuerying nodes (seed={seed}, limit={limit})...")
        
        try:
            result = await self.client.list_nodes(
                seed=seed,
                max_nodes=limit,
                include_guid=show_guids
            )
            
            nodes = result.get('results', [])
            print(f"Found {len(nodes)} nodes")
            
            if result.get('_truncated'):
                print(f"Note: Results truncated to {result.get('_max_items')} items")
            
            return nodes
            
        except Exception as e:
            print(f"Error querying nodes: {e}")
            return []
    
    async def query_edges(self, seed: Optional[int] = None,
                         limit: int = 10,
                         show_guids: bool = False) -> List[Dict[str, Any]]:
        """Query edges with optimization."""
        print(f"\nQuerying edges (seed={seed}, limit={limit})...")
        
        try:
            result = await self.client.list_edges(
                seed=seed,
                max_edges=limit,
                include_guids=show_guids
            )
            
            edges = result.get('results', [])
            print(f"Found {len(edges)} edges")
            
            if result.get('_truncated'):
                print(f"Note: Results truncated to {result.get('_max_items')} items")
            
            return edges
            
        except Exception as e:
            print(f"Error querying edges: {e}")
            return []
    
    async def get_node_details(self, node_id: str, seed: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific node."""
        print(f"\nQuerying node details (id={node_id}, seed={seed})...")
        
        try:
            result = await self.client.get_node_with_edges(node_id, seed)
            print(f"Found node with {len(result.get('_outgoing_edges', []))} outgoing edges")
            return result
            
        except Exception as e:
            print(f"Error getting node details: {e}")
            return None
    
    def print_nodes(self, nodes: List[Dict[str, Any]], show_guids: bool = False):
        """Pretty print nodes."""
        if not nodes:
            print("No nodes to display")
            return
        
        print("\nNodes:")
        print("-" * 80)
        
        for i, node in enumerate(nodes):
            print(f"\n[{i+1}] Node: {node.get('Node', 'N/A')}")
            print(f"    Seed: {node.get('Seed', 'N/A')}")
            print(f"    Type: {node.get('ObjType', 'N/A')}")
            print(f"    Name: {node.get('ObjName', 'N/A')}")
            
            if show_guids and 'Id' in node:
                print(f"    GUID: {node['Id']}")
    
    def print_edges(self, edges: List[Dict[str, Any]], show_guids: bool = False):
        """Pretty print edges."""
        if not edges:
            print("No edges to display")
            return
        
        print("\nEdges:")
        print("-" * 80)
        
        for i, edge in enumerate(edges):
            print(f"\n[{i+1}] Edge Type: {edge.get('Etype', 'N/A')}")
            print(f"    Seed: {edge.get('Seed', 'N/A')}")
            
            if show_guids:
                if 'F' in edge:
                    print(f"    From: {edge['F']}")
                if 'T' in edge:
                    print(f"    To: {edge['T']}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Query graph data from OData service",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Connection parameters
    parser.add_argument("--url", help="OData service URL (or use ODATA_URL env var)")
    parser.add_argument("--user", help="Username (or use ODATA_USER env var)")
    parser.add_argument("--password", help="Password (or use ODATA_PASS env var)")
    
    # Query parameters
    parser.add_argument("--seed", type=int, help="Filter by seed value")
    parser.add_argument("--limit", type=int, default=10, help="Maximum items to retrieve")
    parser.add_argument("--show-guids", action="store_true", help="Show GUID fields")
    
    # Query type
    parser.add_argument("--nodes", action="store_true", help="Query nodes")
    parser.add_argument("--edges", action="store_true", help="Query edges")
    parser.add_argument("--node-details", help="Get details for specific node ID")
    
    # Other options
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    # Get connection parameters
    service_url = args.url or os.getenv("ODATA_URL")
    username = args.user or os.getenv("ODATA_USER")
    password = args.password or os.getenv("ODATA_PASS")
    
    if not service_url:
        print("Error: Service URL not provided. Use --url or set ODATA_URL env var")
        sys.exit(1)
    
    # Create query tool
    tool = GraphQueryTool(service_url, username, password, args.verbose)
    
    # Execute queries
    results = {}
    
    if args.nodes:
        nodes = await tool.query_nodes(args.seed, args.limit, args.show_guids)
        results['nodes'] = nodes
        
        if not args.json:
            tool.print_nodes(nodes, args.show_guids)
    
    if args.edges:
        edges = await tool.query_edges(args.seed, args.limit, args.show_guids)
        results['edges'] = edges
        
        if not args.json:
            tool.print_edges(edges, args.show_guids)
    
    if args.node_details:
        if args.seed is None:
            print("Error: --seed is required when using --node-details")
            sys.exit(1)
        
        node = await tool.get_node_details(args.node_details, args.seed)
        results['node_details'] = node
        
        if not args.json and node:
            print("\nNode Details:")
            print(json.dumps(node, indent=2))
    
    # Output JSON if requested
    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())