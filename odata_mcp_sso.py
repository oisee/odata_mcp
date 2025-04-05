#!/usr/bin/env python3
"""
Extended OData MCP with SSO Cookie Support

This extends the main odata_mcp.py to support cookie-based authentication
for SSO scenarios.
"""

import os
import sys
from typing import Optional, Tuple, Dict

# Import the main OData MCP components
from odata_mcp import MetadataParser, ODataClient, ODataMCPBridge, ODataMetadata

class SSOMetadataParser(MetadataParser):
    """Extended MetadataParser that supports cookie-based SSO authentication."""
    
    def __init__(self, service_url: str, auth: Optional[Tuple[str, str]] = None, 
                 cookies: Optional[Dict[str, str]] = None, verbose: bool = False):
        super().__init__(service_url, auth, verbose)
        
        # If cookies are provided, add them to the session
        if cookies:
            self.session.cookies.update(cookies)
            self._log_verbose(f"Added {len(cookies)} cookies to session")

class SSOODataClient(ODataClient):
    """Extended ODataClient that supports cookie-based SSO authentication."""
    
    def __init__(self, metadata: ODataMetadata, auth: Optional[Tuple[str, str]] = None,
                 cookies: Optional[Dict[str, str]] = None, verbose: bool = False, 
                 optimize_guids: bool = True, max_response_items: int = 1000):
        super().__init__(metadata, auth, verbose, optimize_guids, max_response_items)
        
        # If cookies are provided, add them to the session
        if cookies:
            self.session.cookies.update(cookies)
            self._log_verbose(f"Added {len(cookies)} cookies to session")

class SSOODataMCPBridge(ODataMCPBridge):
    """Extended ODataMCPBridge that supports cookie-based SSO authentication."""
    
    def __init__(self, service_url: str, auth: Optional[Tuple[str, str]] = None, 
                 cookies: Optional[Dict[str, str]] = None, mcp_name: str = "odata-mcp", 
                 verbose: bool = False, tool_prefix: Optional[str] = None, 
                 tool_postfix: Optional[str] = None, use_postfix: bool = True):
        # Store cookies before calling parent __init__
        self.cookies = cookies
        
        # We need to override the initialization process to use our SSO-enabled classes
        self.service_url = service_url
        self.auth = auth
        self.verbose = verbose
        self.mcp = None  # Will be set by parent __init__
        self.registered_entity_tools = {}
        self.registered_function_tools = []
        self.use_postfix = use_postfix
        
        # Call parent's __init__ but it will use our overridden _initialize method
        super().__init__(service_url, auth, mcp_name, verbose, tool_prefix, tool_postfix, use_postfix)
    
    def __init__(self, service_url: str, auth: Optional[Tuple[str, str]] = None, 
                 cookies: Optional[Dict[str, str]] = None, mcp_name: str = "odata-mcp", 
                 verbose: bool = False, tool_prefix: Optional[str] = None, 
                 tool_postfix: Optional[str] = None, use_postfix: bool = True):
        # Store cookies
        self.cookies = cookies
        
        # Initialize parent but override parser and client creation
        self.service_url = service_url
        self.auth = auth
        self.verbose = verbose
        
        from fastmcp import FastMCP
        self.mcp = FastMCP(name=mcp_name, timeout=120)
        self.registered_entity_tools = {}
        self.registered_function_tools = []
        self.use_postfix = use_postfix
        
        # Generate service identifier from service URL
        service_id = self._generate_service_identifier(service_url)
        
        if use_postfix:
            self.tool_prefix = ""
            self.tool_postfix = tool_postfix or f"_for_{service_id}"
        else:
            self.tool_prefix = tool_prefix or f"{service_id}_"
            self.tool_postfix = ""

        try:
            self._log_verbose("Initializing SSO Metadata Parser...")
            self.parser = SSOMetadataParser(service_url, auth, cookies, verbose=self.verbose)
            self._log_verbose("Parsing OData Metadata...")
            self.metadata = self.parser.parse()
            self._log_verbose("Metadata Parsed. Initializing SSO OData Client...")
            self.client = SSOODataClient(
                self.metadata, 
                auth,
                cookies,
                verbose=self.verbose,
                optimize_guids=True,
                max_response_items=1000
            )
            self._log_verbose("SSO OData Client Initialized.")

            self._log_verbose("Registering MCP Tools...")
            self._register_tools()
            self._log_verbose("MCP Tools Registered.")

        except Exception as e:
            print(f"FATAL ERROR during initialization: {e}", file=sys.stderr)
            print("The wrapper cannot start. Please check the OData service URL, credentials, and network connectivity.", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)


def parse_cookie_string(cookie_string: str) -> Dict[str, str]:
    """Parse a cookie string into a dictionary."""
    cookies = {}
    if cookie_string:
        for cookie in cookie_string.split('; '):
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name] = value
    return cookies


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="OData to MCP Wrapper with SSO Support")
    parser.add_argument("service_url", nargs='?', help="URL of the OData service")
    parser.add_argument("--cookie", help="Cookie string for SSO authentication")
    parser.add_argument("--cookie-env", help="Environment variable containing cookie string", 
                       default="ODATA_COOKIE")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Get service URL
    service_url = args.service_url or os.getenv("ODATA_URL")
    if not service_url:
        print("ERROR: Service URL not provided", file=sys.stderr)
        sys.exit(1)
    
    # Get cookies
    cookie_string = args.cookie or os.getenv(args.cookie_env)
    cookies = parse_cookie_string(cookie_string) if cookie_string else None
    
    if args.verbose and cookies:
        print(f"[VERBOSE] Using {len(cookies)} cookies for authentication", file=sys.stderr)
    
    # Create bridge with SSO support
    bridge = SSOODataMCPBridge(
        service_url=service_url,
        cookies=cookies,
        verbose=args.verbose
    )
    
    # Run the MCP server
    print(f"Starting OData MCP Server with SSO support for: {service_url}", file=sys.stderr)
    bridge.mcp.run()