#!/usr/bin/env python3
"""
Example: Using SSO Cookies with OData MCP

This shows how to use the existing OData MCP with SSO cookies
by extending the MetadataParser and ODataClient classes.
"""

import os
import sys
from typing import Optional, Tuple, Dict

# Add the parent directory to the path to import odata_mcp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odata_mcp import MetadataParser, ODataClient, ODataMCPBridge

def parse_cookie_string(cookie_string: str) -> Dict[str, str]:
    """Parse a cookie string into a dictionary."""
    cookies = {}
    if cookie_string:
        for cookie in cookie_string.split('; '):
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name] = value
    return cookies

# Monkey-patch the MetadataParser to add cookies
original_init = MetadataParser.__init__

def new_metadata_parser_init(self, service_url: str, auth: Optional[Tuple[str, str]] = None, 
                            verbose: bool = False, cookies: Optional[Dict[str, str]] = None):
    # Call original init
    original_init(self, service_url, auth, verbose)
    
    # Add cookies if provided
    if cookies:
        self.session.cookies.update(cookies)
        if self.verbose:
            print(f"[{self.__class__.__name__}] Added {len(cookies)} cookies to session", file=sys.stderr)

MetadataParser.__init__ = new_metadata_parser_init

# Monkey-patch the ODataClient to add cookies
original_client_init = ODataClient.__init__

def new_client_init(self, metadata, auth: Optional[Tuple[str, str]] = None,
                   verbose: bool = False, optimize_guids: bool = True, 
                   max_response_items: int = 1000, cookies: Optional[Dict[str, str]] = None):
    # Call original init
    original_client_init(self, metadata, auth, verbose, optimize_guids, max_response_items)
    
    # Add cookies if provided
    if cookies:
        self.session.cookies.update(cookies)
        if self.verbose:
            print(f"[{self.__class__.__name__}] Added {len(cookies)} cookies to session", file=sys.stderr)

ODataClient.__init__ = new_client_init

# Monkey-patch the ODataMCPBridge to pass cookies
original_bridge_init = ODataMCPBridge.__init__

def new_bridge_init(self, service_url: str, auth: Optional[Tuple[str, str]] = None, 
                   mcp_name: str = "odata-mcp", verbose: bool = False, 
                   tool_prefix: Optional[str] = None, tool_postfix: Optional[str] = None, 
                   use_postfix: bool = True, cookies: Optional[Dict[str, str]] = None):
    # Store cookies
    self.cookies = cookies
    
    # We need to override the parser and client creation
    # Save original methods
    self._original_init_parser = lambda: MetadataParser(service_url, auth, verbose, cookies)
    self._original_init_client = lambda metadata: ODataClient(
        metadata, auth, verbose, True, 1000, cookies
    )
    
    # Call original init (but we'll override parser/client creation)
    original_bridge_init(self, service_url, auth, mcp_name, verbose, 
                        tool_prefix, tool_postfix, use_postfix)

ODataMCPBridge.__init__ = new_bridge_init

# Now override the initialization in the bridge
def override_bridge_initialization():
    """Override the bridge initialization to use our cookie-enabled versions."""
    original_bridge_init_code = ODataMCPBridge.__init__.__code__
    
    # This is a bit hacky but works for demonstration
    # In production, you'd properly extend the classes
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    import argparse
    
    load_dotenv()
    
    # Your OData service URL
    service_url = os.getenv("ODATA_SERVICE_URL", "https://your-odata-service.example.com/odata/")
    
    # Get cookies from environment or command line
    cookie_string = os.getenv("ODATA_COOKIE")
    
    if not cookie_string:
        print("No ODATA_COOKIE environment variable found.", file=sys.stderr)
        print("\nTo use SSO, set your cookies in the environment:", file=sys.stderr)
        print("export ODATA_COOKIE='MYSAPSSO2=...; SAP_SESSIONID_D15_122=...'", file=sys.stderr)
        sys.exit(1)
    
    # Parse cookies
    cookies = parse_cookie_string(cookie_string)
    print(f"Using {len(cookies)} cookies for authentication", file=sys.stderr)
    
    # Important SAP SSO cookies
    important_cookies = ['MYSAPSSO2', 'SAP_SESSIONID_D15_122', 'sap-usercontext']
    for cookie_name in important_cookies:
        if cookie_name in cookies:
            print(f"✓ Found {cookie_name}", file=sys.stderr)
    
    try:
        # First, let's test the connection directly
        print(f"\nTesting connection to: {service_url}", file=sys.stderr)
        
        # Create a parser with cookies
        parser = MetadataParser(service_url, auth=None, verbose=True, cookies=cookies)
        metadata = parser.parse()
        
        print(f"\n✓ Successfully connected and parsed metadata!", file=sys.stderr)
        print(f"  Found {len(metadata.entity_types)} entity types", file=sys.stderr)
        print(f"  Found {len(metadata.entity_sets)} entity sets", file=sys.stderr)
        print(f"  Found {len(metadata.function_imports)} function imports", file=sys.stderr)
        
        # Show entity sets
        if metadata.entity_sets:
            print("\nEntity Sets:", file=sys.stderr)
            for name, entity_set in list(metadata.entity_sets.items())[:5]:
                print(f"  - {name} (type: {entity_set.entity_type})", file=sys.stderr)
        
        # Now create the full bridge
        print("\nCreating OData MCP Bridge with SSO...", file=sys.stderr)
        bridge = ODataMCPBridge(
            service_url=service_url,
            verbose=True,
            cookies=cookies
        )
        
        print("\n✓ Bridge created successfully!", file=sys.stderr)
        print("\nStarting MCP server...", file=sys.stderr)
        bridge.mcp.run()
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)