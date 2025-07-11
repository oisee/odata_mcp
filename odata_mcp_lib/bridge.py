"""
OData to MCP bridge that dynamically generates MCP tools from OData metadata.
"""

import asyncio
import json
import re
import sys
import signal
import traceback
import fnmatch
import tempfile
import platform
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

try:
    from fastmcp import FastMCP
    from fastmcp.tools import Tool
    import mcp.types as types
except ImportError:
    print("ERROR: Could not import FastMCP. Make sure it's installed and accessible.", file=sys.stderr)
    print("You might need to adjust the import statement based on your project structure.", file=sys.stderr)
    sys.exit(1)

from .transport import Transport, TransportMessage

from .models import EntityProperty, EntityType, FunctionImport
from .metadata_parser import MetadataParser
from .client import ODataClient
from .name_shortener import NameShortener
from .hint_manager import HintManager


class ODataMCPBridge:
    """Bridge between OData and MCP, creating tools from OData metadata."""

    def __init__(self, service_url: str, auth: Optional[Union[Tuple[str, str], Dict[str, str]]] = None, mcp_name: str = "odata-mcp", verbose: bool = False, 
                 tool_prefix: Optional[str] = None, tool_postfix: Optional[str] = None, use_postfix: bool = True, tool_shrink: bool = False,
                 allowed_entities: Optional[List[str]] = None, allowed_functions: Optional[List[str]] = None, sort_tools: bool = True,
                 pagination_hints: bool = False, legacy_dates: bool = True, verbose_errors: bool = False,
                 response_metadata: bool = False, max_response_size: int = 5 * 1024 * 1024, max_items: int = 100,
                 read_only: bool = False, read_only_but_functions: bool = False,
                 trace_mcp: bool = False, hints_file: Optional[str] = None, hint: Optional[str] = None,
                 transport: Optional[Transport] = None, info_tool_name: Optional[str] = None,
                 enabled_operations: Optional[set] = None, disabled_operations: Optional[set] = None):
        self.service_url = service_url
        self.auth = auth
        self.verbose = verbose
        self.tool_shrink = tool_shrink
        self.allowed_entities = allowed_entities
        self.allowed_functions = allowed_functions
        self.sort_tools = sort_tools
        self.pagination_hints = pagination_hints
        self.legacy_dates = legacy_dates
        self.verbose_errors = verbose_errors
        self.response_metadata = response_metadata
        self.max_response_size = max_response_size
        self.max_items = max_items
        self.read_only = read_only
        self.read_only_but_functions = read_only_but_functions
        self.trace_mcp = trace_mcp
        self.transport = transport
        self.trace_file = None
        self.info_tool_name = info_tool_name
        self.enabled_operations = enabled_operations
        self.disabled_operations = disabled_operations
        
        # Set up MCP trace logging if enabled
        if self.trace_mcp:
            self._setup_trace_logging()
            
        # Set up hint manager
        self.hint_manager = HintManager(verbose=self.verbose)
        
        # Load hints from file
        self.hint_manager.load_from_file(hints_file)
        
        # Set CLI hint if provided
        if hint:
            self.hint_manager.set_cli_hint(hint)
            
        # Create descriptive server name that includes service info
        parsed_url = urlparse(service_url)
        service_host = parsed_url.hostname or "unknown"
        service_path = parsed_url.path.strip('/').split('/')[-1] if parsed_url.path else "odata"
        
        # If mcp_name is the default, make it more descriptive
        if mcp_name == "odata-mcp":
            descriptive_name = f"OData MCP - {service_host}/{service_path}"
        else:
            descriptive_name = mcp_name
            
        self.mcp = FastMCP(name=descriptive_name)
        self.registered_entity_tools = {}
        self.registered_function_tools = []
        self.all_registered_tools = {}  # Track all tools for trace functionality
        self.use_postfix = use_postfix
        
        # Initialize name shortener
        self.name_shortener = NameShortener(aggressive=tool_shrink)
        
        # Generate service identifier from service URL (after setting tool_shrink)
        service_id = self._generate_service_identifier(service_url)
        
        if use_postfix:
            self.tool_prefix = ""
            if tool_postfix:
                self.tool_postfix = tool_postfix
            else:
                # Apply shrinking to default postfix if enabled
                if tool_shrink:
                    # Use name shortener for service name
                    short_service = self.name_shortener.shorten_service_name(service_id, max_length=4)
                    self.tool_postfix = f"_{short_service}"
                else:
                    self.tool_postfix = f"_for_{service_id}"
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
                max_response_items=self.max_items,
                pagination_hints=self.pagination_hints,
                legacy_dates=self.legacy_dates,
                verbose_errors=self.verbose_errors,
                response_metadata=self.response_metadata,
                max_response_size=self.max_response_size
            )
            self._log_verbose("OData Client Initialized.")

            self._log_verbose("Registering MCP Tools...")
            if self.allowed_entities:
                self._log_verbose(f"Entity filter active - only generating tools for: {', '.join(self.allowed_entities)}")
            if self.read_only:
                self._log_verbose("Read-only mode active - hiding all modifying operations (create, update, delete, and function imports)")
            elif self.read_only_but_functions:
                self._log_verbose("Read-only-but-functions mode active - hiding create, update, and delete operations but allowing function imports")
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
            print(f"[{timestamp} Bridge VERBOSE] {message}", file=sys.stderr)
    
    def _setup_trace_logging(self):
        """Set up MCP trace logging to a file."""
        try:
            # Determine trace file location based on platform
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if platform.system() == 'Windows':
                trace_dir = tempfile.gettempdir()
            else:
                trace_dir = '/tmp'
            
            trace_filename = f"mcp_trace_{timestamp}.log"
            trace_path = f"{trace_dir}/{trace_filename}"
            
            self.trace_file = open(trace_path, 'w')
            self._log_verbose(f"MCP trace logging enabled - writing to: {trace_path}")
            
            # Write initial header
            self.trace_file.write(f"=== MCP Trace Log Started at {datetime.now().isoformat()} ===\n")
            self.trace_file.write(f"Service URL: {self.service_url}\n")
            self.trace_file.write(f"Platform: {platform.system()} {platform.release()}\n")
            self.trace_file.write("===\n\n")
            self.trace_file.flush()
        except Exception as e:
            print(f"WARNING: Failed to set up MCP trace logging: {e}", file=sys.stderr)
            self.trace_mcp = False
    
    def _log_mcp_message(self, direction: str, message: Any):
        """Log an MCP message to the trace file."""
        if not self.trace_mcp or not self.trace_file:
            return
            
        try:
            timestamp = datetime.now().isoformat()
            self.trace_file.write(f"[{timestamp}] {direction}:\n")
            if isinstance(message, (dict, list)):
                self.trace_file.write(json.dumps(message, indent=2, default=str))
            else:
                self.trace_file.write(str(message))
            self.trace_file.write("\n\n")
            self.trace_file.flush()
        except Exception as e:
            # Don't let trace logging failures break the main functionality
            if self.verbose:
                print(f"WARNING: Failed to write to MCP trace log: {e}", file=sys.stderr)
    
    def _matches_entity_filter(self, entity_name: str, patterns: List[str]) -> bool:
        """Check if an entity name matches any of the provided patterns (supports wildcards)."""
        return self._matches_filter_patterns(entity_name, patterns)
    
    def _matches_function_filter(self, function_name: str, patterns: List[str]) -> bool:
        """Check if a function name matches any of the provided patterns (supports wildcards)."""
        return self._matches_filter_patterns(function_name, patterns)
    
    def _matches_filter_patterns(self, name: str, patterns: List[str]) -> bool:
        """Generic method to check if a name matches any of the provided patterns (supports wildcards)."""
        for pattern in patterns:
            if '*' in pattern:
                # Use fnmatch for wildcard matching
                if fnmatch.fnmatch(name, pattern):
                    return True
            else:
                # Exact match
                if name == pattern:
                    return True
        return False
    
    def _is_operation_allowed(self, operation_type: str) -> bool:
        """Check if an operation type is allowed based on enable/disable filters.
        
        Operation types:
        - C: Create
        - S: Search  
        - F: Filter
        - G: Get
        - U: Update
        - D: Delete
        - A: Actions/Function imports
        """
        # If enabled operations are specified, only those are allowed
        if self.enabled_operations is not None:
            return operation_type in self.enabled_operations
            
        # If disabled operations are specified, all except those are allowed
        if self.disabled_operations is not None:
            return operation_type not in self.disabled_operations
            
        # If neither is specified, all operations are allowed
        return True
    
    def _function_relates_to_allowed_entities(self, func_name: str, func_import: 'FunctionImport') -> bool:
        """Check if a function relates to entities that are in the allowed entities list."""
        # Extract entity types from function name patterns
        # This is heuristic-based - we look for common patterns in function names
        entity_hints = []
        
        # Common patterns: ACTIVATE_CLASS, UNIT_TEST_PROGRAM, etc.
        func_upper = func_name.upper()
        
        # Look for entity names in the function name
        for entity_pattern in self.allowed_entities:
            entity_base = entity_pattern.rstrip('*').upper()
            if entity_base in func_upper:
                entity_hints.append(entity_base)
        
        # Also check function parameters for entity-related hints
        for param in func_import.parameters:
            param_name = param.name.upper() if hasattr(param, 'name') else ''
            # Check if parameter names match allowed entities
            for entity_pattern in self.allowed_entities:
                entity_base = entity_pattern.rstrip('*').upper()
                if entity_base in param_name:
                    entity_hints.append(entity_base)
        
        # If we found any entity hints, the function relates to allowed entities
        if entity_hints:
            return True
        
        # If no specific entity hints found, allow the function by default
        # (this avoids being too restrictive for generic functions)
        return True
    
    def _generate_service_identifier(self, service_url: str) -> str:
        """Generate a compact service identifier from the service URL."""
        parsed = urlparse(service_url)
        
        # Pattern 1: SAP OData services like /sap/opu/odata/sap/ZODD_000_SRV or BPCM_ADDRESS_SCREENING_HITS_SRV
        # Use shorter version: ZODD_000_SRV -> Z000 (first letter + numbers)
        match = re.search(r'/([A-Z][A-Z0-9_]*_SRV)', service_url, re.IGNORECASE)
        if match:
            svc_name = match.group(1)
            # For tool_shrink mode, return full name to extract longest word later
            if hasattr(self, 'tool_shrink') and self.tool_shrink:
                return svc_name
            # Extract compact form: take first char + first numbers found
            compact = re.search(r'^([A-Z])[A-Z]*_?(\d+)', svc_name)
            if compact:
                return f"{compact.group(1)}{compact.group(2)}"
            return svc_name[:8]  # Max 8 chars
        
        # Pattern 2: .svc endpoints like /MyService.svc -> MySvc
        match = re.search(r'/([A-Za-z][A-Za-z0-9_]+)\.svc', service_url)
        if match:
            name = match.group(1)
            return f"{name[:5]}Svc" if len(name) > 5 else f"{name}Svc"
        
        # Pattern 3: Generic service name from path like /odata/TestService -> Test
        match = re.search(r'/odata/([A-Za-z][A-Za-z0-9_]+)', service_url)
        if match:
            return match.group(1)[:8]
        
        # Pattern 4: Host-based like service.example.com -> svc_ex
        if parsed.hostname:
            parts = parsed.hostname.split('.')
            if len(parts) >= 2 and parts[0] != 'localhost':
                return f"{parts[0][:3]}_{parts[1][:2]}"
        
        # Pattern 5: Extract last meaningful path segment  
        path_segments = [p for p in parsed.path.split('/') if p and p not in ['api', 'odata', 'sap', 'opu']]
        if path_segments:
            last_segment = path_segments[-1]
            clean_segment = re.sub(r'[^a-zA-Z0-9_]', '_', last_segment)
            clean_segment = re.sub(r'_+', '_', clean_segment).strip('_')
            if len(clean_segment) > 1:
                return clean_segment[:8]
        
        # Ultimate fallback
        return 'od'
    
    def _apply_tool_shrink(self, base_name: str) -> str:
        """Apply tool name shortening rules."""
        parts = base_name.split('_', 1)
        if len(parts) != 2:
            return base_name
        
        operation, entity_name = parts
        
        # Shorten operation prefixes
        operation_map = {
            'create': 'create',
            'get': 'get',
            'update': 'upd',
            'delete': 'del',
            'search': 'search',
            'filter': 'filter',
            'count':  'count',
            'invoke': 'call'
        }
        
        short_op = operation_map.get(operation, operation[:4])
        
        # Use the new name shortener for entity names
        shortened_entity = self.name_shortener.shorten_entity_name(entity_name)
        new_base = f"{short_op}_{shortened_entity}"
        
        return new_base
    
    def _make_tool_name(self, base_name: str) -> str:
        """Generate a tool name with appropriate prefix or postfix, ensuring max 64 chars."""
        # Check if we need to apply shrinking
        full_name_test = f"{self.tool_prefix}{base_name}{self.tool_postfix}"
        
        # Auto-shrink if name is too long (even without --tool-shrink flag)
        if self.tool_shrink or self.name_shortener.should_auto_shrink(full_name_test, threshold=60):
            base_name = self._apply_tool_shrink(base_name)
        
        full_name = f"{self.tool_prefix}{base_name}{self.tool_postfix}"
        
        # Final safety check - should rarely be needed with new algorithm
        if len(full_name) > 64:
            # Emergency truncation
            max_base = 64 - len(self.tool_prefix) - len(self.tool_postfix)
            if max_base > 0:
                parts = base_name.split('_', 1)
                if len(parts) == 2:
                    op, entity = parts
                    remaining = max_base - len(op) - 1
                    base_name = f"{op}_{entity[:remaining]}"
                else:
                    base_name = base_name[:max_base]
            full_name = f"{self.tool_prefix}{base_name}{self.tool_postfix}"
            
        return full_name

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
            safe_name = re.sub(r'\W|^(?=\d)', '_', name)  # Replace non-alphanumeric, starting digits
            if safe_name != name:
                print(f"Warning: Parameter name '{name}' mapped to '{safe_name}' for tool '{tool_name}'", file=sys.stderr)
                name = safe_name  # Use the safe name

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
            "print": print,  # Allow printing errors within execed code
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
            # Track the tool for trace functionality
            self.all_registered_tools[tool_name] = tool_func
            self._log_verbose(f"Registered tool: {tool_name}")
            return tool_name
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Failed to create or register tool {tool_name}: {e}", file=sys.stderr)
            if self.verbose:
                traceback.print_exc(file=sys.stderr)  # Show traceback if verbose
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

        expand = kwargs.get('expand')  # Support expand parameter if passed
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
            'type_hint': prop.get_python_type_hint().replace('Optional[','').replace(']',''),  # Keys shouldn't be optional in signature
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
            # Check if this entity matches any filter pattern (if specified)
            if self.allowed_entities and not self._matches_entity_filter(es_name, self.allowed_entities):
                self._log_verbose(f"Skipping EntitySet '{es_name}' - doesn't match any entity filter pattern")
                continue
                
            entity_type = self.metadata.entity_types.get(entity_set.entity_type)
            if not entity_type:
                self._log_verbose(f"Warning: Skipping tools for EntitySet '{es_name}' because EntityType '{entity_set.entity_type}' was not found or defined.")
                continue

            self.registered_entity_tools[es_name] = []
            tool_name = None  # Reset for each tool type

            # --- List / Filter Tool ---
            if self._is_operation_allowed('F'):
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
            if self._is_operation_allowed('F'):
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

            # --- Search Tool (only if searchable) ---
            if entity_set.searchable and self._is_operation_allowed('S'):
                try:
                    tool_name = self._make_tool_name(f"search_{es_name}")
                    params = [
                        {'name': 'search_term', 'type_hint': 'str', 'required': True, 'description': "Text term(s) to search for"},
                        {'name': 'top', 'type_hint': 'Optional[int]', 'required': False, 'description': "Maximum number of entities"},
                        {'name': 'skip', 'type_hint': 'Optional[int]', 'required': False, 'description': "Number of entities to skip"}
                    ]
                    base_desc = f"Performs a free-text search within the '{es_name}' set."
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
            else:
                self._log_verbose(f"Skipping search tool for '{es_name}' - entity set is not searchable")

            # --- Get Tool ---
            key_props = entity_type.get_key_properties()
            if key_props and self._is_operation_allowed('G'):
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
            # Skip create/update/delete tools in read-only modes
            if entity_set.creatable and not self.read_only and not self.read_only_but_functions and self._is_operation_allowed('C'):
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

            if entity_set.updatable and key_props and not self.read_only and not self.read_only_but_functions and self._is_operation_allowed('U'):  # Need keys to update
                try:
                    tool_name = self._make_tool_name(f"update_{es_name}")
                    # Params are keys (required) + non-keys (optional)
                    key_params = self._get_param_defs_for_keys(key_props)
                    data_params = self._get_param_defs([p for p in entity_type.properties if not p.is_key], required_override=False)  # All data params optional for MERGE/PATCH
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

            if entity_set.deletable and key_props and not self.read_only and not self.read_only_but_functions and self._is_operation_allowed('D'):  # Need keys to delete
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
        # Skip function tools if in full read-only mode
        if not self.read_only and self._is_operation_allowed('A'):
            for func_name, func_import in self.metadata.function_imports.items():
                # Check if this function matches any filter pattern (if specified)
                if self.allowed_functions and not self._matches_function_filter(func_name, self.allowed_functions):
                    self._log_verbose(f"Skipping Function '{func_name}' - doesn't match any function filter pattern")
                    continue
                
                # Check if this function relates to entities that are filtered out
                if self.allowed_entities and not self._function_relates_to_allowed_entities(func_name, func_import):
                    self._log_verbose(f"Skipping Function '{func_name}' - relates to entities not in allowed list")
                    continue
                
                try:
                    # Params based on function import definition
                    params = self._get_param_defs(func_import.parameters)  # Required based on nullability
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
        elif self.verbose:
            if not self.read_only:
                self._log_verbose("Skipping all function imports - operation type 'A' is not allowed")
            else:
                self._log_verbose("Skipping all function imports due to --read-only mode")

        # --- Log Summary (only if verbose) ---
        if self.verbose:
            print("\n--- Registered Tools Summary ---", file=sys.stderr)
            print(f"- Service Info: {self._make_tool_name('odata_service_info')}", file=sys.stderr)
            
            # Sort entity sets if sort_tools is enabled
            entity_items = list(self.registered_entity_tools.items())
            if self.sort_tools:
                entity_items.sort(key=lambda x: x[0])
                
            for es_name, tools in entity_items:
                if tools:
                    # Sort individual tools within each entity set if sort_tools is enabled
                    tool_list = sorted(tools) if self.sort_tools else tools
                    print(f"- Entity Set '{es_name}': {', '.join(tool_list)}", file=sys.stderr)
            
            if self.registered_function_tools:
                # Sort function tools if sort_tools is enabled
                func_tools = sorted(self.registered_function_tools) if self.sort_tools else self.registered_function_tools
                print(f"- Function Imports: {', '.join(func_tools)}", file=sys.stderr)
            print("-------------------------------\n", file=sys.stderr)
    

    def add_service_info_tool(self):
        """Add a tool to provide information about the OData service structure."""
        async def odata_service_info() -> str:
            """RECOMMENDED STARTING POINT: Get comprehensive information about this OData service.
            
            This tool provides essential metadata about the configured OData service, including:
            - Service URL and description
            - Available entity sets and their operations (create, read, update, delete)
            - Entity types with properties and relationships
            - Function imports with parameters
            - Registered MCP tools for each entity/function
            - Implementation hints and known issues (if applicable)
            
            Always call this tool first to understand the service structure before using other tools."""
            # Use previously stored registration info for tools
            registered_entity_tools_summary = {}
            entity_items = list(self.registered_entity_tools.items())
            if self.sort_tools:
                entity_items.sort(key=lambda x: x[0])
            
            for name, tools in entity_items:
                if tools:
                    # Sort tools within each entity if sort_tools is enabled
                    registered_entity_tools_summary[name] = sorted(tools) if self.sort_tools else tools

            entity_set_details = {}
            # Sort entity sets if sort_tools is enabled
            entity_set_items = list(self.metadata.entity_sets.items())
            if self.sort_tools:
                entity_set_items.sort(key=lambda x: x[0])
                
            for name, es in entity_set_items:
                # Attempt to get the related entity type description
                et = self.metadata.entity_types.get(es.entity_type)
                et_desc = et.description if et else None

                entity_set_details[name] = {
                    "entity_type": es.entity_type,
                    "description": es.description or et_desc or "No description",  # Use entity type desc as fallback
                    "creatable": es.creatable,
                    "updatable": es.updatable,
                    "deletable": es.deletable,
                    "searchable": es.searchable,
                }

            entity_type_details = {}
            # Sort entity types if sort_tools is enabled
            entity_type_items = list(self.metadata.entity_types.items())
            if self.sort_tools:
                entity_type_items.sort(key=lambda x: x[0])
                
            for name, et in entity_type_items:
                entity_type_details[name] = {
                    "description": et.description or "No description",
                    "key_properties": et.key_properties,
                    "properties": [  # Convert properties to dicts for JSON
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
            # Sort function imports if sort_tools is enabled
            function_import_items = list(self.metadata.function_imports.items())
            if self.sort_tools:
                function_import_items.sort(key=lambda x: x[0])
                
            for name, fi in function_import_items:
                function_import_details[name] = {
                    "description": fi.description or "No description",
                    "http_method": fi.http_method,
                    "return_type": fi.return_type or "Not specified",
                    "parameters": [  # Convert params to dicts for JSON
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
                "entity_types": entity_type_details,  # Added entity type details
                "function_imports": function_import_details,  # Added function details
                "registered_entity_tools_summary": registered_entity_tools_summary,  # Summary of tools per entity set
                "registered_function_tools": sorted(self.registered_function_tools) if self.sort_tools else self.registered_function_tools
            }
            
            # Get hints from hint manager
            implementation_hints = self.hint_manager.get_hints(self.metadata.service_url)
            if implementation_hints:
                info["implementation_hints"] = implementation_hints
            try:
                # Use default=str for complex objects that might not be serializable otherwise
                return json.dumps(info, indent=2, default=str)
            except TypeError as e:
                # Error, print regardless of verbosity
                print(f"ERROR: Error serializing service info: {e}", file=sys.stderr)
                return json.dumps({"error": "Could not serialize service metadata."})

        try:
            # Use custom name if provided, otherwise use default
            if self.info_tool_name:
                tool_name = self._make_tool_name(self.info_tool_name)
            else:
                tool_name = self._make_tool_name("odata_service_info")
            
            self.mcp.add_tool(Tool.from_function(odata_service_info), name=tool_name)
            # Track the tool for trace functionality
            self.all_registered_tools[tool_name] = odata_service_info
            self._log_verbose(f"Registered tool: {tool_name}")
            
            # Also register with 'readme' alias if not using custom name
            if not self.info_tool_name:
                readme_name = self._make_tool_name("readme")
                self.mcp.add_tool(Tool.from_function(odata_service_info), name=readme_name)
                self.all_registered_tools[readme_name] = odata_service_info
                self._log_verbose(f"Registered tool alias: {readme_name}")
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Error registering odata_service_info tool: {e}", file=sys.stderr)

    def _cleanup(self):
        """Clean up resources like trace file."""
        if self.trace_file:
            try:
                self.trace_file.write(f"\n=== MCP Trace Log Ended at {datetime.now().isoformat()} ===\n")
                self.trace_file.close()
                self._log_verbose("MCP trace log file closed")
            except Exception:
                pass  # Ignore cleanup errors
    
    def run(self):
        """Run the MCP server."""
        try:
            # Log startup message only if verbose
            self._log_verbose(f"Starting OData MCP bridge for service: {self.service_url}")
            self._log_verbose(f"MCP Server Name: {self.mcp.name}")
            if not self.metadata.entity_sets:
                # Warning, print only if verbose
                self._log_verbose("Warning: No entity sets were successfully processed. Tools may be limited.")

            # If transport is provided, use it; otherwise use FastMCP's default
            if self.transport:
                # Set up message handler
                self.transport.handler = self._handle_transport_message
                # Run transport asynchronously
                asyncio.run(self._run_with_transport())
            else:
                # The FastMCP server run method handles the main loop
                self.mcp.run()
        finally:
            self._cleanup()
    
    async def _run_with_transport(self):
        """Run the MCP server with custom transport."""
        try:
            await self.transport.start()
            # Keep running until stopped
            while self.transport.is_running:
                await asyncio.sleep(1)
        finally:
            await self.transport.stop()
    
    async def _handle_transport_message(self, message: TransportMessage) -> Optional[TransportMessage]:
        """Handle incoming transport messages."""
        # Convert transport message to MCP request/response
        # This is a simplified handler - in production you'd want full JSON-RPC handling
        try:
            if message.method == "initialize":
                return TransportMessage(
                    id=message.id,
                    result={
                        "protocolVersion": "0.1.0",
                        "capabilities": {
                            "tools": {"listChanged": True}
                        },
                        "serverInfo": {
                            "name": self.mcp.name,
                            "version": "1.3.0",
                            "description": f"OData MCP Bridge for {self.service_url}"
                        }
                    }
                )
            elif message.method == "initialized":
                # No response for notification
                return None
            elif message.method == "tools/list":
                tools = []
                for tool_name in self.all_registered_tools:
                    # Get tool info from FastMCP
                    tools.append({
                        "name": tool_name,
                        "description": "OData operation",
                        "inputSchema": {"type": "object"}
                    })
                return TransportMessage(
                    id=message.id,
                    result={"tools": tools}
                )
            elif message.method == "tools/call":
                # This would need integration with FastMCP's tool execution
                tool_name = message.params.get("name")
                args = message.params.get("arguments", {})
                # For now, return a placeholder
                return TransportMessage(
                    id=message.id,
                    result={
                        "content": [{
                            "type": "text",
                            "text": f"Tool {tool_name} called with args: {args}"
                        }]
                    }
                )
            else:
                return TransportMessage(
                    id=message.id,
                    error={
                        "code": -32601,
                        "message": "Method not found"
                    }
                )
        except Exception as e:
            return TransportMessage(
                id=message.id if message else None,
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            )