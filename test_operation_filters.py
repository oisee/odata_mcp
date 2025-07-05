#!/usr/bin/env python3
"""
Test operation type filtering with --enable and --disable flags.
"""

import subprocess
import json
import sys
import os

def run_trace_command(extra_args=[]):
    """Run the odata_mcp.py command with --trace flag and return registered tools."""
    cmd = [
        sys.executable,
        "odata_mcp.py",
        "--service", "https://services.odata.org/V2/Northwind/Northwind.svc/",
        "--trace",
        "-v"
    ] + extra_args
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Command failed with return code {result.returncode}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    
    # Parse the output to extract registered tools
    output = result.stdout
    
    # Find all tool names in the output
    tools = []
    for line in output.split('\n'):
        line = line.strip()
        # Look for tool lines with icons (🔢, ➕, 🗑️, 🔍, 📖, ✏️, •)
        if any(icon in line for icon in ['🔢', '➕', '🗑️', '🔍', '📖', '✏️', '🔎', '•']):
            # Extract tool name - it's the last word in the line (ends with _for_XXX)
            words = line.split()
            for word in words:
                if '_for_' in word or (word.startswith(('filter_', 'count_', 'create_', 'get_', 'update_', 'delete_', 'search_', 'upd_', 'del_'))):
                    tools.append(word)
                    break
    
    return tools, output

def categorize_tools(tools):
    """Categorize tools by operation type."""
    categories = {
        'C': [],  # Create
        'S': [],  # Search
        'F': [],  # Filter
        'G': [],  # Get
        'U': [],  # Update
        'D': [],  # Delete
        'A': []   # Actions/Functions
    }
    
    for tool in tools:
        if tool.startswith('create_'):
            categories['C'].append(tool)
        elif tool.startswith('search_'):
            categories['S'].append(tool)
        elif tool.startswith('filter_') or tool.startswith('count_'):
            categories['F'].append(tool)
        elif tool.startswith('get_'):
            categories['G'].append(tool)
        elif tool.startswith('update_') or tool.startswith('upd_'):
            categories['U'].append(tool)
        elif tool.startswith('delete_') or tool.startswith('del_'):
            categories['D'].append(tool)
        elif 'service_info' not in tool and 'readme' not in tool:
            # Assume other tools are functions/actions
            categories['A'].append(tool)
    
    return categories

def test_no_filters():
    """Test with no operation filters (all operations should be available)."""
    print("Test 1: No operation filters...")
    tools, output = run_trace_command()
    categories = categorize_tools(tools)
    
    # Debug: Print what we found
    print(f"  Found {len(tools)} total tools")
    for op_type, tool_list in categories.items():
        if tool_list:
            print(f"  {op_type}: {len(tool_list)} tools (e.g., {tool_list[0]})")
    
    # Should have all operation types (except search which may not be available)
    assert len(categories['C']) > 0, "Should have create operations"
    # Search operations may not be available if entities aren't searchable
    # assert len(categories['S']) > 0, "Should have search operations"
    assert len(categories['F']) > 0, "Should have filter operations"
    assert len(categories['G']) > 0, "Should have get operations"
    assert len(categories['U']) > 0, "Should have update operations"
    assert len(categories['D']) > 0, "Should have delete operations"
    
    print(f"✓ Found {len(tools)} tools with all operation types")

def test_enable_read_only():
    """Test with --enable R (should only have S, F, G operations)."""
    print("\nTest 2: --enable R (read-only operations)...")
    tools, output = run_trace_command(["--enable", "R"])
    categories = categorize_tools(tools)
    
    # Should only have read operations
    assert len(categories['C']) == 0, "Should not have create operations"
    # S is included in R but may not exist if no searchable entities
    # assert len(categories['S']) > 0, "Should have search operations"
    assert len(categories['F']) > 0, "Should have filter operations"
    assert len(categories['G']) > 0, "Should have get operations"
    assert len(categories['U']) == 0, "Should not have update operations"
    assert len(categories['D']) == 0, "Should not have delete operations"
    assert len(categories['A']) == 0, "Should not have action operations"
    
    print(f"✓ Found {len(tools)} tools with only read operations (S, F, G)")

def test_disable_cud():
    """Test with --disable CUD (should not have create, update, delete)."""
    print("\nTest 3: --disable CUD...")
    tools, output = run_trace_command(["--disable", "CUD"])
    categories = categorize_tools(tools)
    
    # Should not have CUD operations but should have others
    assert len(categories['C']) == 0, "Should not have create operations"
    # assert len(categories['S']) > 0, "Should have search operations"  # May not exist
    assert len(categories['F']) > 0, "Should have filter operations"
    assert len(categories['G']) > 0, "Should have get operations"
    assert len(categories['U']) == 0, "Should not have update operations"
    assert len(categories['D']) == 0, "Should not have delete operations"
    # Note: Northwind service has no function imports, so we can't test A here
    
    print(f"✓ Found {len(tools)} tools without CUD operations")

def test_enable_specific():
    """Test with --enable FG (should only have filter and get operations)."""
    print("\nTest 4: --enable FG...")
    tools, output = run_trace_command(["--enable", "FG"])
    categories = categorize_tools(tools)
    
    # Should only have F and G operations
    assert len(categories['C']) == 0, "Should not have create operations"
    assert len(categories['S']) == 0, "Should not have search operations"
    assert len(categories['F']) > 0, "Should have filter operations"
    assert len(categories['G']) > 0, "Should have get operations"
    assert len(categories['U']) == 0, "Should not have update operations"
    assert len(categories['D']) == 0, "Should not have delete operations"
    assert len(categories['A']) == 0, "Should not have action operations"
    
    print(f"✓ Found {len(tools)} tools with only F and G operations")

def test_disable_actions():
    """Test with --disable A (should not have function imports)."""
    print("\nTest 5: --disable A...")
    tools, output = run_trace_command(["--disable", "A"])
    categories = categorize_tools(tools)
    
    # Should have all operations except actions
    assert len(categories['C']) > 0, "Should have create operations"
    # assert len(categories['S']) > 0, "Should have search operations"  # May not exist
    assert len(categories['F']) > 0, "Should have filter operations"
    assert len(categories['G']) > 0, "Should have get operations"
    assert len(categories['U']) > 0, "Should have update operations"
    assert len(categories['D']) > 0, "Should have delete operations"
    assert len(categories['A']) == 0, "Should not have action operations"
    
    print(f"✓ Found {len(tools)} tools without action operations")

def test_case_insensitive():
    """Test that operation codes are case-insensitive."""
    print("\nTest 6: Case insensitivity (--enable sfg)...")
    tools1, _ = run_trace_command(["--enable", "sfg"])
    tools2, _ = run_trace_command(["--enable", "SFG"])
    
    assert set(tools1) == set(tools2), "Case should not matter for operation codes"
    
    print(f"✓ Case insensitive operation codes work correctly")

def test_invalid_operation():
    """Test that invalid operation codes produce an error."""
    print("\nTest 7: Invalid operation code...")
    cmd = [
        sys.executable,
        "odata_mcp.py",
        "--service", "https://services.odata.org/V2/Northwind/Northwind.svc/",
        "--enable", "XYZ"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    assert result.returncode != 0, "Should fail with invalid operation code"
    assert "Invalid operation codes" in result.stderr, "Should show error about invalid codes"
    
    print(f"✓ Invalid operation codes properly rejected")

def test_verbose_output():
    """Test that verbose output shows operation filter info."""
    print("\nTest 8: Verbose output shows operation filters...")
    _, output = run_trace_command(["--enable", "R"])
    
    assert "Enabled Operations:" in output or "Enabled operations:" in output, "Should show enabled operations in verbose output"
    
    print(f"✓ Verbose output includes operation filter information")

def main():
    print("Testing OData MCP Operation Type Filtering")
    print("=" * 50)
    
    test_no_filters()
    test_enable_read_only()
    test_disable_cud()
    test_enable_specific()
    test_disable_actions()
    test_case_insensitive()
    test_invalid_operation()
    test_verbose_output()
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")

if __name__ == "__main__":
    main()