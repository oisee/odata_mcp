#!/usr/bin/env python3
"""
Enhanced OData MCP Bridge with Create/Delete Override Support

This version allows overriding metadata restrictions to force-enable
create, update, and delete operations for entity sets that the OData
service metadata marks as read-only.
"""

import json
from typing import Dict, List, Optional, Set
from odata_mcp import ODataMCPBridge, EntitySet

class ODataMCPBridgeWithOverrides(ODataMCPBridge):
    """Enhanced OData MCP Bridge that allows overriding entity set restrictions."""
    
    def __init__(self, 
                 service_url: str, 
                 auth: Optional[tuple] = None, 
                 mcp_name: str = "odata-mcp",
                 verbose: bool = False,
                 tool_prefix: Optional[str] = None,
                 tool_postfix: Optional[str] = None,
                 use_postfix: bool = True,
                 override_readonly: bool = False,
                 entity_overrides: Optional[Dict[str, Dict[str, bool]]] = None):
        """
        Initialize OData MCP Bridge with override support.
        
        Args:
            service_url: OData service URL
            auth: Authentication credentials (username, password)
            mcp_name: Name for the MCP server
            verbose: Enable verbose logging
            tool_prefix: Prefix for tool names (if use_postfix=False)
            tool_postfix: Postfix for tool names (if use_postfix=True)
            use_postfix: Whether to use postfix (True) or prefix (False)
            override_readonly: If True, force all entity sets to be creatable/updatable/deletable
            entity_overrides: Dict mapping entity set names to override flags
                             e.g., {"PROGRAMSet": {"creatable": True, "deletable": True}}
        """
        self.override_readonly = override_readonly
        self.entity_overrides = entity_overrides or {}
        
        # Initialize parent class
        super().__init__(
            service_url=service_url,
            auth=auth,
            mcp_name=mcp_name,
            verbose=verbose,
            tool_prefix=tool_prefix,
            tool_postfix=tool_postfix,
            use_postfix=use_postfix
        )
    
    def _apply_overrides(self):
        """Apply overrides to entity set metadata after parsing."""
        if self.verbose:
            self._log_verbose("Applying entity set overrides...")
        
        for entity_set_name, entity_set in self.metadata.entity_sets.items():
            original_state = {
                'creatable': entity_set.creatable,
                'updatable': entity_set.updatable,
                'deletable': entity_set.deletable,
                'searchable': entity_set.searchable
            }
            
            # Apply global override
            if self.override_readonly:
                entity_set.creatable = True
                entity_set.updatable = True
                entity_set.deletable = True
                if self.verbose:
                    self._log_verbose(f"Globally overriding {entity_set_name} to be fully writable")
            
            # Apply specific entity overrides
            if entity_set_name in self.entity_overrides:
                overrides = self.entity_overrides[entity_set_name]
                for flag, value in overrides.items():
                    if hasattr(entity_set, flag):
                        setattr(entity_set, flag, value)
                        if self.verbose:
                            self._log_verbose(f"Overriding {entity_set_name}.{flag} to {value}")
            
            # Log changes
            if self.verbose:
                new_state = {
                    'creatable': entity_set.creatable,
                    'updatable': entity_set.updatable,
                    'deletable': entity_set.deletable,
                    'searchable': entity_set.searchable
                }
                if original_state != new_state:
                    self._log_verbose(f"{entity_set_name} changed from {original_state} to {new_state}")
    
    def _register_tools(self):
        """Override to apply overrides before registering tools."""
        # Apply overrides first
        self._apply_overrides()
        
        # Then register tools with the modified metadata
        super()._register_tools()
        
        if self.verbose:
            # Log summary of what tools were registered
            self._log_verbose("\nRegistered tools summary:")
            for entity_set_name, tools in self.registered_entity_tools.items():
                self._log_verbose(f"  {entity_set_name}: {', '.join(tools)}")


def main():
    """Example usage with override support."""
    import os
    import asyncio
    from mcp import stdio_server
    
    # Get configuration from environment
    service_url = os.environ.get('ODATA_SERVICE_URL', 'http://vhcala4hci:50000/sap/opu/odata/sap/ZODD_000_SRV')
    username = os.environ.get('ODATA_USERNAME')
    password = os.environ.get('ODATA_PASSWORD')
    verbose = os.environ.get('ODATA_VERBOSE', 'false').lower() == 'true'
    override_readonly = os.environ.get('ODATA_OVERRIDE_READONLY', 'false').lower() == 'true'
    
    # Parse entity-specific overrides from environment
    # Format: ODATA_OVERRIDE_<EntitySetName>_<Flag>=true/false
    entity_overrides = {}
    for key, value in os.environ.items():
        if key.startswith('ODATA_OVERRIDE_') and not key == 'ODATA_OVERRIDE_READONLY':
            parts = key.split('_')
            if len(parts) >= 4:  # ODATA_OVERRIDE_EntitySetName_Flag
                entity_set_name = '_'.join(parts[2:-1])
                flag = parts[-1].lower()
                if flag in ['creatable', 'updatable', 'deletable', 'searchable']:
                    if entity_set_name not in entity_overrides:
                        entity_overrides[entity_set_name] = {}
                    entity_overrides[entity_set_name][flag] = value.lower() == 'true'
    
    # Create auth tuple if credentials provided
    auth = (username, password) if username and password else None
    
    # Create bridge with override support
    bridge = ODataMCPBridgeWithOverrides(
        service_url=service_url,
        auth=auth,
        mcp_name="odata-mcp-enhanced",
        verbose=verbose,
        override_readonly=override_readonly,
        entity_overrides=entity_overrides
    )
    
    if verbose:
        print(f"Starting enhanced OData MCP server for {service_url}", file=sys.stderr)
        if override_readonly:
            print("Global override enabled - all entities are writable", file=sys.stderr)
        if entity_overrides:
            print(f"Entity-specific overrides: {entity_overrides}", file=sys.stderr)
    
    # Run the server
    asyncio.run(stdio_server(bridge.mcp))


if __name__ == "__main__":
    main()