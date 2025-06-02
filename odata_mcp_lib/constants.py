"""
Constants used throughout the OData MCP library.
"""

from typing import Optional

# OData primitive type mappings to Python types
ODATA_PRIMITIVE_TYPES = {
    "Edm.String": str,
    "Edm.Int16": int,
    "Edm.Int32": int,
    "Edm.Int64": int,
    "Edm.Decimal": float,
    "Edm.Double": float,
    "Edm.Boolean": bool,
    "Edm.DateTime": str,
    "Edm.DateTimeOffset": str,
    "Edm.Time": str,
    "Edm.Guid": str,
    "Edm.Binary": str
}

# Map Python types to their string representation for exec()
TYPE_MAP = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    # Add Optional types explicitly
    Optional[str]: "Optional[str]",
    Optional[int]: "Optional[int]",
    Optional[float]: "Optional[float]",
    Optional[bool]: "Optional[bool]",
}

# Namespaces for OData XML parsing
NAMESPACES = {
    'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
    'edm': 'http://schemas.microsoft.com/ado/2008/09/edm',
    'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
    'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
    'atom': 'http://www.w3.org/2005/Atom',
    'app': 'http://www.w3.org/2007/app'
}