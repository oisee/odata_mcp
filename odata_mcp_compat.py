"""
Backward compatibility layer for odata_mcp imports.
This module re-exports all the classes from odata_mcp_lib to maintain compatibility
with existing programs that import directly from odata_mcp.
"""

# Re-export everything from the new modular library
from odata_mcp_lib import *

# Explicitly re-export main classes for direct import compatibility
from odata_mcp_lib import (
    EntityProperty,
    EntityType,
    EntitySet,
    FunctionImport,
    ODataMetadata,
    ODataGUIDHandler,
    MetadataParser,
    ODataClient,
    ODataMCPBridge
)

# For programs that import like: from odata_mcp import MetadataParser
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