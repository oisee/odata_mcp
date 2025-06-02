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
from dotenv import load_dotenv

from odata_mcp_lib import ODataMCPBridge

# Load environment variables from .env file
load_dotenv()


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
    parser.add_argument("-u", "--user", help="Username for basic authentication (overrides ODATA_USERNAME env var)")
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

    env_user = os.getenv("ODATA_USER") or os.getenv("ODATA_USERNAME")
    env_pass = os.getenv("ODATA_PASS") or os.getenv("ODATA_PASSWORD")

    # Determine final user/pass based on priority: CLI args > Env Vars
    final_user = args.user if args.user is not None else env_user
    final_pass = args.password if args.password is not None else env_pass

    if final_user and final_pass:
        auth = (final_user, final_pass)
        if args.verbose: print(f"[VERBOSE] Using authentication for user: {final_user}", file=sys.stderr)
    elif args.verbose:
        # Print only if verbose and no auth is configured
        print("[VERBOSE] No complete authentication provided or configured. Attempting anonymous access.", file=sys.stderr)

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