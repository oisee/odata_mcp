#!/bin/bash
# Test script for HTTP/SSE transport

echo "Testing OData MCP HTTP/SSE Transport"
echo "===================================="
echo

# Default values
SERVER_URL="http://localhost:8080"
ODATA_SERVICE="${ODATA_URL:-https://services.odata.org/V2/Northwind/Northwind.svc/}"

echo "Using OData service: $ODATA_SERVICE"
echo "HTTP server will run on: $SERVER_URL"
echo

# Function to test RPC endpoint
test_rpc() {
    echo "Testing RPC endpoint..."
    
    # Test initialize
    echo "1. Initialize:"
    curl -s -X POST $SERVER_URL/rpc \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "Test Client",
                    "version": "1.0.0"
                }
            }
        }' | jq .
    
    echo
    echo "2. List tools:"
    curl -s -X POST $SERVER_URL/rpc \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }' | jq .
}

# Function to test SSE endpoint
test_sse() {
    echo
    echo "Testing SSE endpoint..."
    echo "Connecting to SSE stream (press Ctrl+C to stop):"
    echo
    
    # Connect to SSE stream and show first few events
    timeout 5 curl -N -H 'Accept: text/event-stream' $SERVER_URL/sse 2>/dev/null | head -20
}

# Check if server is already running
if curl -s -o /dev/null -w "%{http_code}" $SERVER_URL/health | grep -q "200"; then
    echo "HTTP server is already running!"
    echo
    test_rpc
    test_sse
else
    echo "Starting OData MCP with HTTP transport..."
    echo "Run this in another terminal:"
    echo
    echo "python odata_mcp.py --transport http --service \"$ODATA_SERVICE\""
    echo
    echo "Then run this script again to test the endpoints."
fi