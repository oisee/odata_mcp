#!/usr/bin/env python3
"""
Test transport implementations.
"""

import asyncio
import json
from odata_mcp_lib.transport import TransportMessage
from odata_mcp_lib.transport.stdio import StdioTransport
from odata_mcp_lib.transport.http_sse import HttpSSETransport


async def test_message_handler(message: TransportMessage) -> TransportMessage:
    """Simple test handler."""
    if message.method == "test":
        return TransportMessage(
            id=message.id,
            result={"status": "ok", "echo": message.params}
        )
    return TransportMessage(
        id=message.id,
        error={"code": -32601, "message": "Method not found"}
    )


async def test_stdio_transport():
    """Test STDIO transport."""
    print("Testing STDIO transport...")
    
    # Create transport
    transport = StdioTransport(handler=test_message_handler)
    
    # Test message serialization
    msg = TransportMessage(id=1, method="test", params={"hello": "world"})
    json_str = msg.to_json()
    print(f"Serialized: {json_str}")
    
    # Test message deserialization
    msg2 = TransportMessage.from_json(json_str)
    print(f"Deserialized: method={msg2.method}, params={msg2.params}")
    
    print("STDIO transport test passed!")


async def test_http_transport():
    """Test HTTP/SSE transport."""
    print("\nTesting HTTP/SSE transport...")
    
    # Create transport
    transport = HttpSSETransport(host="127.0.0.1", port=8888, handler=test_message_handler)
    
    # Start transport
    await transport.start()
    print("HTTP transport started on http://127.0.0.1:8888")
    
    # Wait a bit
    await asyncio.sleep(1)
    
    # Stop transport
    await transport.stop()
    print("HTTP transport stopped")
    
    print("HTTP/SSE transport test passed!")


async def main():
    """Run all tests."""
    await test_stdio_transport()
    await test_http_transport()
    print("\nAll transport tests passed!")


if __name__ == "__main__":
    asyncio.run(main())