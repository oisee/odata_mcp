"""
OData MCP Library - A modular implementation of OData v2 to MCP bridge.
"""

from .models import (
    EntityProperty,
    EntityType,
    EntitySet,
    FunctionImport,
    ODataMetadata
)
from .guid_handler import ODataGUIDHandler
from .metadata_parser import MetadataParser
from .client import ODataClient
from .bridge import ODataMCPBridge

__all__ = [
    'EntityProperty',
    'EntityType', 
    'EntitySet',
    'FunctionImport',
    'ODataMetadata',
    'ODataGUIDHandler',
    'MetadataParser',
    'ODataClient',
    'ODataMCPBridge'
]