#!/usr/bin/env python3
"""Test script to verify --tool-postfix functionality."""

import subprocess
import sys
import json

def test_postfix(postfix_arg=None):
    """Test the tool postfix functionality."""
    cmd = [
        sys.executable, 
        "odata_mcp.py",
        "--service", "https://services.odata.org/V4/Northwind/Northwind.svc",
        "--verbose"
    ]
    
    if postfix_arg:
        cmd.extend(["--tool-postfix", postfix_arg])
    
    print(f"Running command: {' '.join(cmd)}")
    print("=" * 60)
    
    # Run the command and capture output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Send a list-tools request
    list_tools_request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }
    
    process.stdin = subprocess.PIPE
    stdout, stderr = process.communicate(input=json.dumps(list_tools_request) + "\n", timeout=10)
    
    print("STDERR Output:")
    print(stderr)
    print("\nSTDOUT Output:")
    print(stdout)
    
    # Parse the response
    try:
        for line in stdout.strip().split('\n'):
            if line.strip():
                response = json.loads(line)
                if 'result' in response and 'tools' in response['result']:
                    tools = response['result']['tools']
                    print(f"\nFound {len(tools)} tools:")
                    for tool in tools[:5]:  # Show first 5 tools
                        print(f"  - {tool['name']}")
                    if len(tools) > 5:
                        print(f"  ... and {len(tools) - 5} more")
                    return tools
    except Exception as e:
        print(f"Error parsing response: {e}")
    
    return None

if __name__ == "__main__":
    print("Test 1: Default behavior (no --tool-postfix)")
    tools1 = test_postfix()
    
    print("\n" + "=" * 60 + "\n")
    
    print("Test 2: With custom postfix '_custom'")
    tools2 = test_postfix("_custom")
    
    # Compare tool names
    if tools1 and tools2:
        print("\n" + "=" * 60)
        print("Comparison of tool names:")
        for i in range(min(3, len(tools1), len(tools2))):
            print(f"  Default: {tools1[i]['name']}")
            print(f"  Custom:  {tools2[i]['name']}")
            print()