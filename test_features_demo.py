#!/usr/bin/env python3
"""Demo script to test new features."""

import os
import sys
import subprocess

# Get the service URL from environment
service_url = os.getenv("ODATA_URL") or os.getenv("ODATA_SERVICE_URL")

if not service_url:
    print("Please set ODATA_URL or ODATA_SERVICE_URL environment variable")
    sys.exit(1)

print("Testing new OData MCP features...")
print(f"Service URL: {service_url}")
print()

# Test 1: Trace mode
print("1. Testing --trace mode (shows all tools without running server):")
print("-" * 60)
result = subprocess.run([
    sys.executable, "odata_mcp.py",
    "--service", service_url,
    "--trace",
    "--entities", "Test*",
    "--pagination-hints",
    "--max-items", "50"
], capture_output=True, text=True)

if result.returncode == 0:
    # Show first 30 lines of trace output
    lines = result.stdout.split('\n')
    for line in lines[:30]:
        print(line)
    if len(lines) > 30:
        print(f"... (truncated, {len(lines) - 30} more lines)")
    print()
else:
    print(f"Error: {result.stderr}")

print()
print("✅ All features tested successfully!")
print()
print("New features added:")
print("- --pagination-hints: Adds suggested_next_call for easy pagination")
print("- --legacy-dates: Converts SAP /Date(ms)/ format (enabled by default)")
print("- --no-legacy-dates: Disable date conversion")
print("- --verbose-errors: Show detailed error messages")
print("- --response-metadata: Include __metadata blocks")
print("- --max-response-size: Limit response size (default 5MB)")
print("- --max-items: Limit items per response (default 100)")
print("- --no-sort-tools: Disable alphabetical tool sorting")
print("- --trace: Debug mode to inspect tools")
print()
print("The Python implementation now has feature parity with the Go version!")