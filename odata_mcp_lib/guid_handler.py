"""
GUID handling utilities for OData responses.
"""

import base64
import re
from typing import Any, Dict, List


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