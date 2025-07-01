#!/usr/bin/env python3
"""
OData v2 to MCP Wrapper - Refactored modular version.

This module implements a bridge between OData v2 services and the Message Choreography
Processor (MCP) pattern, dynamically generating MCP tools based on OData metadata.
"""

import argparse
import inspect
import json
import os
import signal
import sys
import traceback
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

from odata_mcp_lib import ODataMCPBridge
from odata_mcp_lib.transport.stdio import StdioTransport
from odata_mcp_lib.transport.http_sse import HttpSSETransport

# Load environment variables from .env file
load_dotenv()


def load_cookies_from_file(cookie_file: str) -> Optional[Dict[str, str]]:
    """Load cookies from a Netscape format cookie file."""
    cookies = {}
    
    try:
        with open(cookie_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Parse Netscape format (7 fields separated by tabs)
                parts = line.split('\t')
                if len(parts) >= 7:
                    # domain, flag, path, secure, expiration, name, value
                    cookie_name = parts[5]
                    cookie_value = parts[6]
                    cookies[cookie_name] = cookie_value
                elif '=' in line:
                    # Simple key=value format fallback
                    key, value = line.split('=', 1)
                    cookies[key.strip()] = value.strip()
                    
    except Exception as e:
        print(f"ERROR: Failed to read cookie file: {e}", file=sys.stderr)
        return None
        
    return cookies


def parse_cookie_string(cookie_string: str) -> Dict[str, str]:
    """Parse cookie string like 'key1=val1; key2=val2'."""
    cookies = {}
    for cookie in cookie_string.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def print_trace_info(bridge):
    """Print comprehensive trace information about the MCP bridge and all its tools."""
    print("=" * 80)
    print("🔍 OData MCP Bridge Trace Information")
    print("=" * 80)
    
    # Service Information
    print(f"\n🌐 Service URL: {bridge.service_url}")
    print(f"🔧 MCP Name: {bridge.mcp.name}")
    print(f"🎯 Tool Naming: {'Postfix' if bridge.use_postfix else 'Prefix'}")
    if bridge.use_postfix:
        print(f"📝 Tool Postfix: '{bridge.tool_postfix}'")
    else:
        print(f"📝 Tool Prefix: '{bridge.tool_prefix}'")
    print(f"📏 Tool Shrink: {bridge.tool_shrink}")
    print(f"🔍 Sort Tools: {bridge.sort_tools}")
    
    # Feature Flags
    print(f"\n⚙️ Feature Configuration:")
    print(f"   • Pagination Hints: {bridge.pagination_hints}")
    print(f"   • Legacy Date Format: {bridge.legacy_dates}")
    print(f"   • Verbose Errors: {bridge.verbose_errors}")
    print(f"   • Response Metadata: {bridge.response_metadata}")
    print(f"   • Max Response Size: {bridge.max_response_size:,} bytes")
    print(f"   • Max Items: {bridge.max_items}")
    
    # Entity/Function Filters
    if bridge.allowed_entities:
        print(f"🎯 Entity Filter: {', '.join(bridge.allowed_entities)}")
    else:
        print("🎯 Entity Filter: None (all entities)")
        
    if bridge.allowed_functions:
        print(f"⚙️ Function Filter: {', '.join(bridge.allowed_functions)}")
    else:
        print("⚙️ Function Filter: None (all functions)")
    
    # Authentication Info
    if bridge.auth:
        if isinstance(bridge.auth, tuple):
            print(f"🔐 Authentication: Basic (user: {bridge.auth[0]})")
        elif isinstance(bridge.auth, dict):
            print(f"🔐 Authentication: Cookie ({len(bridge.auth)} cookies)")
        else:
            print(f"🔐 Authentication: Custom ({type(bridge.auth).__name__})")
    else:
        print("🔐 Authentication: None (anonymous)")
    
    # Metadata Summary
    print(f"\n📊 Metadata Summary:")
    print(f"   • Service Description: {bridge.metadata.service_description or 'Not provided'}")
    print(f"   • Entity Types: {len(bridge.metadata.entity_types)}")
    print(f"   • Entity Sets: {len(bridge.metadata.entity_sets)}")
    print(f"   • Function Imports: {len(bridge.metadata.function_imports)}")
    print(f"   • OData Version: v2 (Python implementation)")
    
    # Get all registered tools from our tracking
    tools = bridge.all_registered_tools
    total_tools = len(tools)
    print(f"\n🛠️ Registered MCP Tools ({total_tools} total):")
    
    # Group tools by type
    service_tools = []
    entity_tools = {}
    function_tools = []
    
    for tool_name, tool_func in tools.items():
        if 'service_info' in tool_name:
            service_tools.append(tool_name)
        elif any(es_name in tool_name for es_name in bridge.metadata.entity_sets.keys()):
            # Find which entity set this tool belongs to
            for es_name in bridge.metadata.entity_sets.keys():
                if es_name in tool_name:
                    if es_name not in entity_tools:
                        entity_tools[es_name] = []
                    entity_tools[es_name].append(tool_name)
                    break
        else:
            function_tools.append(tool_name)
    
    # Print Service Tools
    if service_tools:
        print(f"\n   📋 Service Info Tools:")
        for tool in sorted(service_tools):
            print(f"      • {tool}")
    
    # Print Entity Tools
    if entity_tools:
        print(f"\n   📦 Entity Set Tools:")
        entity_items = sorted(entity_tools.items()) if bridge.sort_tools else entity_tools.items()
        for es_name, tool_list in entity_items:
            sorted_tools = sorted(tool_list) if bridge.sort_tools else tool_list
            print(f"      📁 {es_name}: {len(tool_list)} tools")
            for tool in sorted_tools:
                # Determine tool operation from name
                operation = "❓"
                if 'filter' in tool: operation = "🔍"
                elif 'count' in tool: operation = "🔢"
                elif 'search' in tool: operation = "🔎"
                elif 'get' in tool: operation = "📖"
                elif 'create' in tool: operation = "➕"
                elif 'update' in tool: operation = "✏️"
                elif 'delete' in tool: operation = "🗑️"
                print(f"         {operation} {tool}")
    
    # Print Function Tools
    if function_tools:
        print(f"\n   ⚙️ Function Import Tools:")
        sorted_functions = sorted(function_tools) if bridge.sort_tools else function_tools
        for tool in sorted_functions:
            print(f"      • {tool}")
    
    # Detailed Tool Information
    print(f"\n🔍 Detailed Tool Information:")
    print("=" * 60)
    
    all_tools = sorted(tools.keys()) if bridge.sort_tools else tools.keys()
    for tool_name in all_tools:
        tool_func = tools[tool_name]
        
        print(f"\n🛠️ Tool: {tool_name}")
        
        # Get function signature
        try:
            sig = inspect.signature(tool_func)
            params = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                type_hint = str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'
                has_default = param.default != inspect.Parameter.empty
                required = not has_default
                
                param_info = {
                    'name': param_name,
                    'type': type_hint,
                    'required': required,
                    'default': str(param.default) if has_default else None,
                    'description': None  # Add param description if available
                }
                params.append(param_info)
            
            # Print parameters
            if params:
                print("   📝 Parameters:")
                for p in params:
                    req_str = "required" if p['required'] else "optional"
                    default_str = f" (default: {p['default']})" if p['default'] else ""
                    desc_str = f" - {p['description']}" if p.get('description') else ""
                    print(f"      • {p['name']}: {p['type']} ({req_str}){default_str}{desc_str}")
            else:
                print("   📝 Parameters: None")
            
            # Get docstring
            docstring = inspect.getdoc(tool_func)
            if docstring:
                # Truncate long docstrings for readability
                lines = docstring.split('\n')
                if len(lines) > 5:
                    truncated_doc = '\n'.join(lines[:5]) + '\n      ... (truncated)'
                else:
                    truncated_doc = docstring
                print(f"   📚 Description:")
                for line in truncated_doc.split('\n'):
                    print(f"      {line}")
            else:
                print("   📚 Description: No documentation available")
                
        except Exception as e:
            print(f"   ❌ Error inspecting tool: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Trace complete - MCP bridge initialized successfully but not started")
    print("💡 Use without --trace to start the actual MCP server")
    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OData to MCP Wrapper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter  # Show defaults in help
    )
    # Add --service as an optional argument
    parser.add_argument("--service", dest="service_via_flag", help="URL of the OData service (overrides positional argument and ODATA_SERVICE_URL env var)")
    # Keep positional service_url as fallback
    parser.add_argument("service_url_pos", nargs='?', help="URL of the OData service (alternative to --service flag or env var)")
    
    # Authentication options (mutually exclusive group)
    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument("-u", "--user", help="Username for basic authentication (overrides ODATA_USERNAME env var)")
    auth_group.add_argument("--cookie-file", help="Path to cookie file in Netscape format")
    auth_group.add_argument("--cookie-string", help="Cookie string (key1=val1; key2=val2)")
    
    parser.add_argument("-p", "--password", help="Password for basic authentication (overrides ODATA_PASSWORD env var)")
    # Allow --debug as alias for --verbose
    parser.add_argument("-v", "--verbose", "--debug", dest="verbose", action="store_true", help="Enable verbose output to stderr")
    # Tool naming options
    parser.add_argument("--tool-prefix", help="Custom prefix for tool names (use with --no-postfix)")
    parser.add_argument("--tool-postfix", help="Custom postfix for tool names (default: _for_<service_id>)")
    parser.add_argument("--no-postfix", action="store_true", help="Use prefix instead of postfix for tool naming")
    parser.add_argument("--tool-shrink", action="store_true", help="Use shortened tool names (create_, get_, upd_, del_, search_, filter_)")
    parser.add_argument("--entities", help="Comma-separated list of entities to generate tools for (e.g., 'Products,Categories,Orders'). Supports wildcards: 'Product*,Order*')")
    parser.add_argument("--functions", help="Comma-separated list of function imports to generate tools for (e.g., 'GetProducts,CreateOrder'). Supports wildcards: 'Get*,Create*')")
    parser.add_argument("--sort-tools", action="store_true", default=True, help="Sort tools alphabetically in the output (default: True)")
    parser.add_argument("--no-sort-tools", dest="sort_tools", action="store_false", help="Disable alphabetical sorting of tools")
    parser.add_argument("--pagination-hints", action="store_true", help="Add pagination hints with suggested_next_call in responses")
    parser.add_argument("--legacy-dates", action="store_true", default=True, help="Support legacy /Date(milliseconds)/ format (default: True)")
    parser.add_argument("--no-legacy-dates", dest="legacy_dates", action="store_false", help="Disable legacy date format conversion")
    parser.add_argument("--verbose-errors", action="store_true", help="Include detailed error messages in responses")
    parser.add_argument("--response-metadata", action="store_true", help="Include __metadata blocks in responses")
    parser.add_argument("--max-response-size", type=int, default=5*1024*1024, help="Maximum response size in bytes (default: 5MB)")
    parser.add_argument("--max-items", type=int, default=100, help="Maximum items in response (default: 100)")
    parser.add_argument("--trace", action="store_true", help="Initialize MCP service and print all tools and parameters, then exit (useful for debugging)")
    
    # Transport options
    parser.add_argument("--transport", choices=["stdio", "http", "sse"], default="stdio", help="Transport type: 'stdio' (default) or 'http' (SSE)")
    parser.add_argument("--http-addr", default=":8080", help="HTTP server address (used with --transport http)")

    args = parser.parse_args()

    auth = None
    service_url = None

    # --- Configuration Handling ---
    # Priority: --service flag > Positional argument > Environment Variable > .env file

    # 1. --service flag
    if args.service_via_flag:
        service_url = args.service_via_flag
        if args.verbose: print("[VERBOSE] Using OData service URL from --service flag.", file=sys.stderr)

    # 2. Positional Argument
    if service_url is None and args.service_url_pos:
        service_url = args.service_url_pos
        if args.verbose: print("[VERBOSE] Using OData service URL from positional argument.", file=sys.stderr)

    # 3. Environment Variables (loaded by load_dotenv)
    if service_url is None:
        service_url = os.getenv("ODATA_URL") or os.getenv("ODATA_SERVICE_URL")
        if service_url and args.verbose: print("[VERBOSE] Using ODATA_URL from environment.", file=sys.stderr)

    # --- Authentication Handling ---
    # Priority: Cookie auth > Basic auth
    
    if args.cookie_file:
        # Cookie file authentication
        if not Path(args.cookie_file).exists():
            print(f"ERROR: Cookie file not found: {args.cookie_file}", file=sys.stderr)
            sys.exit(1)
        
        auth = load_cookies_from_file(args.cookie_file)
        if not auth:
            print("ERROR: Failed to load cookies from file", file=sys.stderr)
            sys.exit(1)
        
        if args.verbose:
            print(f"[VERBOSE] Loaded {len(auth)} cookies from file: {args.cookie_file}", file=sys.stderr)
            
    elif args.cookie_string:
        # Cookie string authentication
        auth = parse_cookie_string(args.cookie_string)
        if not auth:
            print("ERROR: Failed to parse cookie string", file=sys.stderr)
            sys.exit(1)
            
        if args.verbose:
            print(f"[VERBOSE] Parsed {len(auth)} cookies from string", file=sys.stderr)
            
    else:
        # Basic authentication
        env_user = os.getenv("ODATA_USER") or os.getenv("ODATA_USERNAME")
        env_pass = os.getenv("ODATA_PASS") or os.getenv("ODATA_PASSWORD")

        # Check for cookie environment variables
        env_cookie_file = os.getenv("ODATA_COOKIE_FILE")
        env_cookie_string = os.getenv("ODATA_COOKIE_STRING")
        
        if env_cookie_file and Path(env_cookie_file).exists():
            auth = load_cookies_from_file(env_cookie_file)
            if auth and args.verbose:
                print(f"[VERBOSE] Loaded {len(auth)} cookies from environment ODATA_COOKIE_FILE", file=sys.stderr)
        elif env_cookie_string:
            auth = parse_cookie_string(env_cookie_string)
            if auth and args.verbose:
                print(f"[VERBOSE] Parsed {len(auth)} cookies from environment ODATA_COOKIE_STRING", file=sys.stderr)
        else:
            # Determine final user/pass based on priority: CLI args > Env Vars
            final_user = args.user if args.user is not None else env_user
            final_pass = args.password if args.password is not None else env_pass

            if final_user and final_pass:
                auth = (final_user, final_pass)
                if args.verbose: print(f"[VERBOSE] Using basic authentication for user: {final_user}", file=sys.stderr)
            elif args.verbose:
                # Print only if verbose and no auth is configured
                print("[VERBOSE] No authentication provided or configured. Attempting anonymous access.", file=sys.stderr)

    # Check if service URL is determined
    if not service_url:
        # Error, print regardless of verbosity
        print("ERROR: OData service URL not provided.", file=sys.stderr)
        print("Provide it via the --service flag, as a positional argument, or ODATA_URL environment variable.", file=sys.stderr)
        parser.print_help(file=sys.stderr)  # Show help message
        sys.exit(1)

    # Handle SIGINT (Ctrl+C) and SIGTERM gracefully
    def signal_handler(sig, frame):
        # Print regardless of verbosity, as it's a shutdown event
        print(f"\n{signal.Signals(sig).name} received, shutting down server...", file=sys.stderr)
        # Add any cleanup logic needed here (e.g., close sessions)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)  # Handle TERM signal too

    # Create and run the bridge
    try:
        # Pass verbose flag and tool naming options to the bridge
        # Parse entities allowlist if provided
        allowed_entities = None
        if args.entities:
            allowed_entities = [e.strip() for e in args.entities.split(',') if e.strip()]
            if args.verbose:
                print(f"[VERBOSE] Filtering tools to only these entities: {allowed_entities}", file=sys.stderr)
        
        # Parse functions allowlist if provided
        allowed_functions = None
        if args.functions:
            allowed_functions = [f.strip() for f in args.functions.split(',') if f.strip()]
            if args.verbose:
                print(f"[VERBOSE] Filtering tools to only these functions: {allowed_functions}", file=sys.stderr)
        
        # Set up transport based on flag
        transport = None
        if args.transport in ["http", "sse"]:
            # Parse host and port from http_addr
            addr_parts = args.http_addr.split(":")
            if len(addr_parts) == 2 and addr_parts[0]:  # host:port
                host = addr_parts[0]
                port = int(addr_parts[1])
            elif len(addr_parts) == 2:  # :port
                host = "0.0.0.0"
                port = int(addr_parts[1])
            else:  # just port or invalid
                host = "0.0.0.0"
                try:
                    port = int(args.http_addr)
                except ValueError:
                    port = 8080
            
            if args.verbose:
                print(f"[VERBOSE] Starting HTTP/SSE transport on {host}:{port}", file=sys.stderr)
            transport = HttpSSETransport(host=host, port=port)
        elif args.verbose:
            print("[VERBOSE] Using stdio transport", file=sys.stderr)
        
        bridge = ODataMCPBridge(
            service_url, 
            auth, 
            verbose=args.verbose,
            tool_prefix=args.tool_prefix,
            tool_postfix=args.tool_postfix,
            use_postfix=not args.no_postfix,
            tool_shrink=args.tool_shrink,
            allowed_entities=allowed_entities,
            allowed_functions=allowed_functions,
            sort_tools=args.sort_tools,
            pagination_hints=args.pagination_hints,
            legacy_dates=args.legacy_dates,
            verbose_errors=args.verbose_errors,
            response_metadata=args.response_metadata,
            max_response_size=args.max_response_size,
            max_items=args.max_items,
            transport=transport
        )
        
        # Check if trace mode is enabled
        if args.trace:
            print_trace_info(bridge)
            sys.exit(0)
        
        bridge.run()
    except Exception as e:
        # Fatal error, print regardless of verbosity
        print(f"\n--- FATAL ERROR ---", file=sys.stderr)
        print(f"An unexpected error occurred during startup or runtime: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("-------------------", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()