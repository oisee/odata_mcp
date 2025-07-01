"""
STDIO transport implementation for OData MCP.
"""

import asyncio
import sys
import json
from typing import Optional, TextIO
from . import Transport, TransportMessage


class StdioTransport(Transport):
    """STDIO transport implementation using stdin/stdout."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stdin = sys.stdin
        self._stdout = sys.stdout
        self._reader_task = None
        
    async def start(self) -> None:
        """Start the STDIO transport."""
        if self._running:
            return
            
        self._running = True
        
        # Start reader task
        self._reader_task = asyncio.create_task(self._reader_loop())
        
    async def stop(self) -> None:
        """Stop the STDIO transport."""
        self._running = False
        
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
                
    async def send_message(self, message: TransportMessage) -> None:
        """Send a message to stdout."""
        if not self._running:
            raise RuntimeError("Transport not running")
            
        # Convert message to JSON and write to stdout
        json_str = message.to_json()
        await asyncio.to_thread(self._write_line, json_str)
        
    async def receive_message(self) -> Optional[TransportMessage]:
        """Receive a message from stdin."""
        if not self._running:
            return None
            
        # Read line from stdin
        line = await asyncio.to_thread(self._read_line)
        if not line:
            return None
            
        try:
            return TransportMessage.from_json(line)
        except json.JSONDecodeError:
            # Invalid JSON, ignore
            return None
            
    def _read_line(self) -> Optional[str]:
        """Read a line from stdin (blocking)."""
        try:
            line = self._stdin.readline()
            if line:
                return line.strip()
        except (EOFError, KeyboardInterrupt):
            pass
        return None
        
    def _write_line(self, line: str) -> None:
        """Write a line to stdout (blocking)."""
        self._stdout.write(line + '\n')
        self._stdout.flush()
        
    async def _reader_loop(self) -> None:
        """Main reader loop that processes incoming messages."""
        while self._running:
            try:
                # Read message
                message = await self.receive_message()
                if not message:
                    await asyncio.sleep(0.01)  # Small delay to avoid busy loop
                    continue
                    
                # Handle message
                response = await self.handle_message(message)
                
                # Send response if not a notification
                if response and message.id is not None:
                    await self.send_message(response)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                if self._running:
                    error_msg = TransportMessage(
                        id=None,
                        error={
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    )
                    try:
                        await self.send_message(error_msg)
                    except:
                        pass