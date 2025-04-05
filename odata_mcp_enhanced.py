#!/usr/bin/env python3
"""
Enhanced OData MCP Wrapper with GUID Handling and Response Optimization

This enhanced version includes:
- Automatic base64 GUID to standard GUID conversion
- Response size optimization
- XML namespace fixing for proper serialization
- Specialized handling for graph data models
"""

import json
from typing import Any, Dict, List, Optional
from odata_mcp import ODataClient, ODataMetadata
from odata_guid_fix import ODataGUIDHandler, GraphDataOptimizer, XMLNamespaceFixer


class EnhancedODataClient(ODataClient):
    """Enhanced OData client with GUID handling and response optimization."""
    
    def __init__(self, metadata: ODataMetadata, auth: Optional[tuple] = None, 
                 verbose: bool = False, optimize_guids: bool = True,
                 max_response_items: int = 1000):
        """
        Initialize enhanced OData client.
        
        Args:
            metadata: OData service metadata
            auth: Authentication credentials
            verbose: Enable verbose logging
            optimize_guids: Automatically convert base64 GUIDs to standard format
            max_response_items: Maximum items to return in collection responses
        """
        super().__init__(metadata, auth, verbose)
        self.optimize_guids = optimize_guids
        self.max_response_items = max_response_items
        self.guid_handler = ODataGUIDHandler()
        self.graph_optimizer = GraphDataOptimizer()
        
        # Identify GUID fields from metadata
        self._identify_guid_fields()
    
    def _identify_guid_fields(self):
        """Identify fields that are likely GUIDs based on metadata."""
        self.guid_fields_by_entity = {}
        
        for entity_name, entity_type in self.metadata.entity_types.items():
            guid_fields = []
            for prop in entity_type.properties:
                # Binary fields with GUID-like names
                if (prop.type == "Edm.Binary" and 
                    any(name in prop.name.upper() for name in ['ID', 'GUID', 'F', 'T'])):
                    guid_fields.append(prop.name)
                # Also check description for GUID hints
                elif prop.description and 'GUID' in prop.description.upper():
                    guid_fields.append(prop.name)
            
            self.guid_fields_by_entity[entity_name] = guid_fields
            if guid_fields and self.verbose:
                self._log_verbose(f"Identified GUID fields for {entity_name}: {guid_fields}")
    
    def _parse_odata_response(self, response) -> Dict[str, Any]:
        """Parse and optimize OData response."""
        # First, get the standard parsed response
        parsed = super()._parse_odata_response(response)
        
        # Skip optimization if disabled
        if not self.optimize_guids:
            return parsed
        
        # Optimize the response
        return self._optimize_response(parsed)
    
    def _optimize_response(self, data: Any) -> Any:
        """Optimize response data by converting GUIDs and limiting size."""
        if isinstance(data, dict):
            # Check if it's a collection response
            if 'results' in data and isinstance(data['results'], list):
                # Get entity type from the first result if available
                entity_type = self._guess_entity_type(data['results'][0] if data['results'] else {})
                guid_fields = self.guid_fields_by_entity.get(entity_type, [])
                
                # Optimize the results
                data['results'] = self.guid_handler.optimize_odata_response(
                    data['results'], 
                    guid_fields=guid_fields,
                    max_items=self.max_response_items
                )
                
                # Add optimization info
                if len(data['results']) == self.max_response_items:
                    data['_truncated'] = True
                    data['_max_items'] = self.max_response_items
            else:
                # Single entity response
                entity_type = self._guess_entity_type(data)
                guid_fields = self.guid_fields_by_entity.get(entity_type, [])
                data = self.guid_handler.optimize_odata_response(data, guid_fields=guid_fields)
        
        return data
    
    def _guess_entity_type(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Guess entity type from entity data structure."""
        if not entity_data:
            return None
        
        # Check metadata if available
        if '__metadata' in entity_data and 'type' in entity_data['__metadata']:
            # Extract entity type from fully qualified name
            fqn = entity_data['__metadata']['type']
            return fqn.split('.')[-1] if '.' in fqn else fqn
        
        # Otherwise, try to match by properties
        entity_props = set(entity_data.keys())
        for entity_type, type_def in self.metadata.entity_types.items():
            type_props = {prop.name for prop in type_def.properties}
            # If entity has most of the type's properties, it's likely that type
            if len(entity_props & type_props) >= len(type_props) * 0.7:
                return entity_type
        
        return None
    
    async def list_nodes(self, seed: Optional[int] = None, 
                        max_nodes: int = 100,
                        include_guid: bool = False) -> Dict[str, Any]:
        """
        Specialized method for listing graph nodes.
        
        Args:
            seed: Optional seed value to filter by
            max_nodes: Maximum number of nodes to retrieve
            include_guid: Whether to include the binary GUID field
            
        Returns:
            Optimized node data
        """
        # Build optimized query
        select_fields = ['Seed', 'Node', 'ObjType', 'ObjName']
        if include_guid:
            select_fields.append('Id')
        
        params = self.graph_optimizer.build_node_query(
            seed=seed,
            select_fields=select_fields,
            max_nodes=max_nodes
        )
        
        # Use the standard list method
        result = await self.list_or_filter_entities('ZLLM_00_NODESet', params)
        
        # Add query info
        result['_query_info'] = {
            'entity_set': 'ZLLM_00_NODESet',
            'optimized': True,
            'fields_selected': select_fields
        }
        
        return result
    
    async def list_edges(self, seed: Optional[int] = None,
                        max_edges: int = 100,
                        include_guids: bool = False) -> Dict[str, Any]:
        """
        Specialized method for listing graph edges.
        
        Args:
            seed: Optional seed value to filter by
            max_edges: Maximum number of edges to retrieve
            include_guids: Whether to include the binary GUID fields
            
        Returns:
            Optimized edge data
        """
        # Build optimized query
        select_fields = ['Seed', 'Etype']
        if include_guids:
            select_fields.extend(['F', 'T'])
        
        params = self.graph_optimizer.build_edge_query(
            seed=seed,
            select_fields=select_fields,
            max_edges=max_edges
        )
        
        # Use the standard list method
        result = await self.list_or_filter_entities('ZLLM_00_EDGESet', params)
        
        # Add query info
        result['_query_info'] = {
            'entity_set': 'ZLLM_00_EDGESet',
            'optimized': True,
            'fields_selected': select_fields
        }
        
        return result
    
    async def get_node_with_edges(self, node_id: str, seed: int) -> Dict[str, Any]:
        """
        Get a node with its connected edges.
        
        Args:
            node_id: Node ID (can be base64 or standard GUID)
            seed: Seed value
            
        Returns:
            Node data with connected edges
        """
        # Convert to base64 if needed
        if '-' in node_id:
            node_id_base64 = self.guid_handler.guid_to_base64(node_id)
        else:
            node_id_base64 = node_id
        
        # Get the node
        node_result = await self.get_entity('ZLLM_00_NODESet', {
            'Seed': seed,
            'Id': node_id_base64
        })
        
        # Try to get edges (this might fail if filtering by binary is not supported)
        try:
            # Get outgoing edges
            outgoing_params = {
                '$filter': f"Seed eq {seed}",
                '$top': 50,
                '$select': 'Etype,T'
            }
            outgoing = await self.list_or_filter_entities('ZLLM_00_EDGESet', outgoing_params)
            
            # Filter in memory if backend doesn't support binary field filtering
            if outgoing.get('results'):
                node_id_optimized = self.guid_handler.base64_to_guid(node_id_base64)
                outgoing['results'] = [
                    edge for edge in outgoing['results']
                    if self.guid_handler.base64_to_guid(edge.get('F', '')) == node_id_optimized
                ]
            
            node_result['_outgoing_edges'] = outgoing.get('results', [])
        except Exception as e:
            if self.verbose:
                self._log_verbose(f"Could not fetch edges: {e}")
            node_result['_outgoing_edges'] = []
        
        return node_result


# Example usage
async def example_enhanced_usage():
    """Example of using the enhanced OData client."""
    from odata_mcp import ODataMetadata, EntityType, EntityProperty, EntitySet
    
    # Create sample metadata for a graph service
    metadata = ODataMetadata(
        service_url="http://example.com/odata",
        entity_types={
            "ZLLM_00_NODE": EntityType(
                name="ZLLM_00_NODE",
                properties=[
                    EntityProperty(name="Seed", type="Edm.Int32", is_key=True),
                    EntityProperty(name="Id", type="Edm.Binary", is_key=True, description="GUID"),
                    EntityProperty(name="Node", type="Edm.String"),
                    EntityProperty(name="ObjType", type="Edm.String"),
                    EntityProperty(name="ObjName", type="Edm.String")
                ],
                key_properties=["Seed", "Id"]
            )
        },
        entity_sets={
            "ZLLM_00_NODESet": EntitySet(
                name="ZLLM_00_NODESet",
                entity_type="ZLLM_00_NODE"
            )
        }
    )
    
    # Create enhanced client
    client = EnhancedODataClient(
        metadata=metadata,
        verbose=True,
        optimize_guids=True,
        max_response_items=100
    )
    
    # Example: List nodes with optimization
    print("Fetching optimized node list...")
    nodes = await client.list_nodes(seed=1, max_nodes=10)
    print(json.dumps(nodes, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_enhanced_usage())