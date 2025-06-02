#!/usr/bin/env python3
"""
OData v2 to MCP Wrapper (Enhanced based on Specification - v5 - Explicit Tool Signatures)

This module implements a bridge between OData v2 services and the Message Choreography
Processor (MCP) pattern, dynamically generating MCP tools based on OData metadata.
It incorporates features like standard OData query parameters, pagination info,
count, and search tools.

v2: Corrected tool registration calls by removing the unsupported 'fn_args' parameter.
v3: Added --verbose/--debug flag to control informational output to stderr.
v4: Updated argparse to accept both --service flag and positional service_url.
v5: Use exec() to create tool functions with explicit signatures matching OData metadata.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple, get_type_hints, ForwardRef
import signal
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import argparse # Using argparse for better flag handling
import traceback # For printing stack traces on error
import inspect # To help build signatures
import base64  # For GUID handling

import requests
# Use lxml for XML parsing - consider installing 'defusedxml' for enhanced security
from lxml import etree
from pydantic import BaseModel, Field # Keep Field for potential future use, though exec won't use it directly
from dotenv import load_dotenv

# Attempt to import FastMCP - adjust path as needed for your environment
try:
    from fastmcp import FastMCP
    import mcp.types as types
    # Conditional print based on initial check for verbose flags
    if '--verbose' in sys.argv or '--debug' in sys.argv:
         print("FastMCP imported successfully.", file=sys.stderr)
except ImportError:
    print("ERROR: Could not import FastMCP. Make sure it's installed and accessible.", file=sys.stderr)
    print("You might need to adjust the import statement based on your project structure.", file=sys.stderr)
    sys.exit(1)


# Load environment variables from .env file
load_dotenv()

# Constants
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

# --- GUID Handling ---

class ODataGUIDHandler:
    """Handles conversion and optimization of GUID fields in OData responses."""
    
    @staticmethod
    def base64_to_guid(base64_string: str) -> str:
        """
        Convert base64 encoded binary GUID to standard GUID format.
        
        Args:
            base64_string: Base64 encoded binary GUID
            
        Returns:
            Standard GUID string format (e.g., '550D1E94-44FB-4E8D-8E5C-8F63E5C20F80')
        """
        try:
            # Decode base64 to bytes
            guid_bytes = base64.b64decode(base64_string)
            
            # Convert to hex and format as GUID
            hex_string = guid_bytes.hex().upper()
            
            # Format as standard GUID: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            if len(hex_string) == 32:
                return f"{hex_string[0:8]}-{hex_string[8:12]}-{hex_string[12:16]}-{hex_string[16:20]}-{hex_string[20:32]}"
            else:
                # Return original if not standard GUID length
                return base64_string
        except Exception:
            # Return original on any error
            return base64_string
    
    @staticmethod
    def guid_to_base64(guid_string: str) -> str:
        """
        Convert standard GUID format to base64 encoded binary.
        
        Args:
            guid_string: Standard GUID string
            
        Returns:
            Base64 encoded binary GUID
        """
        try:
            # Remove hyphens and convert to bytes
            hex_string = guid_string.replace('-', '')
            guid_bytes = bytes.fromhex(hex_string)
            
            # Encode to base64
            return base64.b64encode(guid_bytes).decode('utf-8')
        except Exception:
            # Return original on any error
            return guid_string
    
    @classmethod
    def optimize_odata_response(cls, response_data: Any, 
                              guid_fields: List[str] = None,
                              max_items: int = None) -> Any:
        """
        Optimize OData response by converting GUID fields and limiting size.
        
        Args:
            response_data: The OData response data
            guid_fields: List of field names that contain GUIDs
            max_items: Maximum number of items to return
            
        Returns:
            Optimized response data
        """
        if guid_fields is None:
            # Common GUID field names in graph models
            guid_fields = ['Id', 'F', 'T', 'FromId', 'ToId']
        
        if isinstance(response_data, dict):
            # Handle single entity
            return cls._convert_entity_guids(response_data, guid_fields)
        elif isinstance(response_data, list):
            # Handle collection
            if max_items and len(response_data) > max_items:
                response_data = response_data[:max_items]
            return [cls._convert_entity_guids(item, guid_fields) for item in response_data]
        
        return response_data
    
    @classmethod
    def _convert_entity_guids(cls, entity: Dict[str, Any], 
                            guid_fields: List[str]) -> Dict[str, Any]:
        """Convert GUID fields in a single entity."""
        optimized = entity.copy()
        
        for field in guid_fields:
            if field in optimized and isinstance(optimized[field], str):
                # Check if it looks like base64
                if cls._is_base64(optimized[field]):
                    optimized[field] = cls.base64_to_guid(optimized[field])
        
        return optimized
    
    @staticmethod
    def _is_base64(s: str) -> bool:
        """Check if a string appears to be base64 encoded."""
        # Base64 pattern with padding
        pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
        
        # Check length is multiple of 4 and matches pattern
        return len(s) % 4 == 0 and bool(pattern.match(s))

# --- Pydantic Models for Metadata ---

class EntityProperty(BaseModel):
    name: str
    type: str # OData type string (e.g., "Edm.String")
    nullable: bool = True
    is_key: bool = False
    description: Optional[str] = None

    def get_python_type(self) -> type:
        return ODATA_PRIMITIVE_TYPES.get(self.type, str)

    def get_python_type_hint(self) -> str:
        """Get the Python type hint string for this property."""
        py_type = self.get_python_type()
        type_str = TYPE_MAP.get(py_type, "str") # Default to str if type not in map
        if self.nullable and not self.is_key: # Keys are typically required even if nullable in OData model
             # Ensure Optional is handled correctly even if base type wasn't in TYPE_MAP
             optional_type_str = TYPE_MAP.get(Optional[py_type], f"Optional[{type_str}]")
             return optional_type_str
        return type_str

class EntityType(BaseModel):
    name: str
    properties: List[EntityProperty] = []
    key_properties: List[str] = []
    description: Optional[str] = None

    def get_key_properties(self) -> List[EntityProperty]:
        return [prop for prop in self.properties if prop.is_key]

class EntitySet(BaseModel):
    name: str
    entity_type: str
    creatable: bool = True
    updatable: bool = True
    deletable: bool = True
    searchable: bool = False
    description: Optional[str] = None

class FunctionImport(BaseModel):
    name: str
    http_method: str = "GET"
    return_type: Optional[str] = None
    parameters: List[EntityProperty] = []
    description: Optional[str] = None

class ODataMetadata(BaseModel):
    entity_types: Dict[str, EntityType] = {}
    entity_sets: Dict[str, EntitySet] = {}
    function_imports: Dict[str, FunctionImport] = {}
    service_url: str
    service_description: Optional[str] = None

# --- Metadata Parser ---
# (MetadataParser class remains largely the same as v4 - code omitted for brevity,
#  assume it's included here as before)
class MetadataParser:
    """Parses OData v2 metadata from an OData service."""

    def __init__(self, service_url: str, auth: Optional[Tuple[str, str]] = None, verbose: bool = False):
        self.service_url = service_url.rstrip('/')
        self.metadata_url = f"{self.service_url}/$metadata"
        self.auth = auth
        self.verbose = verbose # Store verbosity flag
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
        # Standard headers
        self.session.headers.update({
            'Accept': 'application/xml, application/atom+xml, application/json',
            'User-Agent': 'OData-MCP-Wrapper/1.3' # Version bump
        })

    def _log_verbose(self, message: str):
        """Prints message to stderr only if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print(f"[{timestamp} Parser VERBOSE] {message}", file=sys.stderr)

    def _get_description(self, element) -> Optional[str]:
        """Helper to extract description from annotations (basic attempt)."""
        # Basic check for common annotation terms - might need refinement
        # Check for SAP annotations first
        desc = element.xpath("./@*[local-name()='label' and namespace-uri()='http://www.sap.com/Protocols/SAPData']", namespaces=NAMESPACES)
        if desc: return desc[0]
        # Check standard annotations
        desc = element.xpath(".//*[local-name()='LongDescription']/text()", namespaces=NAMESPACES)
        if desc: return desc[0]
        desc = element.xpath(".//*[local-name()='Summary']/text()", namespaces=NAMESPACES)
        if desc: return desc[0]
        desc = element.xpath(".//*[local-name()='Documentation']//*[local-name()='Summary']/text()", namespaces=NAMESPACES)
        if desc: return desc[0]
        # Fallback to Description
        desc = element.xpath(".//*[local-name()='Description']/text()", namespaces=NAMESPACES)
        if desc: return desc[0]
        return None

    def parse(self) -> ODataMetadata:
        """Parse the OData metadata document."""
        entity_types = {}
        entity_sets = {}
        function_imports = {}
        service_description = None

        try:
            self._log_verbose(f"Fetching metadata from {self.metadata_url}...")
            response = self.session.get(self.metadata_url)
            response.raise_for_status()
            self._log_verbose("Metadata fetched successfully.")

            try:
                # Use defusedxml for safety if available, fallback to lxml
                try:
                    # Note: DeprecationWarning is expected here if using defusedxml.lxml
                    from defusedxml import lxml as safe_lxml
                    root = safe_lxml.fromstring(response.content)
                    self._log_verbose("Parsed metadata with defusedxml.")
                except ImportError:
                    root = etree.fromstring(response.content)
                    self._log_verbose("Parsed metadata with lxml (defusedxml not found).")
                except Exception as parse_err:
                    # This is an actual error, print regardless of verbosity
                    print(f"ERROR: Error parsing XML metadata: {parse_err}", file=sys.stderr)
                    # Try parsing as potentially non-XML if root parsing fails
                    if b'</edmx:Edmx>' not in response.content: # Quick check if it looks like XML
                         print("ERROR: Response doesn't seem to be XML. Attempting service doc discovery.", file=sys.stderr)
                         raise ValueError("Metadata response is not valid XML")
                    else:
                         raise # Re-raise original parsing error

                # Find the main schema element for descriptions
                schema = root.find('.//edm:Schema', namespaces=NAMESPACES)
                if schema is not None:
                    service_description = self._get_description(schema)

                entity_types = self._parse_entity_types(root)
                entity_sets = self._parse_entity_sets(root, entity_types) # Pass entity_types for context
                function_imports = self._parse_function_imports(root)

            except Exception as xml_error:
                 # This is an actual error during processing
                print(f"ERROR: Error processing XML metadata: {xml_error}", file=sys.stderr)
                self._log_verbose("Falling back to service document discovery...") # Verbose msg for fallback attempt

            # Fallback/Augment with service document if needed
            if not entity_sets:
                self._log_verbose("Attempting to get EntitySets from service document...")
                entity_sets = self._get_entity_sets_from_service_doc()
                if entity_sets and not entity_types:
                    # Create minimal entity types if none were parsed from metadata
                    self._log_verbose("Creating minimal entity types based on service document...")
                    for name, es in entity_sets.items():
                         if es.entity_type not in entity_types:
                             entity_types[es.entity_type] = EntityType(
                                 name=es.entity_type,
                                 properties=[EntityProperty(name="ID", type="Edm.String", is_key=True, description="Generic ID")],
                                 key_properties=["ID"],
                                 description=f"Minimal type for {es.entity_type}"
                            )

            self._log_verbose(f"Parsing complete. Found {len(entity_types)} types, {len(entity_sets)} sets, {len(function_imports)} functions.")
            return ODataMetadata(
                entity_types=entity_types,
                entity_sets=entity_sets,
                function_imports=function_imports,
                service_url=self.service_url,
                service_description=service_description
            )

        except requests.exceptions.RequestException as req_err:
             # Fatal error, print regardless of verbosity
            print(f"FATAL ERROR: Could not fetch metadata: {req_err}", file=sys.stderr)
            # If 401/403, suggest auth issue
            if req_err.response is not None and req_err.response.status_code in [401, 403]:
                 print("ERROR: Authentication might be required or incorrect. Check credentials.", file=sys.stderr)
            raise
        except Exception as e:
             # Fatal error, print regardless of verbosity
            print(f"FATAL ERROR: Unexpected error during metadata parsing: {e}", file=sys.stderr)
            # Attempt a minimal fallback using only service doc
            try:
                self._log_verbose("Attempting final fallback using only service document...")
                fb_entity_sets = self._get_entity_sets_from_service_doc()
                fb_entity_types = {}
                if fb_entity_sets:
                    for name, es in fb_entity_sets.items():
                        if es.entity_type not in fb_entity_types:
                             fb_entity_types[es.entity_type] = EntityType(
                                 name=es.entity_type,
                                 properties=[EntityProperty(name="ID", type="Edm.String", is_key=True, description="Generic ID")],
                                 key_properties=["ID"],
                                 description=f"Minimal type for {es.entity_type}"
                             )
                return ODataMetadata(
                    entity_types=fb_entity_types,
                    entity_sets=fb_entity_sets,
                    function_imports={},
                    service_url=self.service_url
                )
            except Exception as fallback_error:
                # Error, print regardless of verbosity
                print(f"ERROR: Error during final fallback: {fallback_error}", file=sys.stderr)
                raise e # Re-raise the original error

    def _get_entity_sets_from_service_doc(self) -> Dict[str, EntitySet]:
        """Get entity sets from the service document (AtomPub format)."""
        entity_sets = {}
        try:
            self._log_verbose(f"Fetching service document from {self.service_url}...")
            # Prefer AtomPub format for service document
            headers = {'Accept': 'application/atom+xml, application/xml'}
            response = self.session.get(self.service_url, headers=headers)
            response.raise_for_status()

            # Use defusedxml for safety if available
            try:
                # Note: DeprecationWarning is expected here if using defusedxml.lxml
                from defusedxml import lxml as safe_lxml
                root = safe_lxml.fromstring(response.content)
            except ImportError:
                root = etree.fromstring(response.content)

            # AtomPub service document structure
            for collection in root.xpath('//app:collection', namespaces=NAMESPACES):
                name = collection.get('href')
                title_elem = collection.find('./atom:title', namespaces=NAMESPACES)
                # Use title attribute as fallback description if element text is missing
                title = title_elem.text if title_elem is not None and title_elem.text else collection.get('title', name)
                if name:
                    # Basic assumption: EntityType name matches EntitySet name if not found elsewhere
                    # Use title as description if available
                    entity_sets[name] = EntitySet(
                        name=name,
                        entity_type=name, # Assume type name matches set name initially
                        description=title if title != name else None # Only use title if it's different from href
                    )
            self._log_verbose(f"Found {len(entity_sets)} potential entity sets in service document.")
            return entity_sets

        except Exception as e:
            # This is a warning during fallback, print only if verbose
            if self.verbose:
                print(f"Warning: Could not get entity sets from service document: {e}", file=sys.stderr)
            return {}

    def _parse_entity_types(self, root) -> Dict[str, EntityType]:
        """Parse EntityType elements from metadata."""
        entity_types = {}
        # Ensure we are looking within a schema element
        schema = root.find('.//edm:Schema', namespaces=NAMESPACES)
        if schema is None:
            self._log_verbose("Warning: No Schema element found in metadata. Cannot parse entity types.")
            return {}

        for et_elem in schema.xpath('./edm:EntityType', namespaces=NAMESPACES):
            name = et_elem.get('Name')
            if not name: continue

            description = self._get_description(et_elem)

            # --- Key Properties ---
            key_props_names = []
            key_elem = et_elem.find('./edm:Key', namespaces=NAMESPACES)
            if key_elem is not None:
                key_props_names = [
                    prop_ref.get('Name')
                    for prop_ref in key_elem.findall('./edm:PropertyRef', namespaces=NAMESPACES)
                    if prop_ref.get('Name')
                ]

            # --- Properties ---
            properties = []
            for prop_elem in et_elem.xpath('./edm:Property', namespaces=NAMESPACES):
                prop_name = prop_elem.get('Name')
                prop_type = prop_elem.get('Type')
                if not prop_name or not prop_type: continue

                nullable = prop_elem.get('Nullable', 'true').lower() == 'true'
                is_key = prop_name in key_props_names
                prop_desc = self._get_description(prop_elem)

                properties.append(EntityProperty(
                    name=prop_name,
                    type=prop_type,
                    nullable=nullable,
                    is_key=is_key,
                    description=prop_desc
                ))

            entity_types[name] = EntityType(
                name=name,
                properties=properties,
                key_properties=key_props_names,
                description=description
            )
        return entity_types

    def _parse_entity_sets(self, root, entity_types: Dict[str, EntityType]) -> Dict[str, EntitySet]:
        """Parse EntitySet elements from metadata."""
        entity_sets = {}
        # Find the EntityContainer first
        container = root.find('.//edm:EntityContainer', namespaces=NAMESPACES)
        if container is None:
            self._log_verbose("Warning: No EntityContainer found in metadata. Cannot parse entity sets.")
            return {}

        for es_elem in container.xpath('./edm:EntitySet', namespaces=NAMESPACES):
            name = es_elem.get('Name')
            entity_type_fqn = es_elem.get('EntityType') # Fully qualified name
            if not name or not entity_type_fqn: continue

            # Extract simple name from fully qualified name (e.g., Namespace.Type -> Type)
            entity_type_name = entity_type_fqn.split('.')[-1]

            # Check if the entity type exists in our parsed types
            if entity_type_name not in entity_types:
                # Only warn if verbose
                self._log_verbose(f"Warning: EntityType '{entity_type_name}' for EntitySet '{name}' not found in parsed types. Using minimal definition.")
                # Create minimal type if not found
                entity_types[entity_type_name] = EntityType(
                     name=entity_type_name,
                     properties=[EntityProperty(name="ID", type="Edm.String", is_key=True, description="Generic ID")],
                     key_properties=["ID"],
                     description=f"Minimal type for {entity_type_name}"
                )


            description = self._get_description(es_elem)

            # Basic check for SAP creatable/updatable/deletable annotations
            creatable = es_elem.get('{http://www.sap.com/Protocols/SAPData}creatable', 'true').lower() == 'true'
            updatable = es_elem.get('{http://www.sap.com/Protocols/SAPData}updatable', 'true').lower() == 'true'
            deletable = es_elem.get('{http://www.sap.com/Protocols/SAPData}deletable', 'true').lower() == 'true'
            searchable = es_elem.get('{http://www.sap.com/Protocols/SAPData}searchable', 'false').lower() == 'true'


            entity_sets[name] = EntitySet(
                name=name,
                entity_type=entity_type_name,
                creatable=creatable,
                updatable=updatable,
                deletable=deletable,
                searchable=searchable,
                description=description
            )
        return entity_sets

    def _parse_function_imports(self, root) -> Dict[str, FunctionImport]:
        """Parse FunctionImport elements from metadata."""
        function_imports = {}
         # Find the EntityContainer first
        container = root.find('.//edm:EntityContainer', namespaces=NAMESPACES)
        if container is None:
            # No container, no function imports expected in standard OData v2
            return {}

        for func_elem in container.xpath('./edm:FunctionImport', namespaces=NAMESPACES):
            name = func_elem.get('Name')
            if not name: continue

            # Look for metadata namespace first, then try without
            http_method = func_elem.get('{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}HttpMethod')
            if http_method is None:
                http_method = func_elem.get('HttpMethod', 'GET').upper() # Fallback without namespace
            else:
                http_method = http_method.upper()

            return_type = func_elem.get('ReturnType')
            description = self._get_description(func_elem)

            parameters = []
            for param_elem in func_elem.xpath('./edm:Parameter', namespaces=NAMESPACES):
                param_name = param_elem.get('Name')
                param_type = param_elem.get('Type')
                if not param_name or not param_type: continue

                # Nullability is less common/standardized for function params, default to optional
                nullable = param_elem.get('Nullable', 'true').lower() == 'true'
                # SAP Mode attribute: 'In', 'Out', 'InOut'. Treat 'In' and 'InOut' as input params.
                mode = param_elem.get('{http://www.sap.com/Protocols/SAPData}Mode', 'In')
                if mode.lower() not in ['in', 'inout']:
                    continue # Skip output-only parameters

                param_desc = self._get_description(param_elem)


                parameters.append(EntityProperty(
                    name=param_name,
                    type=param_type,
                    nullable=nullable,
                    description=param_desc
                ))

            function_imports[name] = FunctionImport(
                name=name,
                http_method=http_method,
                return_type=return_type,
                parameters=parameters,
                description=description
            )
        return function_imports

# --- OData Client ---
# (ODataClient class remains largely the same as v4 - code omitted for brevity,
#  assume it's included here as before, including CSRF handling and logging)
class ODataClient:
    """Client for interacting with an OData v2 service."""

    def __init__(self, metadata: ODataMetadata, auth: Optional[Tuple[str, str]] = None, 
                 verbose: bool = False, optimize_guids: bool = True,
                 max_response_items: int = 1000):
        self.metadata = metadata
        self.auth = auth
        self.verbose = verbose # Store verbosity
        self.optimize_guids = optimize_guids
        self.max_response_items = max_response_items
        self.guid_handler = ODataGUIDHandler()
        self.base_url = metadata.service_url
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
        # Standard headers, always prefer JSON
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'OData-MCP-Wrapper/1.3',
            'Content-Type': 'application/json' # For POST/PUT/MERGE
        })
        # SAP specific header for CSRF token handling if needed (add logic later)
        self.csrf_token = None
        self.csrf_cookie = None
        
        # Identify GUID fields from metadata
        self._identify_guid_fields()

    def _log_verbose(self, message: str):
        """Prints message to stderr only if verbose mode is enabled."""
        if self.verbose:
             # Add timestamp for debugging context
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print(f"[{timestamp} Client VERBOSE] {message}", file=sys.stderr)
    
    def _identify_guid_fields(self):
        """Identify fields that are likely GUIDs based on metadata."""
        self.guid_fields_by_entity = {}
        
        for entity_name, entity_type in self.metadata.entity_types.items():
            guid_fields = []
            for prop in entity_type.properties:
                # Binary fields with GUID-like names
                if (prop.type == "Edm.Binary" and 
                    any(name in prop.name.upper() for name in ['ID', 'GUID', 'F', 'T'])):
                    guid_fields.append(prop.name)
                # Also check description for GUID hints
                elif prop.description and 'GUID' in prop.description.upper():
                    guid_fields.append(prop.name)
            
            self.guid_fields_by_entity[entity_name] = guid_fields
            if guid_fields and self.verbose:
                self._log_verbose(f"Identified GUID fields for {entity_name}: {guid_fields}")

    def _fetch_csrf_token(self):
        """Fetch CSRF token required by some SAP OData services for modifying requests."""
        self._log_verbose("Fetching CSRF token...")
        try:
            # Fetch token using a non-modifying request (e.g., GET metadata)
            # Use service document URL which is usually simpler/faster
            headers = {'X-CSRF-Token': 'Fetch', 'Accept': 'application/json'} # Prefer JSON for response if any
            response = self.session.get(self.metadata.service_url, headers=headers, params={'$top': 0}) # Light request
            response.raise_for_status()

            self.csrf_token = response.headers.get('X-CSRF-Token')
            # Store relevant cookies needed to send back with the token
            self.csrf_cookie = response.cookies # requests manages cookies by default, but store if needed explicitly

            if self.csrf_token:
                 self._log_verbose(f"CSRF token fetched successfully.")
            else:
                 # This is a potential issue, warn regardless of verbosity? Let's make it verbose for now.
                 self._log_verbose("Warning: No CSRF token returned by service. Modifying operations might fail.")

        except requests.exceptions.RequestException as e:
             # Warning, print only if verbose
             if self.verbose:
                print(f"Warning: Could not fetch CSRF token: {e}. Modifying operations might fail.", file=sys.stderr)
             self.csrf_token = None # Ensure token is None if fetch fails
             self.csrf_cookie = None
        except Exception as e:
              # Unexpected error, print only if verbose
             if self.verbose:
                print(f"Warning: Unexpected error fetching CSRF token: {e}", file=sys.stderr)
             self.csrf_token = None
             self.csrf_cookie = None

    def _make_request(self, method: str, url: str, requires_csrf: bool = False, **kwargs) -> requests.Response:
         """Internal helper to make requests, handling CSRF."""
         # Ensure CSRF is fetched only once initially if required for modifying methods
         modifying_methods = ['POST', 'PUT', 'MERGE', 'PATCH', 'DELETE']
         is_modifying = method.upper() in modifying_methods

         # If modifying and requires CSRF (usually true for SAP), ensure token exists
         if is_modifying and requires_csrf and not self.csrf_token:
             self._fetch_csrf_token() # Attempt to fetch if needed and not present

         # Merge headers, prioritize kwargs headers
         request_headers = self.session.headers.copy() # Start with session defaults
         if 'headers' in kwargs:
              request_headers.update(kwargs.pop('headers'))

         # Add CSRF token if required and available
         if is_modifying and requires_csrf and self.csrf_token:
              request_headers['X-CSRF-Token'] = self.csrf_token

         kwargs['headers'] = request_headers

         # Use stored cookies if needed (requests session might handle this automatically)
         # If CSRF fetch stored specific cookies, use them
         # Using session cookies should be sufficient unless explicitly overridden
         # if is_modifying and requires_csrf and self.csrf_cookie and 'cookies' not in kwargs:
         #      kwargs['cookies'] = self.csrf_cookie


         response = self.session.request(method, url, **kwargs)

          # Handle CSRF token expiry (often 403 Forbidden with specific message/header)
         # Check X-CSRF-Token header in response too, SAP might signal expiry there
         csrf_required_header = response.headers.get('x-csrf-token', '').lower()

         # Condition for retry: 403 status and (required header present or specific text in body)
         needs_csrf_retry = (
             response.status_code == 403 and
             is_modifying and # Only retry modifying requests
             (csrf_required_header == 'required' or 'CSRF token validation failed' in response.text)
         )

         if needs_csrf_retry:
                self._log_verbose("CSRF token seems invalid/expired. Refetching...")
                self._fetch_csrf_token() # Fetch a new token
                if self.csrf_token:
                     # Retry the request with the new token
                     request_headers['X-CSRF-Token'] = self.csrf_token
                     kwargs['headers'] = request_headers
                     # Use new cookies if refetch provided them
                     # kwargs['cookies'] = self.csrf_cookie # Session handles cookies usually

                     self._log_verbose("Retrying request with new CSRF token...")
                     response = self.session.request(method, url, **kwargs)
                else:
                     # Error, print regardless of verbosity
                     print("ERROR: Failed to refetch CSRF token. Request aborted.", file=sys.stderr)
                     # We should probably raise an exception here instead of returning the 403
                     # Re-create the original exception context if possible
                     raise requests.exceptions.RequestException(f"CSRF token required and refetch failed.", response=response)


         return response


    def _build_key_string(self, entity_type: EntityType, key_values: Dict[str, Any]) -> str:
        """Build the key predicate string for OData URLs."""
        key_props = entity_type.get_key_properties()
        if not key_props:
            raise ValueError(f"Entity type {entity_type.name} has no defined key properties.")

        # Ensure all key values are provided
        missing_keys = [prop.name for prop in key_props if prop.name not in key_values or key_values[prop.name] is None]
        if missing_keys:
            raise ValueError(f"Missing value(s) for key properties: {', '.join(missing_keys)}")

        if len(key_props) == 1:
            key_prop = key_props[0]
            key_value = key_values[key_prop.name]
            py_type = key_prop.get_python_type()
            if py_type == str:
                # Basic check for quotes inside string - needs proper escaping in real world
                key_value_str = str(key_value).replace("'", "''")
                return f"('{key_value_str}')"
            else: # Assume numeric or boolean which don't need quotes
                # Format boolean as true/false lowercase
                if py_type == bool:
                     return f"({str(key_value).lower()})"
                return f"({key_value})"
        else: # Composite key
            key_parts = []
            for key_prop in key_props:
                key_value = key_values[key_prop.name]
                py_type = key_prop.get_python_type()
                if py_type == str:
                    key_value_str = str(key_value).replace("'", "''")
                    key_parts.append(f"{key_prop.name}='{key_value_str}'")
                elif py_type == bool:
                     key_parts.append(f"{key_prop.name}={str(key_value).lower()}")
                else:
                    key_parts.append(f"{key_prop.name}={key_value}")
            return f"({','.join(key_parts)})"

    def _parse_odata_error(self, response: requests.Response) -> str:
         """Attempt to extract a meaningful error message from OData error response."""
         try:
             error_data = response.json()
             # Common OData v2 error structures
             if 'error' in error_data and 'message' in error_data['error']:
                  msg_obj = error_data['error']['message']
                  if isinstance(msg_obj, dict) and 'value' in msg_obj:
                      return msg_obj['value']
                  elif isinstance(msg_obj, str):
                      return msg_obj
                  else: # Fallback for unexpected message format
                      return json.dumps(error_data['error'])

             # SAP specific structure? (check common patterns)
             elif 'error' in error_data and 'innererror' in error_data['error']:
                  inner_error = error_data['error']['innererror']
                  if 'errordetails' in inner_error and isinstance(inner_error['errordetails'], list):
                       details = [d.get('message', '') for d in inner_error['errordetails'] if d.get('message')]
                       if details: return "; ".join(details)
                  # Fallback to application specific message if available
                  if 'application' in inner_error and 'message_text' in inner_error['application']:
                       return inner_error['application']['message_text']

             # Fallback to raw text if structure not recognized
             return response.text[:500] # Limit length

         except json.JSONDecodeError:
             return response.text[:500] # Return raw text if not JSON
         except Exception as e: # Catch any other parsing errors
              self._log_verbose(f"Warning: Exception while parsing OData error response: {e}")
              return response.text[:500]


    def _parse_odata_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse JSON response, handling common OData v2 structures and errors."""
        try:
             # Check status first - raise detailed error if needed
             response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
             error_message = self._parse_odata_error(response)
             # Error, print regardless of verbosity
             print(f"ERROR: OData HTTP Error: {http_err.response.status_code} {http_err.response.reason}. Message: {error_message}", file=sys.stderr)
             # Re-raise with a more informative message
             raise ValueError(f"OData request failed ({http_err.response.status_code}): {error_message}") from http_err


        # Handle No Content responses (common for PUT/DELETE/MERGE)
        if response.status_code == 204:
            return {"message": "Operation successful (No content returned)."}

        if not response.content:
            # Should not happen if status wasn't 204, but handle defensively
            self._log_verbose(f"Warning: Operation successful but empty response received (Status: {response.status_code}).")
            return {"message": "Operation successful (Empty response received)."}

        try:
            data = response.json()
            # Standard OData v2 structure is {"d": ...}
            # Results for collections are often in {"d": {"results": [...]}}
            if 'd' in data:
                # Get the content of 'd' and optimize if enabled
                parsed = data['d']
            else:
                # Sometimes results are directly in root (less common for v2)
                self._log_verbose(f"Warning: OData response missing 'd' wrapper (keys: {list(data.keys())}). Returning raw response.")
                parsed = data
            
            # Optimize the response if enabled
            return self._optimize_response(parsed, response)
            
        except json.JSONDecodeError:
            # Error, print regardless of verbosity
            print(f"ERROR: Non-JSON response received despite Accept header (Status: {response.status_code}).", file=sys.stderr)
            return {"message": "Operation successful (Non-JSON response received).", "content": response.text[:500]}
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Failed to parse OData JSON response: {e}", file=sys.stderr)
            raise ValueError(f"Failed to parse OData response: {e}") from e
    
    def _optimize_response(self, data: Any, response: requests.Response) -> Any:
        """Optimize response data by converting GUIDs and limiting size."""
        # Skip optimization if disabled
        if not self.optimize_guids:
            return data
        
        if isinstance(data, dict):
            # Check if it's a collection response
            if 'results' in data and isinstance(data['results'], list):
                # Get entity type from the first result if available
                entity_type = self._guess_entity_type(data['results'][0] if data['results'] else {})
                guid_fields = self.guid_fields_by_entity.get(entity_type, [])
                
                # Optimize the results
                optimized_results = self.guid_handler.optimize_odata_response(
                    data['results'], 
                    guid_fields=guid_fields,
                    max_items=self.max_response_items
                )
                
                # Check if we truncated
                if self.max_response_items and len(data['results']) > self.max_response_items:
                    data['results'] = optimized_results
                    data['_truncated'] = True
                    data['_max_items'] = self.max_response_items
                else:
                    data['results'] = optimized_results
                    
            else:
                # Single entity response
                entity_type = self._guess_entity_type(data)
                guid_fields = self.guid_fields_by_entity.get(entity_type, [])
                data = self.guid_handler.optimize_odata_response(data, guid_fields=guid_fields)
        
        return data
    
    def _guess_entity_type(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Guess entity type from entity data structure."""
        if not entity_data:
            return None
        
        # Check metadata if available
        if '__metadata' in entity_data and 'type' in entity_data['__metadata']:
            # Extract entity type from fully qualified name
            fqn = entity_data['__metadata']['type']
            return fqn.split('.')[-1] if '.' in fqn else fqn
        
        # Otherwise, try to match by properties
        entity_props = set(entity_data.keys())
        for entity_type, type_def in self.metadata.entity_types.items():
            type_props = {prop.name for prop in type_def.properties}
            # If entity has most of the type's properties, it's likely that type
            if len(entity_props & type_props) >= len(type_props) * 0.7:
                return entity_type
        
        return None

    def _extract_pagination(self, data: Any, response: requests.Response) -> Dict[str, Any]:
        """Extract pagination info from OData v2 response (d.__count, d.__next)."""
        pagination = {}
        total_count = None
        next_skip = None

        # Look for pagination info within the data dictionary (which is usually response['d'])
        data_dict = data if isinstance(data, dict) else {}

        # Check for inline count (OData v2 specific, usually in 'd')
        if '__count' in data_dict:
            try:
                total_count = int(data_dict['__count'])
                pagination['total_count'] = total_count
            except (ValueError, TypeError):
                 if self.verbose: # Only warn if verbose
                    print(f"Warning: Could not parse __count value: {data_dict.get('__count')}", file=sys.stderr)

        # Check for next link (OData v2 specific, usually in 'd')
        if '__next' in data_dict:
            next_link = data_dict['__next']
            pagination['has_more'] = True
            # Try to parse $skip or $skiptoken from the next link
            try:
                parsed_url = urlparse(next_link)
                query_params = parse_qs(parsed_url.query)
                # Prepare suggested next call based on original params + next link info
                original_params = parse_qs(urlparse(response.request.url).query)
                suggested_next = {}
                 # Preserve original params unless overridden by next link
                preserved_keys = ['$filter', '$select', '$expand', '$orderby', '$search', '$top']
                for key in preserved_keys:
                    # Only include if present in the *original* request
                    if key in original_params:
                         suggested_next[key] = original_params[key][0]

                if '$skip' in query_params:
                    next_skip = int(query_params['$skip'][0])
                    pagination['next_skip'] = next_skip
                    suggested_next['$skip'] = next_skip # Override skip
                    # Ensure $skiptoken is removed if $skip is present
                    if '$skiptoken' in suggested_next: del suggested_next['$skiptoken']

                elif '$skiptoken' in query_params:
                    next_token = query_params['$skiptoken'][0]
                    pagination['next_skiptoken'] = next_token
                    suggested_next['$skiptoken'] = next_token # Add skiptoken
                     # Ensure $skip is removed if $skiptoken is present
                    if '$skip' in suggested_next: del suggested_next['$skip']

                # Try to convert $top to int if present
                if '$top' in suggested_next:
                     try: suggested_next['$top'] = int(suggested_next['$top'])
                     except (ValueError, TypeError): del suggested_next['$top'] # Remove if invalid

                pagination['suggested_next_call'] = suggested_next


            except Exception as e:
                 if self.verbose: # Only warn if verbose
                    print(f"Warning: Could not parse parameters from next link '{next_link}': {e}", file=sys.stderr)
        elif total_count is not None and 'results' in data_dict and isinstance(data_dict['results'], list):
             # Infer has_more if count > returned results (requires $inlinecount)
             num_results = len(data_dict['results'])
             # Get current skip from original request URL
             parsed_req_url = urlparse(response.request.url)
             req_params = parse_qs(parsed_req_url.query)
             current_skip = int(req_params.get('$skip', [0])[0])
             current_top_str = req_params.get('$top', [None])[0]
              # Estimate top based on num_results if not specified or invalid
             current_top = num_results
             if current_top_str:
                  try: current_top = int(current_top_str)
                  except (ValueError, TypeError): pass # Keep num_results if $top is invalid

             if total_count > current_skip + num_results:
                 pagination['has_more'] = True
                 next_skip_val = current_skip + (current_top if current_top > 0 and num_results >= current_top else num_results) # Calculate next skip
                 pagination['next_skip'] = next_skip_val
                 # Suggest next call parameters
                 suggested_next = {'$skip': next_skip_val}
                 preserved_keys = ['$filter', '$select', '$expand', '$orderby', '$search', '$top']
                 for key in preserved_keys:
                      if key in req_params:
                           suggested_next[key] = req_params[key][0]
                 # Ensure $skiptoken is removed
                 if '$skiptoken' in suggested_next: del suggested_next['$skiptoken']

                 # Try to convert $top to int
                 if '$top' in suggested_next:
                      try: suggested_next['$top'] = int(suggested_next['$top'])
                      except (ValueError, TypeError): del suggested_next['$top']

                 pagination['suggested_next_call'] = suggested_next


        # Set default has_more if not determined
        if 'has_more' not in pagination:
             pagination['has_more'] = False

        return pagination

    async def list_or_filter_entities(self, entity_set_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve a list of entities with filtering, sorting, pagination etc."""
        url = f"{self.base_url}/{entity_set_name}"

        # Ensure JSON format and add inline count for pagination
        odata_params = {'$format': 'json', '$inlinecount': 'allpages'}

        # Add user-provided OData params ($filter, $top, $skip, $select, $expand, $orderby, $search)
        allowed_params = ['$filter', '$top', '$skip', '$select', '$expand', '$orderby', '$search', '$skiptoken']
        for key, value in params.items():
            # Simple validation: ensure $top and $skip are integers if present
            if key == '$top' and value is not None:
                try: value = int(value)
                except (ValueError, TypeError): raise ValueError("$top parameter must be an integer.")
            if key == '$skip' and value is not None:
                 try: value = int(value)
                 except (ValueError, TypeError): raise ValueError("$skip parameter must be an integer.")

            if key in allowed_params and value is not None:
                odata_params[key] = value

        try:
            self._log_verbose(f"Requesting: GET {url} with params {odata_params}")
            response = await asyncio.to_thread(
                 self._make_request, 'GET', url, params=odata_params
             )
            parsed_data = self._parse_odata_response(response)

            # Extract results and pagination
            # Results might be directly under 'd' or in 'd.results'
            results = parsed_data.get('results', parsed_data) if isinstance(parsed_data, dict) else parsed_data
            pagination = self._extract_pagination(parsed_data, response)

            # Ensure results is always a list for consistency in collection queries
            if not isinstance(results, list):
                 # If pagination suggests multiple items or count > 1, this is unexpected
                 if pagination.get('total_count', 0) > 1 or pagination.get('has_more', False):
                      self._log_verbose(f"Warning: Expected list result for {entity_set_name} filter/list, but got single object {type(results)}. Wrapping in list.")
                      results = [results] if results is not None else []
                 elif results is None: # Handle null result explicitly
                      results = []
                 else: # Likely a single result (count <= 1), wrap in list for consistency
                      results = [results]


            final_response = {"results": results}
            if pagination:
                final_response["pagination"] = pagination

            return final_response

        except requests.exceptions.RequestException as e:
            # Error, print regardless of verbosity
            error_details = self._parse_odata_error(e.response) if e.response else "No details available."
            print(f"ERROR: Error listing/filtering {entity_set_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData request failed ({e.response.status_code if e.response else 'N/A'}): {error_details}") from e
        except Exception as e:
             # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during list/filter {entity_set_name}: {e}", file=sys.stderr)
            raise

    async def get_entity_count(self, entity_set_name: str, filter_param: Optional[str] = None) -> int:
        """Get the count of entities, potentially filtered."""
        url = f"{self.base_url}/{entity_set_name}/$count"
        params = {}
        if filter_param:
            params['$filter'] = filter_param

        try:
            self._log_verbose(f"Requesting: GET {url} with params {params}")
            response = await asyncio.to_thread(
                 self._make_request, 'GET', url, params=params
            )
            # OData V4 uses /$count which returns plain number
            # OData V2 often doesn't support /$count, need fallback
            if response.status_code == 200:
                 # Check content type? Assume plain text for now
                 return int(response.text)
            elif response.status_code in [404, 400, 405]: # Not Found, Bad Request, Method Not Allowed likely means /$count unsupported
                 raise ValueError(f"/$count endpoint not supported or filter invalid (Status: {response.status_code}).")
            else:
                 # Raise error for other unexpected statuses
                  response.raise_for_status()


        except (requests.exceptions.RequestException, ValueError, TypeError) as e:
             # Fallback for services that don't support /$count but support $inlinecount
             self._log_verbose(f"Warning: /$count failed or not supported for {entity_set_name} ({e}). Falling back to $inlinecount.")
             try:
                # Request 0 items but with inline count
                list_params = {'$top': 0} # $inlinecount=allpages added by list_or_filter_entities
                if filter_param:
                    list_params['$filter'] = filter_param
                count_response = await self.list_or_filter_entities(entity_set_name, list_params)
                if 'pagination' in count_response and 'total_count' in count_response['pagination']:
                    return count_response['pagination']['total_count']
                else:
                     # Maybe the service returned results even with $top=0? Count them.
                     if 'results' in count_response and isinstance(count_response['results'], list):
                          self._log_verbose("Warning: $inlinecount fallback didn't return count, counting $top=0 results.")
                          return len(count_response['results'])
                     raise ValueError("Fallback failed: Could not get count via $inlinecount or $top=0.")
             except Exception as fallback_e:
                  # Error, print regardless of verbosity
                  print(f"ERROR: Error getting count for {entity_set_name}: {fallback_e}", file=sys.stderr)
                  raise ValueError(f"Could not determine count for {entity_set_name}: {fallback_e}") from fallback_e
        return -1 # Should not be reached


    async def get_entity(self, entity_set_name: str, key_values: Dict[str, Any], expand: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve a single entity by its key."""
        entity_set = self.metadata.entity_sets.get(entity_set_name)
        if not entity_set: raise ValueError(f"Unknown entity set: {entity_set_name}")
        entity_type = self.metadata.entity_types.get(entity_set.entity_type)
        if not entity_type: raise ValueError(f"Unknown entity type: {entity_set.entity_type}")

        key_str = self._build_key_string(entity_type, key_values)
        url = f"{self.base_url}/{entity_set_name}{key_str}"
        params = {'$format': 'json'}
        if expand:
            params['$expand'] = expand

        try:
            self._log_verbose(f"Requesting: GET {url} with params {params}")
            response = await asyncio.to_thread(
                 self._make_request, 'GET', url, params=params
            )
            return self._parse_odata_response(response)
        except requests.exceptions.RequestException as e:
            # Error, print regardless of verbosity
            error_details = self._parse_odata_error(e.response) if e.response else "No details available."
            print(f"ERROR: Error getting {entity_set_name} with key {key_values}: {e}", file=sys.stderr)
            raise ValueError(f"OData GET request failed ({e.response.status_code if e.response else 'N/A'}): {error_details}") from e
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during get {entity_set_name}: {e}", file=sys.stderr)
            raise


    async def create_entity(self, entity_set_name: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new entity."""
        entity_set = self.metadata.entity_sets.get(entity_set_name)
        if not entity_set: raise ValueError(f"Unknown entity set: {entity_set_name}")
        if not entity_set.creatable: raise ValueError(f"Entity set {entity_set_name} not configured as creatable.")

        url = f"{self.base_url}/{entity_set_name}"
        params = {'$format': 'json'} # Add format to query params for POST

        try:
            self._log_verbose(f"Requesting: POST {url} with data {entity_data}")
            response = await asyncio.to_thread(
                 self._make_request, 'POST', url, params=params, json=entity_data, requires_csrf=True
             )
            # Check for 201 Created specifically, then parse
            if response.status_code == 201:
                return self._parse_odata_response(response)
            else:
                # If not 201, let parse_odata_response handle potential errors/other success codes
                 self._log_verbose(f"Warning: Create entity for {entity_set_name} returned status {response.status_code} (expected 201). Parsing response anyway.")
                 return self._parse_odata_response(response) # Will raise error if status is 4xx/5xx
        except requests.exceptions.RequestException as e:
             # Error, print regardless of verbosity
             error_details = self._parse_odata_error(e.response) if e.response else "No details available."
             print(f"ERROR: Error creating entity in {entity_set_name}: {e}", file=sys.stderr)
             raise ValueError(f"OData POST request failed ({e.response.status_code if e.response else 'N/A'}): {error_details}") from e
        except Exception as e:
             # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during create {entity_set_name}: {e}", file=sys.stderr)
            raise

    async def update_entity(self, entity_set_name: str, key_values: Dict[str, Any], entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing entity (using MERGE/PATCH)."""
        entity_set = self.metadata.entity_sets.get(entity_set_name)
        if not entity_set: raise ValueError(f"Unknown entity set: {entity_set_name}")
        if not entity_set.updatable: raise ValueError(f"Entity set {entity_set_name} not configured as updatable.")
        entity_type = self.metadata.entity_types.get(entity_set.entity_type)
        if not entity_type: raise ValueError(f"Unknown entity type: {entity_set.entity_type}")

        key_str = self._build_key_string(entity_type, key_values)
        url = f"{self.base_url}/{entity_set_name}{key_str}"
        params = {'$format': 'json'} # Add format to query params

        try:
            # Prefer MERGE for partial updates (standard in OData v2/v3)
            self._log_verbose(f"Requesting: MERGE {url} with data {entity_data}")
            response = await asyncio.to_thread(
                  self._make_request, 'MERGE', url, params=params, json=entity_data, requires_csrf=True
             )
            # Some servers might expect PATCH or PUT
            if response.status_code == 405: # Method Not Allowed, try PUT
                 self._log_verbose("MERGE not allowed for update, trying PUT...")
                 self._log_verbose(f"Requesting: PUT {url} with data {entity_data}")
                 response = await asyncio.to_thread(
                       self._make_request, 'PUT', url, params=params, json=entity_data, requires_csrf=True
                 )
                 # If PUT also fails, maybe try PATCH? Less common for v2 update.
                 if response.status_code == 405:
                      self._log_verbose("PUT not allowed for update, trying PATCH...")
                      self._log_verbose(f"Requesting: PATCH {url} with data {entity_data}")
                      response = await asyncio.to_thread(
                            self._make_request, 'PATCH', url, params=params, json=entity_data, requires_csrf=True
                      )


            # Update often returns 204 No Content on success
            if response.status_code == 204:
                 return {"message": f"Successfully updated entity in {entity_set_name} with key {key_values}."}
            else:
                # If other status, parse response (might return updated entity or error)
                 # This will raise an error for 4xx/5xx statuses
                 return self._parse_odata_response(response)

        except requests.exceptions.RequestException as e:
            # Error, print regardless of verbosity
            error_details = self._parse_odata_error(e.response) if e.response else "No details available."
            print(f"ERROR: Error updating entity in {entity_set_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData update request failed ({e.response.status_code if e.response else 'N/A'}): {error_details}") from e
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during update {entity_set_name}: {e}", file=sys.stderr)
            raise

    async def delete_entity(self, entity_set_name: str, key_values: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an entity."""
        entity_set = self.metadata.entity_sets.get(entity_set_name)
        if not entity_set: raise ValueError(f"Unknown entity set: {entity_set_name}")
        if not entity_set.deletable: raise ValueError(f"Entity set {entity_set_name} not configured as deletable.")
        entity_type = self.metadata.entity_types.get(entity_set.entity_type)
        if not entity_type: raise ValueError(f"Unknown entity type: {entity_set.entity_type}")

        key_str = self._build_key_string(entity_type, key_values)
        url = f"{self.base_url}/{entity_set_name}{key_str}"

        try:
            self._log_verbose(f"Requesting: DELETE {url}")
            response = await asyncio.to_thread(
                 self._make_request, 'DELETE', url, requires_csrf=True
            )
            # Delete often returns 204 No Content on success
            if response.status_code == 204:
                 return {"message": f"Successfully deleted entity from {entity_set_name} with key {key_values}."}
            else:
                 # If other status, parse response (likely an error)
                 # This will raise an error for 4xx/5xx statuses
                 return self._parse_odata_response(response)
        except requests.exceptions.RequestException as e:
             # Error, print regardless of verbosity
             error_details = self._parse_odata_error(e.response) if e.response else "No details available."
             print(f"ERROR: Error deleting entity from {entity_set_name}: {e}", file=sys.stderr)
             raise ValueError(f"OData DELETE request failed ({e.response.status_code if e.response else 'N/A'}): {error_details}") from e
        except Exception as e:
             # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during delete {entity_set_name}: {e}", file=sys.stderr)
            raise

    async def list_nodes(self, seed: Optional[int] = None, 
                        max_nodes: int = 100,
                        include_guid: bool = False) -> Dict[str, Any]:
        """
        Specialized method for listing graph nodes with optimization.
        
        Args:
            seed: Optional seed value to filter by
            max_nodes: Maximum number of nodes to retrieve
            include_guid: Whether to include the binary GUID field
            
        Returns:
            Optimized node data
        """
        # Build optimized query - select only essential fields by default
        select_fields = ['Seed', 'Node', 'ObjType', 'ObjName']
        if include_guid:
            select_fields.append('Id')
        
        params = {
            '$top': max_nodes,
            '$select': ','.join(select_fields)
        }
        
        if seed is not None:
            params['$filter'] = f'Seed eq {seed}'
        
        # Use the standard list method
        result = await self.list_or_filter_entities('ZLLM_00_NODESet', params)
        
        # Add query info
        result['_query_info'] = {
            'entity_set': 'ZLLM_00_NODESet',
            'optimized': True,
            'fields_selected': select_fields
        }
        
        return result
    
    async def list_edges(self, seed: Optional[int] = None,
                        max_edges: int = 100,
                        include_guids: bool = False) -> Dict[str, Any]:
        """
        Specialized method for listing graph edges with optimization.
        
        Args:
            seed: Optional seed value to filter by
            max_edges: Maximum number of edges to retrieve
            include_guids: Whether to include the binary GUID fields
            
        Returns:
            Optimized edge data
        """
        # Build optimized query - exclude large binary fields by default
        select_fields = ['Seed', 'Etype']
        if include_guids:
            select_fields.extend(['F', 'T'])
        
        params = {
            '$top': max_edges,
            '$select': ','.join(select_fields)
        }
        
        if seed is not None:
            params['$filter'] = f'Seed eq {seed}'
        
        # Use the standard list method
        result = await self.list_or_filter_entities('ZLLM_00_EDGESet', params)
        
        # Add query info
        result['_query_info'] = {
            'entity_set': 'ZLLM_00_EDGESet',
            'optimized': True,
            'fields_selected': select_fields
        }
        
        return result

    async def invoke_function(self, function_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Invoke a function import."""
        function_import = self.metadata.function_imports.get(function_name)
        if not function_import: raise ValueError(f"Unknown function import: {function_name}")

        url = f"{self.base_url}/{function_name}"
        odata_params = parameters or {}

        # Ensure JSON format - add to URL query params for both GET and POST
        url_parts = list(urlparse(url))
        query = dict(parse_qs(url_parts[4]))
        query['$format'] = ['json'] # Ensure format is in query

        http_method = function_import.http_method
        # Assume POST functions modify state unless metadata indicates otherwise (not standard in v2)
        requires_csrf = (http_method == 'POST')

        try:
            if http_method == 'GET':
                 # Add function parameters to query string for GET
                 current_query = {}
                 for key, value in odata_params.items():
                     # Simple string conversion for query params, handle boolean correctly
                     py_type = next((p.get_python_type() for p in function_import.parameters if p.name == key), str)
                     if py_type == bool:
                          current_query[key] = str(value).lower()
                     # Add handling for other types if needed (e.g., dates)
                     else:
                          current_query[key] = str(value)


                 # Merge with existing query params (like $format)
                 current_query.update({k: v[0] for k,v in query.items()}) # Flatten format param

                 url_parts[4] = urlencode(current_query, doseq=True)
                 final_url = urlunparse(url_parts)
                 self._log_verbose(f"Requesting: GET {final_url}")
                 response = await asyncio.to_thread(
                      self._make_request, 'GET', final_url
                 )

            elif http_method == 'POST':
                 # For POST, format param is in query, data is in body
                 url_parts[4] = urlencode(query, doseq=True)
                 final_url = urlunparse(url_parts)
                 self._log_verbose(f"Requesting: POST {final_url} with data {odata_params}")
                 response = await asyncio.to_thread(
                      self._make_request, 'POST', final_url, json=odata_params, requires_csrf=requires_csrf
                 )
            else:
                raise ValueError(f"Unsupported HTTP method for function import: {http_method}")

            return self._parse_odata_response(response)

        except requests.exceptions.RequestException as e:
            # Error, print regardless of verbosity
            error_details = self._parse_odata_error(e.response) if e.response else "No details available."
            print(f"ERROR: Error invoking function {function_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData function request failed ({e.response.status_code if e.response else 'N/A'}): {error_details}") from e
        except Exception as e:
             # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during function {function_name}: {e}", file=sys.stderr)
            raise


# --- MCP Bridge ---

class ODataMCPBridge:
    """Bridge between OData and MCP, creating tools from OData metadata."""

    def __init__(self, service_url: str, auth: Optional[Tuple[str, str]] = None, mcp_name: str = "odata-mcp", verbose: bool = False, 
                 tool_prefix: Optional[str] = None, tool_postfix: Optional[str] = None, use_postfix: bool = True):
        self.service_url = service_url
        self.auth = auth
        self.verbose = verbose # Store verbosity
        self.mcp = FastMCP(name=mcp_name, timeout=120) # Increased timeout
        self.registered_entity_tools = {}
        self.registered_function_tools = []
        self.use_postfix = use_postfix
        
        # Generate service identifier from service URL
        service_id = self._generate_service_identifier(service_url)
        
        if use_postfix:
            self.tool_prefix = ""
            self.tool_postfix = tool_postfix or f"_for_{service_id}"
        else:
            self.tool_prefix = tool_prefix or f"{service_id}_"
            self.tool_postfix = ""

        try:
            self._log_verbose("Initializing Metadata Parser...")
            self.parser = MetadataParser(service_url, auth, verbose=self.verbose)
            self._log_verbose("Parsing OData Metadata...")
            self.metadata = self.parser.parse()
            self._log_verbose("Metadata Parsed. Initializing OData Client...")
            self.client = ODataClient(
                self.metadata, 
                auth, 
                verbose=self.verbose,
                optimize_guids=True,  # Enable GUID optimization by default
                max_response_items=1000  # Limit response size
            )
            self._log_verbose("OData Client Initialized.")

            self._log_verbose("Registering MCP Tools...")
            self._register_tools()
            self._log_verbose("MCP Tools Registered.")

        except Exception as e:
             # Fatal error, print regardless of verbosity
            print(f"FATAL ERROR during initialization: {e}", file=sys.stderr)
            print("The wrapper cannot start. Please check the OData service URL, credentials, and network connectivity.", file=sys.stderr)
            # Print traceback for debugging
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    def _log_verbose(self, message: str):
        """Prints message to stderr only if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print(f"[{timestamp} Bridge VERBOSE] {message}", file=sys.stderr) # Add prefix for clarity
    
    def _generate_service_identifier(self, service_url: str) -> str:
        """Generate a unique service identifier from the service URL."""
        from urllib.parse import urlparse
        
        parsed = urlparse(service_url)
        
        # Extract meaningful parts
        host_parts = parsed.hostname.replace('.', '_') if parsed.hostname else 'localhost'
        path_parts = parsed.path.strip('/').replace('/', '_').replace('.', '_')
        
        # Handle common OData service patterns
        if 'northwind' in service_url.lower():
            if 'V4' in service_url:
                return 'northwind_v4'
            elif 'V3' in service_url:
                return 'northwind_v3'
            elif 'V2' in service_url:
                return 'northwind_v2'
            else:
                return 'northwind'
        elif 'trippin' in service_url.lower():
            return 'trippin'
        elif 'zmcp' in service_url.lower():
            # Extract SAP service name
            import re
            match = re.search(r'/([A-Z][A-Z0-9_]+)_SRV', service_url)
            if match:
                return match.group(1).lower()
            return 'sap_service'
        elif 'odata_svc' in path_parts.lower() or 'odata' in path_parts.lower():
            return 'demo_v2'
        else:
            # Fallback: use host and first path segment
            parts = [p for p in [host_parts, path_parts.split('_')[0]] if p]
            result = '_'.join(parts)[:20]  # Limit length
            # Ensure it's a valid identifier
            result = re.sub(r'[^a-zA-Z0-9_]', '_', result)
            return result.lower() or 'odata'
    
    def _make_tool_name(self, base_name: str) -> str:
        """Generate a tool name with appropriate prefix or postfix."""
        return f"{self.tool_prefix}{base_name}{self.tool_postfix}"


    def _format_docstring(self, base_desc: str, params_list: List[Dict[str, Any]], entity_or_func_desc: Optional[str] = None) -> str:
        """Create a formatted docstring for a tool from a list of parameter dicts."""
        doc = f"{base_desc}\n\n"
        if entity_or_func_desc:
            desc_prefix = "Entity Description" if 'entity' in base_desc.lower() else "Function Description"
            doc += f"{desc_prefix}: {entity_or_func_desc}\n\n"
        doc += "Parameters:\n"
        if params_list:
            for param in params_list:
                name = param['name']
                type_str = param['type_hint']
                required = param['required']
                p_desc = param.get('description')

                req_str = "**required**" if required else "optional"
                desc_str = f" - {p_desc}" if p_desc else ""
                doc += f"    - `{name}` ({type_str}, {req_str}){desc_str}\n"
        else:
            doc += "    None\n"
        # Add note about potential OData errors
        doc += "\nNote: Operations may fail if input data violates constraints defined in the OData service.\n"
        return doc

    def _create_and_register_tool(self, tool_name: str, param_defs: List[Dict[str, Any]], docstring: str, implementation_logic: callable):
        """
        Dynamically creates a function with the specified signature using exec()
        and registers it as an MCP tool.

        Args:
            tool_name: The name of the tool (and the function).
            param_defs: A list of dictionaries, each describing a parameter:
                         {'name': str, 'type_hint': str, 'required': bool, 'description': Optional[str]}
            docstring: The docstring for the tool function.
            implementation_logic: The actual async function to call from the generated wrapper.
                                  It should accept 'self' and keyword arguments matching param_defs.
        """
        param_strings = []
        param_names = []
        for p in param_defs:
            name = p['name']
            # Ensure names are valid Python identifiers (basic check)
            safe_name = re.sub(r'\W|^(?=\d)', '_', name) # Replace non-alphanumeric, starting digits
            if safe_name != name:
                 print(f"Warning: Parameter name '{name}' mapped to '{safe_name}' for tool '{tool_name}'", file=sys.stderr)
                 name = safe_name # Use the safe name

            param_names.append(name)
            type_hint = p['type_hint']
            if p['required']:
                param_strings.append(f"{name}: {type_hint}")
            else:
                # Add =None for optional parameters
                param_strings.append(f"{name}: {type_hint} = None")

        signature_params = ", ".join(param_strings)
        # Use * to force keyword-only arguments for clarity
        signature = f"async def {tool_name}(*, {signature_params}) -> str:"

        # Body calls the provided implementation logic
        # Pass only the defined parameters to the implementation
        impl_args = ", ".join(f"{name}={name}" for name in param_names)
        body = [
            f"    '''{docstring}'''",
            # Get the implementation function from the registry
            f"    impl_func = _implementation_registry['{tool_name}']",
            f"    try:",
            f"        return await impl_func({impl_args})",
            f"    except Exception as e:",
            f"        err_msg = f'Error in tool {tool_name}: {{str(e)}}'",
            f"        print(f'ERROR: {{err_msg}}', file=sys.stderr)",
            # Optionally include traceback if verbose?
            # f"        if self.verbose: traceback.print_exc(file=sys.stderr)",
            f"        return json.dumps({{'error': err_msg}}, indent=2)",
        ]

        func_def_str = signature + "\n" + "\n".join(body)

        # Ensure the implementation registry exists
        if not hasattr(self, '_implementation_registry'):
            self._implementation_registry = {}
        
        # Store the implementation logic in the registry
        self._implementation_registry[tool_name] = implementation_logic

        # Prepare scope for exec, including necessary types and modules
        exec_scope = {
            "_implementation_registry": self._implementation_registry,
            "asyncio": asyncio,
            "json": json,
            "Optional": Optional,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "print": print, # Allow printing errors within execed code
            "sys": sys,
            "traceback": traceback,
        }

        try:
            # Execute the function definition string
            # Pass exec_scope as both globals and locals so _implementation_registry is available
            self._log_verbose(f"Generating function for {tool_name}:\n{func_def_str}")
            exec(func_def_str, exec_scope, exec_scope)
            # Retrieve the newly defined function object
            tool_func = exec_scope[tool_name]

            # Register the dynamically created function
            self.mcp.add_tool(tool_func, name=tool_name)
            self._log_verbose(f"Registered tool: {tool_name}")
            return tool_name
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Failed to create or register tool {tool_name}: {e}", file=sys.stderr)
            if self.verbose:
                 traceback.print_exc(file=sys.stderr) # Show traceback if verbose
            return None

    # --- Tool Implementation Logic Helpers ---
    # These contain the actual logic called by the dynamically generated functions

    async def _impl_list_filter(self, entity_set_name: str, **kwargs) -> str:
        """Logic for list/filter tool."""
        params = {
            "$filter": kwargs.get('filter'),
            "$select": kwargs.get('select'),
            "$expand": kwargs.get('expand'),
            "$orderby": kwargs.get('orderby'),
            "$top": kwargs.get('top'),
            "$skip": kwargs.get('skip'),
            "$skiptoken": kwargs.get('skiptoken')
        }
        odata_params = {k: v for k, v in params.items() if v is not None}
        result = await self.client.list_or_filter_entities(entity_set_name, odata_params)
        if params["$filter"] and 'results' in result:
             explanation = f"Returned {entity_set_name} matching filter: '{params['$filter']}'"
             try:
                  json.dumps(explanation)
                  result['filter_explanation'] = explanation
             except TypeError:
                  result['filter_explanation'] = f"Returned {entity_set_name} matching filter (details omitted due to serialization issue)."
        return json.dumps(result, indent=2, default=str)

    async def _impl_count(self, entity_set_name: str, **kwargs) -> str:
        """Logic for count tool."""
        filter_param = kwargs.get('filter')
        count = await self.client.get_entity_count(entity_set_name, filter_param)
        result = {"count": count}
        if filter_param:
            result["filter_explanation"] = f"Counted {entity_set_name} matching filter: '{filter_param}'"
        return json.dumps(result, indent=2)

    async def _impl_search(self, entity_set_name: str, **kwargs) -> str:
        """Logic for search tool."""
        params = {
            "$search": kwargs.get('search_term'),
            "$top": kwargs.get('top'),
            "$skip": kwargs.get('skip')
        }
        odata_params = {k: v for k, v in params.items() if v is not None}
        result = await self.client.list_or_filter_entities(entity_set_name, odata_params)
        result['search_explanation'] = f"Found {entity_set_name} matching search term: '{params['$search']}'"
        return json.dumps(result, indent=2, default=str)

    async def _impl_get_entity(self, entity_set_name: str, entity_type: EntityType, **kwargs) -> str:
        """Logic for get entity tool."""
        key_props = entity_type.get_key_properties()
        key_values = {}
        missing_keys = []
        param_names = {p['name'] for p in self._get_param_defs_for_keys(key_props)}

        for name in param_names:
             if name not in kwargs:
                  missing_keys.append(name)
             else:
                 key_values[name] = kwargs[name]

        if missing_keys:
             raise ValueError(f"Missing required key parameters: {', '.join(missing_keys)}")

        expand = kwargs.get('expand') # Support expand parameter if passed
        result = await self.client.get_entity(entity_set_name, key_values, expand)
        return json.dumps(result, indent=2, default=str)

    async def _impl_create_entity(self, entity_set_name: str, entity_type: EntityType, **kwargs) -> str:
        """Logic for create entity tool."""
        # Include all non-nullable properties (including keys) as required
        required_props = {p.name for p in entity_type.properties if not p.nullable}
        entity_data = {k: v for k, v in kwargs.items() if v is not None}

        missing_required = [name for name in required_props if name not in entity_data]
        if missing_required:
            raise ValueError(f"Missing required properties: {', '.join(missing_required)}")

        result = await self.client.create_entity(entity_set_name, entity_data)
        return json.dumps(result, indent=2, default=str)

    async def _impl_update_entity(self, entity_set_name: str, entity_type: EntityType, **kwargs) -> str:
        """Logic for update entity tool."""
        key_props = entity_type.get_key_properties()
        key_prop_names = {p.name for p in key_props}
        key_values = {}
        missing_keys = []

        for name in key_prop_names:
             if name not in kwargs:
                  missing_keys.append(name)
             else:
                 key_values[name] = kwargs[name]

        if missing_keys:
            raise ValueError(f"Missing required key parameters: {', '.join(missing_keys)}")

        entity_data = {k: v for k, v in kwargs.items() if k not in key_prop_names and v is not None}
        if not entity_data:
             raise ValueError("No properties provided to update.")

        result = await self.client.update_entity(entity_set_name, key_values, entity_data)
        return json.dumps(result, indent=2, default=str)

    async def _impl_delete_entity(self, entity_set_name: str, entity_type: EntityType, **kwargs) -> str:
        """Logic for delete entity tool."""
        key_props = entity_type.get_key_properties()
        key_prop_names = {p.name for p in key_props}
        key_values = {}
        missing_keys = []

        for name in key_prop_names:
             if name not in kwargs:
                  missing_keys.append(name)
             else:
                 key_values[name] = kwargs[name]

        if missing_keys:
            raise ValueError(f"Missing required key parameters: {', '.join(missing_keys)}")

        result = await self.client.delete_entity(entity_set_name, key_values)
        return json.dumps(result, indent=2, default=str)

    async def _impl_invoke_function(self, function_name: str, function_import: FunctionImport, **kwargs) -> str:
         """Logic for invoking function import."""
         required_params = {p.name for p in function_import.parameters if not p.nullable}
         param_values = {k: v for k, v in kwargs.items() if v is not None}

         missing_required = [name for name in required_params if name not in param_values]
         if missing_required:
              raise ValueError(f"Missing required parameters: {', '.join(missing_required)}")

         result = await self.client.invoke_function(function_name, param_values)
         # Wrap primitive results
         if isinstance(result, (str, int, float, bool)):
              final_result = {"result": result}
         else:
              final_result = result if result is not None else {}
         return json.dumps(final_result, indent=2, default=str)


    # --- Tool Registration Methods (Using _create_and_register_tool) ---

    def _get_param_defs(self, properties: List[EntityProperty], required_override: Optional[bool] = None) -> List[Dict[str, Any]]:
         """Helper to build parameter definition list for registration."""
         defs = []
         for prop in properties:
              # Keys are always required for get/update/delete, ignore OData nullability
              is_required = prop.is_key or (required_override if required_override is not None else not prop.nullable)
              defs.append({
                  'name': prop.name,
                  'type_hint': prop.get_python_type_hint(),
                  'required': is_required,
                  'description': prop.description
              })
         return defs

    def _get_param_defs_for_keys(self, key_props: List[EntityProperty]) -> List[Dict[str, Any]]:
        """Helper for key parameter definitions (always required)."""
        return [{
            'name': prop.name,
            'type_hint': prop.get_python_type_hint().replace('Optional[','').replace(']',''), # Keys shouldn't be optional in signature
            'required': True,
            'description': prop.description or "Part of the entity key"
        } for prop in key_props]


    def _register_tools(self):
        """Register all OData-based tools with MCP."""
        # --- Service Info Tool ---
        # This one is simple, no dynamic params needed
        self.add_service_info_tool()

        # --- Entity Set Tools ---
        for es_name, entity_set in self.metadata.entity_sets.items():
            entity_type = self.metadata.entity_types.get(entity_set.entity_type)
            if not entity_type:
                self._log_verbose(f"Warning: Skipping tools for EntitySet '{es_name}' because EntityType '{entity_set.entity_type}' was not found or defined.")
                continue

            self.registered_entity_tools[es_name] = []
            tool_name = None # Reset for each tool type

            # --- List / Filter Tool ---
            try:
                tool_name = self._make_tool_name(f"filter_{es_name}")
                params = [
                    {'name': 'filter', 'type_hint': 'Optional[str]', 'required': False, 'description': "OData $filter expression"},
                    {'name': 'select', 'type_hint': 'Optional[str]', 'required': False, 'description': "Comma-separated properties to return"},
                    {'name': 'expand', 'type_hint': 'Optional[str]', 'required': False, 'description': "Comma-separated navigation properties to expand"},
                    {'name': 'orderby', 'type_hint': 'Optional[str]', 'required': False, 'description': "Property to sort by"},
                    {'name': 'top', 'type_hint': 'Optional[int]', 'required': False, 'description': "Maximum number of entities"},
                    {'name': 'skip', 'type_hint': 'Optional[int]', 'required': False, 'description': "Number of entities to skip"},
                    {'name': 'skiptoken', 'type_hint': 'Optional[str]', 'required': False, 'description': "Continuation token for pagination"}
                ]
                base_desc = f"Retrieve a list of {entity_type.name} entities from the '{es_name}' set."
                doc = self._format_docstring(base_desc, params, entity_set.description)
                # Need partial or lambda to pass extra args to impl
                # Capture current instance and entity_set_name in closure
                def make_logic(instance, set_name):
                    async def logic(**kwargs):
                        return await instance._impl_list_filter(entity_set_name=set_name, **kwargs)
                    return logic
                logic = make_logic(self, es_name)

                registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                if registered_name: self.registered_entity_tools[es_name].append(registered_name)
            except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)


            # --- Count Tool ---
            try:
                tool_name = self._make_tool_name(f"count_{es_name}")
                params = [{'name': 'filter', 'type_hint': 'Optional[str]', 'required': False, 'description': "OData $filter expression"}]
                base_desc = f"Get the total count of {entity_type.name} entities in the '{es_name}' set."
                doc = self._format_docstring(base_desc, params, entity_set.description)
                # Capture current instance and entity_set_name in closure
                def make_logic(instance, set_name):
                    async def logic(**kwargs):
                        return await instance._impl_count(entity_set_name=set_name, **kwargs)
                    return logic
                logic = make_logic(self, es_name)

                registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                if registered_name: self.registered_entity_tools[es_name].append(registered_name)
            except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)

            # --- Search Tool ---
            try:
                tool_name = self._make_tool_name(f"search_{es_name}")
                params = [
                    {'name': 'search_term', 'type_hint': 'str', 'required': True, 'description': "Text term(s) to search for"},
                    {'name': 'top', 'type_hint': 'Optional[int]', 'required': False, 'description': "Maximum number of entities"},
                    {'name': 'skip', 'type_hint': 'Optional[int]', 'required': False, 'description': "Number of entities to skip"}
                ]
                search_desc = " (Service indicates search IS supported)" if entity_set.searchable else " (Service indicates search may NOT be supported)"
                base_desc = f"Performs a free-text search within the '{es_name}' set{search_desc}."
                doc = self._format_docstring(base_desc, params, entity_set.description)
                # Capture current instance and entity_set_name in closure
                def make_logic(instance, set_name):
                    async def logic(**kwargs):
                        return await instance._impl_search(entity_set_name=set_name, **kwargs)
                    return logic
                logic = make_logic(self, es_name)

                registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                if registered_name: self.registered_entity_tools[es_name].append(registered_name)
            except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)

            # --- Get Tool ---
            key_props = entity_type.get_key_properties()
            if key_props:
                 try:
                    tool_name = self._make_tool_name(f"get_{es_name}")
                    params = self._get_param_defs_for_keys(key_props)
                    # Add optional expand parameter
                    params.append({'name': 'expand', 'type_hint': 'Optional[str]', 'required': False, 'description': "Navigation properties to expand"})

                    base_desc = f"Retrieve a single {entity_type.name} entity from '{es_name}' by its unique key(s)."
                    doc = self._format_docstring(base_desc, params, entity_set.description)
                    # Capture current instance, entity_set_name and entity_type in closure
                    def make_logic(instance, set_name, e_type):
                        async def logic(**kwargs):
                            return await instance._impl_get_entity(entity_set_name=set_name, entity_type=e_type, **kwargs)
                        return logic
                    logic = make_logic(self, es_name, entity_type)

                    registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                    if registered_name: self.registered_entity_tools[es_name].append(registered_name)
                 except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)


            # --- CRUD Tools (conditional) ---
            if entity_set.creatable:
                try:
                    tool_name = self._make_tool_name(f"create_{es_name}")
                    # Include ALL properties for create (including keys that may need to be specified)
                    params = self._get_param_defs(entity_type.properties)
                    base_desc = f"Create a new {entity_type.name} entity in the '{es_name}' set."
                    doc = self._format_docstring(base_desc, params, entity_set.description)
                    # Capture current instance, entity_set_name and entity_type in closure
                    def make_logic(instance, set_name, e_type):
                        async def logic(**kwargs):
                            return await instance._impl_create_entity(entity_set_name=set_name, entity_type=e_type, **kwargs)
                        return logic
                    logic = make_logic(self, es_name, entity_type)

                    registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                    if registered_name: self.registered_entity_tools[es_name].append(registered_name)
                except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)


            if entity_set.updatable and key_props: # Need keys to update
                try:
                    tool_name = self._make_tool_name(f"update_{es_name}")
                    # Params are keys (required) + non-keys (optional)
                    key_params = self._get_param_defs_for_keys(key_props)
                    data_params = self._get_param_defs([p for p in entity_type.properties if not p.is_key], required_override=False) # All data params optional for MERGE/PATCH
                    params = key_params + data_params
                    base_desc = f"Update an existing {entity_type.name} entity in '{es_name}' using its key(s). Uses MERGE/PATCH semantics."
                    doc = self._format_docstring(base_desc, params, entity_set.description)
                    # Capture current instance, entity_set_name and entity_type in closure
                    def make_logic(instance, set_name, e_type):
                        async def logic(**kwargs):
                            return await instance._impl_update_entity(entity_set_name=set_name, entity_type=e_type, **kwargs)
                        return logic
                    logic = make_logic(self, es_name, entity_type)

                    registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                    if registered_name: self.registered_entity_tools[es_name].append(registered_name)
                except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)


            if entity_set.deletable and key_props: # Need keys to delete
                 try:
                    tool_name = self._make_tool_name(f"delete_{es_name}")
                    params = self._get_param_defs_for_keys(key_props)
                    base_desc = f"Delete a {entity_type.name} entity from '{es_name}' using its unique key(s)."
                    doc = self._format_docstring(base_desc, params, entity_set.description)
                    # Capture current instance, entity_set_name and entity_type in closure
                    def make_logic(instance, set_name, e_type):
                        async def logic(**kwargs):
                            return await instance._impl_delete_entity(entity_set_name=set_name, entity_type=e_type, **kwargs)
                        return logic
                    logic = make_logic(self, es_name, entity_type)

                    registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                    if registered_name: self.registered_entity_tools[es_name].append(registered_name)
                 except Exception as e: print(f"ERROR registering {tool_name}: {e}", file=sys.stderr)


        # --- Function Import Tools ---
        for func_name, func_import in self.metadata.function_imports.items():
            try:
                 # Params based on function import definition
                 params = self._get_param_defs(func_import.parameters) # Required based on nullability
                 base_desc = f"Invoke the OData function import '{func_name}'.\nHTTP Method: {func_import.http_method}"
                 doc = self._format_docstring(base_desc, params, func_import.description)
                 # Capture current instance, func_name and func_import in closure
                 def make_logic(instance, fn, fi):
                     async def logic(**kwargs):
                         return await instance._impl_invoke_function(function_name=fn, function_import=fi, **kwargs)
                     return logic
                 logic = make_logic(self, func_name, func_import)

                 tool_name = self._make_tool_name(func_name)
                 registered_name = self._create_and_register_tool(tool_name, params, doc, logic)
                 if registered_name: self.registered_function_tools.append(registered_name)
            except Exception as e: print(f"ERROR registering function {func_name}: {e}", file=sys.stderr)


        # --- Log Summary (only if verbose) ---
        if self.verbose:
            print("\n--- Registered Tools Summary ---", file=sys.stderr)
            print(f"- Service Info: {self._make_tool_name('odata_service_info')}", file=sys.stderr)
            for es_name, tools in self.registered_entity_tools.items():
                if tools:
                    print(f"- Entity Set '{es_name}': {', '.join(sorted(tools))}", file=sys.stderr)
            if self.registered_function_tools:
                 print(f"- Function Imports: {', '.join(sorted(self.registered_function_tools))}", file=sys.stderr)
            print("-------------------------------\n", file=sys.stderr)

    # add_service_info_tool remains the same as v4 (omitted for brevity)
    def add_service_info_tool(self):
        """Add a tool to provide information about the OData service structure."""
        async def odata_service_info() -> str:
            """Provides metadata about the configured OData service, including available entity sets, entity types, function imports, and registered tools."""
            # Use previously stored registration info for tools
            registered_entity_tools_summary = {
                 name: tools for name, tools in self.registered_entity_tools.items() if tools
             }

            entity_set_details = {}
            for name, es in self.metadata.entity_sets.items():
                 # Attempt to get the related entity type description
                 et = self.metadata.entity_types.get(es.entity_type)
                 et_desc = et.description if et else None


                 entity_set_details[name] = {
                     "entity_type": es.entity_type,
                     "description": es.description or et_desc or "No description", # Use entity type desc as fallback
                     "creatable": es.creatable,
                     "updatable": es.updatable,
                     "deletable": es.deletable,
                     "searchable": es.searchable,
                 }

            entity_type_details = {}
            for name, et in self.metadata.entity_types.items():
                 entity_type_details[name] = {
                     "description": et.description or "No description",
                     "key_properties": et.key_properties,
                     "properties": [ # Convert properties to dicts for JSON
                         {
                             "name": p.name,
                             "type": p.type,
                             "is_key": p.is_key,
                             "nullable": p.nullable,
                             "description": p.description or "No description"
                          } for p in et.properties
                     ]
                 }

            function_import_details = {}
            for name, fi in self.metadata.function_imports.items():
                 function_import_details[name] = {
                     "description": fi.description or "No description",
                     "http_method": fi.http_method,
                     "return_type": fi.return_type or "Not specified",
                     "parameters": [ # Convert params to dicts for JSON
                         {
                             "name": p.name,
                             "type": p.type,
                             "nullable": p.nullable,
                             "description": p.description or "No description"
                         } for p in fi.parameters
                     ]
                 }

            info = {
                "service_url": self.metadata.service_url,
                "service_description": self.metadata.service_description or "No description provided in metadata.",
                "entity_sets": entity_set_details,
                "entity_types": entity_type_details, # Added entity type details
                "function_imports": function_import_details, # Added function details
                "registered_entity_tools_summary": registered_entity_tools_summary, # Summary of tools per entity set
                "registered_function_tools": self.registered_function_tools
            }
            try:
                 # Use default=str for complex objects that might not be serializable otherwise
                 return json.dumps(info, indent=2, default=str)
            except TypeError as e:
                  # Error, print regardless of verbosity
                  print(f"ERROR: Error serializing service info: {e}", file=sys.stderr)
                  return json.dumps({"error": "Could not serialize service metadata."})


        try:
            # Register tool with appropriate naming
            tool_name = self._make_tool_name("odata_service_info")
            self.mcp.add_tool(odata_service_info, name=tool_name)
            self._log_verbose(f"Registered tool: {tool_name}")
        except Exception as e:
             # Error, print regardless of verbosity
            print(f"ERROR: Error registering odata_service_info tool: {e}", file=sys.stderr)


    def run(self):
        """Run the MCP server."""
        # Log startup message only if verbose
        self._log_verbose(f"Starting OData MCP bridge for service: {self.service_url}")
        self._log_verbose(f"MCP Server Name: {self.mcp.name}")
        if not self.metadata.entity_sets:
              # Warning, print only if verbose
             self._log_verbose("Warning: No entity sets were successfully processed. Tools may be limited.")

        # The FastMCP server run method handles the main loop
        self.mcp.run()

# --- Main Execution ---
# (main function remains the same as v4 - code omitted for brevity)
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OData to MCP Wrapper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )
    # Add --service as an optional argument
    parser.add_argument("--service", dest="service_via_flag", help="URL of the OData service (overrides positional argument and ODATA_SERVICE_URL env var)")
    # Keep positional service_url as fallback
    parser.add_argument("service_url_pos", nargs='?', help="URL of the OData service (alternative to --service flag or env var)")
    parser.add_argument("-u", "--user", help="Username for basic authentication (overrides ODATA_USERNAME env var)")
    parser.add_argument("-p", "--password", help="Password for basic authentication (overrides ODATA_PASSWORD env var)")
    # Allow --debug as alias for --verbose
    parser.add_argument("-v", "--verbose", "--debug", dest="verbose", action="store_true", help="Enable verbose output to stderr")
    # Tool naming options
    parser.add_argument("--tool-prefix", help="Custom prefix for tool names (use with --no-postfix)")
    parser.add_argument("--tool-postfix", help="Custom postfix for tool names (default: _for_<service_id>)")
    parser.add_argument("--no-postfix", action="store_true", help="Use prefix instead of postfix for tool naming")

    args = parser.parse_args()

    auth = None
    service_url = None

    # --- Configuration Handling ---
    # Priority: --service flag > Positional argument > Environment Variable > .env file

    # 1. --service flag
    if args.service_via_flag:
        service_url = args.service_via_flag
        if args.verbose: print("[VERBOSE] Using OData service URL from --service flag.", file=sys.stderr)

    # 2. Positional Argument
    if service_url is None and args.service_url_pos:
        service_url = args.service_url_pos
        if args.verbose: print("[VERBOSE] Using OData service URL from positional argument.", file=sys.stderr)

    # 3. Environment Variables (loaded by load_dotenv)
    if service_url is None:
        service_url = os.getenv("ODATA_URL")
        if service_url and args.verbose: print("[VERBOSE] Using ODATA_URL from environment.", file=sys.stderr)

    env_user = os.getenv("ODATA_USER")
    env_pass = os.getenv("ODATA_PASS")

    # Determine final user/pass based on priority: CLI args > Env Vars
    final_user = args.user if args.user is not None else env_user
    final_pass = args.password if args.password is not None else env_pass

    if final_user and final_pass:
         auth = (final_user, final_pass)
         if args.verbose: print(f"[VERBOSE] Using authentication for user: {final_user}", file=sys.stderr)
    elif args.verbose:
          # Print only if verbose and no auth is configured
         print("[VERBOSE] No complete authentication provided or configured. Attempting anonymous access.", file=sys.stderr)


    # Check if service URL is determined
    if not service_url:
        # Error, print regardless of verbosity
        print("ERROR: OData service URL not provided.", file=sys.stderr)
        print("Provide it via the --service flag, as a positional argument, or ODATA_URL environment variable.", file=sys.stderr)
        parser.print_help(file=sys.stderr) # Show help message
        sys.exit(1)


    # Handle SIGINT (Ctrl+C) and SIGTERM gracefully
    def signal_handler(sig, frame):
        # Print regardless of verbosity, as it's a shutdown event
        print(f"\n{signal.Signals(sig).name} received, shutting down server...", file=sys.stderr)
        # Add any cleanup logic needed here (e.g., close sessions)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler) # Handle TERM signal too

    # Create and run the bridge
    try:
        # Pass verbose flag and tool naming options to the bridge
        bridge = ODataMCPBridge(
            service_url, 
            auth, 
            verbose=args.verbose,
            tool_prefix=args.tool_prefix,
            tool_postfix=args.tool_postfix,
            use_postfix=not args.no_postfix
        )
        bridge.run()
    except Exception as e:
        # Fatal error, print regardless of verbosity
        print(f"\n--- FATAL ERROR ---", file=sys.stderr)
        print(f"An unexpected error occurred during startup or runtime: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("-------------------", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()