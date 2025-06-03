#!/usr/bin/env python3
"""
OData v2 to MCP Wrapper - Refactored modular version.

This module implements a bridge between OData v2 services and the Message Choreography
Processor (MCP) pattern, dynamically generating MCP tools based on OData metadata.
"""

import argparse
import os
import signal
import sys
import traceback
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

from odata_mcp_lib import ODataMCPBridge

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
        bridge = ODataMCPBridge(
            service_url, 
            auth, 
            verbose=args.verbose,
            tool_prefix=args.tool_prefix,
            tool_postfix=args.tool_postfix,
            use_postfix=not args.no_postfix
        )
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