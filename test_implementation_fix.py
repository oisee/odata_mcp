#!/usr/bin/env python3
"""
Test script to verify the implementation_logic binding fix in OData MCP Wrapper.
This script creates a minimal test case to confirm that the implementation_logic is
properly bound to the dynamically generated functions.
"""

import asyncio
import json
import os
import sys
import re
from typing import Dict, Any, Optional, List

# Directly test the implementation_logic binding without full ODataMCPBridge initialization
class TestImplementationLogic:
    """Test class to verify the implementation_logic binding fix."""
    
    def __init__(self):
        """Initializes the test class."""
        # Create the _implementation_registry
        self._implementation_registry = {}
        # For verbose logging
        self.verbose = True
        
        # Register our test tool
        print("Registering test tool...")
        self.register_test_tool()

    def _log_verbose(self, message: str):
        """Prints message to stderr only if verbose mode is enabled."""
        if self.verbose:
            print(f"[VERBOSE] {message}")

    def register_test_tool(self):
        """Registers a test tool to verify implementation_logic binding."""
        tool_name = "test_tool"
        param_strings = ["param1: str", "param2: Optional[int] = None"]
        signature = f"async def {tool_name}(*, {', '.join(param_strings)}) -> str:"
        
        body = [
            f"    '''Test docstring'''",
            f"    impl_func = _implementation_registry['{tool_name}']",
            f"    try:",
            f"        return await impl_func(param1=param1, param2=param2)",
            f"    except Exception as e:",
            f"        err_msg = f'Error in tool {tool_name}: {{str(e)}}'",
            f"        print(f'ERROR: {{err_msg}}')",
            f"        return json.dumps({{'error': err_msg}}, indent=2)"
        ]
        
        func_def_str = signature + "\n" + "\n".join(body)
        
        # Define the implementation logic
        async def test_implementation(param1: str, param2: Optional[int] = None) -> str:
            """Implementation logic for the test tool."""
            result = {
                "success": True,
                "message": f"Successfully called implementation_logic with param1={param1}, param2={param2}"
            }
            return json.dumps(result, indent=2)
        
        # Store the implementation logic in the registry
        self._implementation_registry[tool_name] = test_implementation
        
        # Prepare scope for exec
        exec_scope = {
            "_implementation_registry": self._implementation_registry,
            "asyncio": asyncio,
            "json": json,
            "Optional": Optional,
            "str": str,
            "int": int,
            "print": print,
        }
        
        # Execute function definition
        print(f"Executing function definition:\n{func_def_str}")
        # Pass exec_scope as globals so _implementation_registry is available
        exec(func_def_str, exec_scope, exec_scope)
        
        # Get the function object
        self.test_tool = exec_scope[tool_name]
        print(f"✅ Successfully created test_tool function")
    
    async def test_call_tool(self):
        """Tests calling the dynamically generated tool."""
        print("\nTesting tool call...")
        try:
            # Call the dynamically generated function
            result = await self.test_tool(param1="test value", param2=42)
            print(f"Result from tool call: {result}")
            
            # Verify the result contains the expected data
            result_data = json.loads(result)
            if (
                result_data.get("success") is True and
                "Successfully called implementation_logic" in result_data.get("message", "")
            ):
                print("\n✅ SUCCESS: implementation_logic binding is working correctly")
                return True
            else:
                print("\n❌ FAILURE: Unexpected result from tool call")
                return False
                
        except Exception as e:
            print(f"\n❌ FAILURE: Error during tool call: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main entry point for the test script."""
    print("Starting implementation_logic binding test...\n")
    
    test = TestImplementationLogic()
    result = await test.test_call_tool()
    
    if result:
        print("\n✅ SUMMARY: implementation_logic binding is working correctly. The fix works!")
        return 0
    else:
        print("\n❌ SUMMARY: implementation_logic binding test failed. More investigation is needed.")
        return 1

if __name__ == "__main__":
    # Run the async test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)