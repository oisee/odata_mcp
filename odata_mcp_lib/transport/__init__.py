"""
Transport layer abstractions for OData MCP.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Awaitable
import asyncio
import json


class TransportMessage:
    """Represents a transport-agnostic message."""
    
    def __init__(self, jsonrpc: str = "2.0", id: Optional[Any] = None, 
                 method: Optional[str] = None, params: Optional[Dict[str, Any]] = None,
                 result: Optional[Any] = None, error: Optional[Dict[str, Any]] = None):
        self.jsonrpc = jsonrpc
        self.id = id
        self.method = method
        self.params = params
        self.result = result
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        msg = {"jsonrpc": self.jsonrpc}
        
        if self.id is not None:
            msg["id"] = self.id
            
        if self.method is not None:
            msg["method"] = self.method
            
        if self.params is not None:
            msg["params"] = self.params
            
        if self.result is not None:
            msg["result"] = self.result
            
        if self.error is not None:
            msg["error"] = self.error
            
        return msg
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransportMessage':
        """Create message from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error")
        )
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TransportMessage':
        """Create message from JSON string."""
        return cls.from_dict(json.loads(json_str))


class Transport(ABC):
    """Abstract base class for transport implementations."""
    
    def __init__(self, handler: Optional[Callable[[TransportMessage], Awaitable[Optional[TransportMessage]]]] = None):
        self.handler = handler
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """Start the transport."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport."""
        pass
    
    @abstractmethod
    async def send_message(self, message: TransportMessage) -> None:
        """Send a message through the transport."""
        pass
    
    @abstractmethod
    async def receive_message(self) -> Optional[TransportMessage]:
        """Receive a message from the transport."""
        pass
    
    async def handle_message(self, message: TransportMessage) -> Optional[TransportMessage]:
        """Handle an incoming message using the registered handler."""
        if self.handler:
            return await self.handler(message)
        return None
    
    @property
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self._running