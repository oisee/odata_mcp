#!/usr/bin/env python3
"""
End-to-end test for Streamable HTTP transport.
Tests the OData MCP bridge with streamable-http transport.
"""

import asyncio
import json
import subprocess
import sys
import time
from typing import Dict, Any
import httpx
import signal

class StreamableHTTPTester:
    def __init__(self, port: int = 8080):
        self.port = port
        self.base_url = f"http://localhost:{port}/mcp"
        self.process = None
        
    async def start_server(self) -> bool:
        """Start the OData MCP server with streamable-http transport."""
        print("🚀 Starting OData MCP server with Streamable HTTP transport...")
        
        # Start the server process
        self.process = subprocess.Popen(
            [
                sys.executable, 
                "odata_mcp.py",
                "--service", "https://services.odata.org/V2/Northwind/Northwind.svc/",
                "--transport", "streamable-http",
                "--http-addr", f"localhost:{self.port}",
                "--verbose"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start (check if process is still running)
        for i in range(10):
            if self.process.poll() is not None:
                # Process terminated
                stdout, stderr = self.process.communicate()
                print(f"❌ Server failed to start!")
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                return False
            
            # Try to connect
            try:
                async with httpx.AsyncClient() as client:
                    # Try a simple connection to see if server is up
                    # For streamable-http, we need to send proper MCP messages
                    await asyncio.sleep(1)
                    print(f"⏳ Waiting for server... ({i+1}/10)")
            except Exception:
                pass
                
        print("✅ Server process started")
        return True
    
    async def test_connection(self) -> bool:
        """Test basic connection to the streamable HTTP endpoint."""
        print("\n📡 Testing connection to Streamable HTTP endpoint...")
        
        # Wait a bit more for server to be fully ready
        await asyncio.sleep(2)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # First just check if the endpoint exists
                try:
                    health_response = await client.get(f"http://localhost:{self.port}/")
                    print(f"📌 Root endpoint status: {health_response.status_code}")
                except:
                    pass
                
                # Streamable HTTP uses a single endpoint for bidirectional communication
                # Send an initialize request
                initialize_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "test-client",
                            "version": "1.0.0"
                        }
                    },
                    "id": 1
                }
                
                print(f"📤 Sending initialize request to {self.base_url}")
                response = await client.post(
                    self.base_url,
                    json=initialize_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    print(f"✅ Connected to {self.base_url}")
                    result = response.json()
                    print(f"📥 Response: {json.dumps(result, indent=2)}")
                    return True
                else:
                    print(f"❌ Connection failed: HTTP {response.status_code}")
                    print(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_list_tools(self) -> bool:
        """Test listing available tools."""
        print("\n🔧 Testing tool listing...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # First initialize
                initialize_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "test-client",
                            "version": "1.0.0"
                        }
                    },
                    "id": 1
                }
                
                init_response = await client.post(
                    self.base_url,
                    json=initialize_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if init_response.status_code != 200:
                    print(f"❌ Initialize failed: {init_response.status_code}")
                    return False
                
                # Now list tools
                list_tools_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 2
                }
                
                response = await client.post(
                    self.base_url,
                    json=list_tools_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "tools" in result["result"]:
                        tools = result["result"]["tools"]
                        print(f"✅ Found {len(tools)} tools")
                        
                        # Show first few tools
                        for i, tool in enumerate(tools[:5]):
                            print(f"  📌 {tool.get('name', 'unknown')}")
                        if len(tools) > 5:
                            print(f"  ... and {len(tools) - 5} more")
                        
                        return len(tools) > 0
                    else:
                        print(f"❌ Unexpected response format")
                        return False
                else:
                    print(f"❌ List tools failed: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ List tools error: {e}")
            return False
    
    async def test_invoke_tool(self) -> bool:
        """Test invoking a specific tool."""
        print("\n🎯 Testing tool invocation...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Initialize first
                initialize_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "test-client",
                            "version": "1.0.0"
                        }
                    },
                    "id": 1
                }
                
                await client.post(
                    self.base_url,
                    json=initialize_request,
                    headers={"Content-Type": "application/json"}
                )
                
                # Call the service info tool
                call_tool_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "odata_service_info_for_Northwind",
                        "arguments": {}
                    },
                    "id": 3
                }
                
                response = await client.post(
                    self.base_url,
                    json=call_tool_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        print(f"✅ Tool invoked successfully")
                        # Print first part of response
                        content = str(result.get("result", {}).get("content", []))
                        if len(content) > 200:
                            print(f"📥 Response preview: {content[:200]}...")
                        else:
                            print(f"📥 Response: {content}")
                        return True
                    else:
                        print(f"❌ Unexpected response format")
                        print(f"Response: {json.dumps(result, indent=2)}")
                        return False
                else:
                    print(f"❌ Tool invocation failed: HTTP {response.status_code}")
                    print(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Tool invocation error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop_server(self):
        """Stop the server process."""
        if self.process:
            print("\n🛑 Stopping server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            print("✅ Server stopped")
    
    async def run_tests(self) -> bool:
        """Run all tests."""
        print("=" * 60)
        print("🧪 E2E Test for Streamable HTTP Transport")
        print("=" * 60)
        
        all_passed = True
        
        try:
            # Start server
            if not await self.start_server():
                return False
            
            # Give server time to fully initialize
            await asyncio.sleep(3)
            
            # Run tests
            tests = [
                ("Connection Test", self.test_connection),
                ("List Tools Test", self.test_list_tools),
                ("Invoke Tool Test", self.test_invoke_tool),
            ]
            
            for test_name, test_func in tests:
                print(f"\n{'='*40}")
                print(f"Running: {test_name}")
                print('='*40)
                
                passed = await test_func()
                if not passed:
                    all_passed = False
                    print(f"❌ {test_name} FAILED")
                else:
                    print(f"✅ {test_name} PASSED")
            
        finally:
            self.stop_server()
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL TESTS PASSED!")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 60)
        
        return all_passed


async def main():
    """Main entry point."""
    tester = StreamableHTTPTester(port=8765)  # Use non-default port to avoid conflicts
    success = await tester.run_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)