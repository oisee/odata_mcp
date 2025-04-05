#!/usr/bin/env python3
"""
OData GUID Handling Fix for Graph Data Model

This module provides fixes for handling Binary GUID fields in OData responses,
particularly for graph data models with nodes and edges.
"""

import base64
import json
import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime


class ODataGUIDHandler:
    """Handles conversion and optimization of GUID fields in OData responses."""
    
    @staticmethod
    def base64_to_guid(base64_string: str) -> str:
        """
        Convert base64 encoded binary GUID to standard GUID format.
        
        Args:
            base64_string: Base64 encoded binary GUID
            
        Returns:
            Standard GUID string format (e.g., '550D1E94-44FB-4E8D-8E5C-8F63E5C20F80')
        """
        try:
            # Decode base64 to bytes
            guid_bytes = base64.b64decode(base64_string)
            
            # Convert to hex and format as GUID
            hex_string = guid_bytes.hex().upper()
            
            # Format as standard GUID: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            if len(hex_string) == 32:
                return f"{hex_string[0:8]}-{hex_string[8:12]}-{hex_string[12:16]}-{hex_string[16:20]}-{hex_string[20:32]}"
            else:
                # Return original if not standard GUID length
                return base64_string
        except Exception:
            # Return original on any error
            return base64_string
    
    @staticmethod
    def guid_to_base64(guid_string: str) -> str:
        """
        Convert standard GUID format to base64 encoded binary.
        
        Args:
            guid_string: Standard GUID string
            
        Returns:
            Base64 encoded binary GUID
        """
        try:
            # Remove hyphens and convert to bytes
            hex_string = guid_string.replace('-', '')
            guid_bytes = bytes.fromhex(hex_string)
            
            # Encode to base64
            return base64.b64encode(guid_bytes).decode('utf-8')
        except Exception:
            # Return original on any error
            return guid_string
    
    @classmethod
    def optimize_odata_response(cls, response_data: Any, 
                              guid_fields: List[str] = None,
                              max_items: int = None) -> Any:
        """
        Optimize OData response by converting GUID fields and limiting size.
        
        Args:
            response_data: The OData response data
            guid_fields: List of field names that contain GUIDs
            max_items: Maximum number of items to return
            
        Returns:
            Optimized response data
        """
        if guid_fields is None:
            # Common GUID field names in graph models
            guid_fields = ['Id', 'F', 'T', 'FromId', 'ToId']
        
        if isinstance(response_data, dict):
            # Handle single entity
            return cls._convert_entity_guids(response_data, guid_fields)
        elif isinstance(response_data, list):
            # Handle collection
            if max_items and len(response_data) > max_items:
                response_data = response_data[:max_items]
            return [cls._convert_entity_guids(item, guid_fields) for item in response_data]
        
        return response_data
    
    @classmethod
    def _convert_entity_guids(cls, entity: Dict[str, Any], 
                            guid_fields: List[str]) -> Dict[str, Any]:
        """Convert GUID fields in a single entity."""
        optimized = entity.copy()
        
        for field in guid_fields:
            if field in optimized and isinstance(optimized[field], str):
                # Check if it looks like base64
                if cls._is_base64(optimized[field]):
                    optimized[field] = cls.base64_to_guid(optimized[field])
        
        return optimized
    
    @staticmethod
    def _is_base64(s: str) -> bool:
        """Check if a string appears to be base64 encoded."""
        # Base64 pattern with padding
        pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
        
        # Check length is multiple of 4 and matches pattern
        return len(s) % 4 == 0 and bool(pattern.match(s))


class GraphDataOptimizer:
    """Optimizes graph data queries for OData services."""
    
    @staticmethod
    def build_node_query(seed: Optional[int] = None,
                        select_fields: Optional[List[str]] = None,
                        max_nodes: int = 100) -> Dict[str, Any]:
        """
        Build optimized query parameters for nodes.
        
        Args:
            seed: Optional seed value to filter by
            select_fields: Fields to select (defaults to essential fields)
            max_nodes: Maximum number of nodes to retrieve
            
        Returns:
            Query parameters dictionary
        """
        params = {
            '$top': max_nodes,
            '$format': 'json'  # Prefer JSON over XML
        }
        
        # Default essential fields to reduce response size
        if select_fields is None:
            select_fields = ['Seed', 'Node', 'ObjType', 'ObjName']
        
        if select_fields:
            params['$select'] = ','.join(select_fields)
        
        if seed is not None:
            params['$filter'] = f'Seed eq {seed}'
        
        return params
    
    @staticmethod
    def build_edge_query(seed: Optional[int] = None,
                        from_id: Optional[str] = None,
                        to_id: Optional[str] = None,
                        select_fields: Optional[List[str]] = None,
                        max_edges: int = 100) -> Dict[str, Any]:
        """
        Build optimized query parameters for edges.
        
        Args:
            seed: Optional seed value to filter by
            from_id: Optional source node ID (as base64)
            to_id: Optional target node ID (as base64)
            select_fields: Fields to select
            max_edges: Maximum number of edges to retrieve
            
        Returns:
            Query parameters dictionary
        """
        params = {
            '$top': max_edges,
            '$format': 'json'
        }
        
        # Default fields excluding large binary GUIDs initially
        if select_fields is None:
            select_fields = ['Seed', 'Etype']
        
        if select_fields:
            params['$select'] = ','.join(select_fields)
        
        # Build filter conditions
        filters = []
        if seed is not None:
            filters.append(f'Seed eq {seed}')
        
        # Note: Filtering by binary fields might not be supported
        # These are included for reference but may need backend support
        if from_id:
            # This might not work with binary fields
            filters.append(f"F eq '{from_id}'")
        if to_id:
            filters.append(f"T eq '{to_id}'")
        
        if filters:
            params['$filter'] = ' and '.join(filters)
        
        return params


class XMLNamespaceFixer:
    """Fixes XML namespace issues in OData responses."""
    
    ODATA_NAMESPACES = {
        'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
        'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
        'atom': 'http://www.w3.org/2005/Atom'
    }
    
    @classmethod
    def add_namespaces_to_xml(cls, xml_content: str) -> str:
        """
        Add proper namespace declarations to XML content.
        
        Args:
            xml_content: Original XML content
            
        Returns:
            Fixed XML content with proper namespaces
        """
        # Check if namespaces are already declared
        if 'xmlns:d=' in xml_content and 'xmlns:m=' in xml_content:
            return xml_content
        
        # Add namespace declarations to root element
        namespace_attrs = ' '.join([f'xmlns:{prefix}="{uri}"' 
                                   for prefix, uri in cls.ODATA_NAMESPACES.items()])
        
        # Find the root element and add namespaces
        root_pattern = r'<(\w+)([^>]*)>'
        match = re.search(root_pattern, xml_content)
        
        if match:
            root_tag = match.group(1)
            existing_attrs = match.group(2)
            
            # Construct new root element with namespaces
            new_root = f'<{root_tag}{existing_attrs} {namespace_attrs}>'
            xml_content = xml_content.replace(match.group(0), new_root, 1)
        
        return xml_content
    
    @staticmethod
    def escape_xml_attribute_value(value: str) -> str:
        """
        Properly escape values for XML attributes.
        
        Args:
            value: Raw attribute value
            
        Returns:
            Properly escaped value
        """
        # XML attribute escape sequences
        escapes = {
            '"': '&quot;',
            "'": '&apos;',
            '<': '&lt;',
            '>': '&gt;',
            '&': '&amp;'
        }
        
        for char, escape in escapes.items():
            value = value.replace(char, escape)
        
        return value


# Example usage and testing functions
def test_guid_conversion():
    """Test GUID conversion functions."""
    handler = ODataGUIDHandler()
    
    # Test base64 to GUID
    base64_guid = "AkkEEAAEH9CL4dDCiWvlwg=="
    standard_guid = handler.base64_to_guid(base64_guid)
    print(f"Base64: {base64_guid}")
    print(f"GUID: {standard_guid}")
    
    # Test GUID to base64
    guid = "550D1E94-44FB-4E8D-8E5C-8F63E5C20F80"
    base64_result = handler.guid_to_base64(guid)
    print(f"\nGUID: {guid}")
    print(f"Base64: {base64_result}")


def example_response_optimization():
    """Example of optimizing an OData response."""
    # Sample response with base64 GUIDs
    sample_response = {
        "results": [
            {
                "Seed": 1,
                "Id": "AkkEEAAEH9CL4dDCiWvlwg==",
                "Node": "CL_TEST_CLASS",
                "ObjType": "CLAS",
                "ObjName": "CL_TEST_CLASS"
            },
            {
                "Seed": 1,
                "Id": "BZkFGBBFI+GL5tHDjXwmyh==",
                "Node": "IF_TEST_INTERFACE",
                "ObjType": "INTF",
                "ObjName": "IF_TEST_INTERFACE"
            }
        ]
    }
    
    handler = ODataGUIDHandler()
    optimized = handler.optimize_odata_response(sample_response["results"])
    
    print("\nOptimized Response:")
    print(json.dumps(optimized, indent=2))


if __name__ == "__main__":
    print("OData GUID Handling Tests\n")
    print("=" * 50)
    
    test_guid_conversion()
    print("\n" + "=" * 50)
    example_response_optimization()