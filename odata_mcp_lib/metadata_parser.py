"""
OData metadata parser for extracting entity types, sets, and function imports.
"""

import sys
from datetime import datetime
from typing import Dict, Optional, Tuple
import requests
from lxml import etree

from .constants import NAMESPACES
from .models import EntityProperty, EntityType, EntitySet, FunctionImport, ODataMetadata


class MetadataParser:
    """Parses OData v2 metadata from an OData service."""

    def __init__(self, service_url: str, auth: Optional[Tuple[str, str]] = None, verbose: bool = False):
        self.service_url = service_url.rstrip('/')
        self.metadata_url = f"{self.service_url}/$metadata"
        self.auth = auth
        self.verbose = verbose
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
        # Standard headers
        self.session.headers.update({
            'Accept': 'application/xml, application/atom+xml, application/json',
            'User-Agent': 'OData-MCP-Wrapper/1.3'
        })

    def _log_verbose(self, message: str):
        """Prints message to stderr only if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print(f"[{timestamp} Parser VERBOSE] {message}", file=sys.stderr)

    def _get_description(self, element) -> Optional[str]:
        """Helper to extract description from annotations (basic attempt)."""
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
                    if b'</edmx:Edmx>' not in response.content:  # Quick check if it looks like XML
                        print("ERROR: Response doesn't seem to be XML. Attempting service doc discovery.", file=sys.stderr)
                        raise ValueError("Metadata response is not valid XML")
                    else:
                        raise  # Re-raise original parsing error

                # Find the main schema element for descriptions
                schema = root.find('.//edm:Schema', namespaces=NAMESPACES)
                if schema is not None:
                    service_description = self._get_description(schema)

                entity_types = self._parse_entity_types(root)
                entity_sets = self._parse_entity_sets(root, entity_types)
                function_imports = self._parse_function_imports(root)

            except Exception as xml_error:
                # This is an actual error during processing
                print(f"ERROR: Error processing XML metadata: {xml_error}", file=sys.stderr)
                self._log_verbose("Falling back to service document discovery...")

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
                raise e  # Re-raise the original error

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
                        entity_type=name,  # Assume type name matches set name initially
                        description=title if title != name else None  # Only use title if it's different from href
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
            entity_type_fqn = es_elem.get('EntityType')  # Fully qualified name
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
                http_method = func_elem.get('HttpMethod', 'GET').upper()  # Fallback without namespace
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
                    continue  # Skip output-only parameters

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