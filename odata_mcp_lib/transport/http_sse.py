"""
HTTP/SSE transport implementation for OData MCP.
"""

import asyncio
import json
import sys
import uuid
from typing import Optional, Dict, Set
from aiohttp import web
from aiohttp_sse import sse_response
import aiohttp_cors
from . import Transport, TransportMessage


class HttpSSETransport(Transport):
    """HTTP/SSE transport implementation using aiohttp."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = host
        self.port = port
        self._app = None
        self._runner = None
        self._site = None
        self._sse_clients: Dict[str, web.StreamResponse] = {}
        self._client_queues: Dict[str, asyncio.Queue] = {}
        
    async def start(self) -> None:
        """Start the HTTP/SSE transport."""
        if self._running:
            return
            
        self._running = True
        
        # Create aiohttp application
        self._app = web.Application()
        
        # Setup CORS
        cors = aiohttp_cors.setup(self._app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # Add routes
        self._app.router.add_get('/health', self._handle_health)
        self._app.router.add_get('/sse', self._handle_sse)
        self._app.router.add_post('/rpc', self._handle_rpc)
        
        # Configure CORS on all routes
        for route in list(self._app.router.routes()):
            cors.add(route)
        
        # Start server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        
        print(f"HTTP/SSE transport listening on http://{self.host}:{self.port}", file=sys.stderr)
        
    async def stop(self) -> None:
        """Stop the HTTP/SSE transport."""
        self._running = False
        
        # Close all SSE connections
        for client_id in list(self._sse_clients.keys()):
            await self._disconnect_client(client_id)
        
        # Stop server
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
            
    async def send_message(self, message: TransportMessage) -> None:
        """Broadcast message to all SSE clients."""
        if not self._running:
            raise RuntimeError("Transport not running")
            
        # Send to all connected SSE clients
        disconnected = []
        for client_id, response in self._sse_clients.items():
            try:
                await response.send_data(
                    data=message.to_json(),
                    event='message'
                )
            except Exception:
                disconnected.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected:
            await self._disconnect_client(client_id)
            
    async def receive_message(self) -> Optional[TransportMessage]:
        """Not used for HTTP transport - messages come through request handlers."""
        return None
        
    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "transport": "http/sse",
            "clients": len(self._sse_clients)
        })
        
    async def _handle_sse(self, request: web.Request) -> web.StreamResponse:
        """Handle SSE connection endpoint."""
        # Create SSE response
        response = await sse_response(request)
        
        # Generate client ID
        client_id = str(uuid.uuid4())
        
        # Store client
        self._sse_clients[client_id] = response
        self._client_queues[client_id] = asyncio.Queue()
        
        try:
            # Send initial connection event
            await response.send_data(
                data=json.dumps({
                    "type": "connection",
                    "clientId": client_id
                }),
                event='connection'
            )
            
            # Keep connection alive and send queued messages
            while self._running:
                try:
                    # Check for queued messages with timeout
                    message = await asyncio.wait_for(
                        self._client_queues[client_id].get(),
                        timeout=30.0  # 30 second timeout
                    )
                    
                    # Send message
                    await response.send_data(
                        data=message.to_json(),
                        event='message'
                    )
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    await response.send_data(
                        data='',
                        event='keepalive'
                    )
                    
        except Exception:
            pass
        finally:
            # Clean up on disconnect
            await self._disconnect_client(client_id)
            
        return response
        
    async def _handle_rpc(self, request: web.Request) -> web.Response:
        """Handle JSON-RPC request endpoint."""
        try:
            # Parse request
            data = await request.json()
            message = TransportMessage.from_dict(data)
            
            # Handle message
            response = await self.handle_message(message)
            
            if response:
                return web.json_response(response.to_dict())
            else:
                # No response for notifications
                return web.Response(status=204)
                
        except json.JSONDecodeError:
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }, status=400)
        except Exception as e:
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }, status=500)
            
    async def _disconnect_client(self, client_id: str) -> None:
        """Disconnect and clean up a client."""
        if client_id in self._sse_clients:
            del self._sse_clients[client_id]
        if client_id in self._client_queues:
            del self._client_queues[client_id]
            
    async def send_to_client(self, client_id: str, message: TransportMessage) -> bool:
        """Send message to specific SSE client."""
        if client_id in self._client_queues:
            await self._client_queues[client_id].put(message)
            return True
        return False