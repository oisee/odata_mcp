"""
OData to MCP bridge that dynamically generates MCP tools from OData metadata.
"""

import asyncio
import json
import re
import sys
import signal
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

try:
    from fastmcp import FastMCP
    import mcp.types as types
except ImportError:
    print("ERROR: Could not import FastMCP. Make sure it's installed and accessible.", file=sys.stderr)
    print("You might need to adjust the import statement based on your project structure.", file=sys.stderr)
    sys.exit(1)

from .models import EntityProperty, EntityType, FunctionImport
from .metadata_parser import MetadataParser
from .client import ODataClient


class ODataMCPBridge:
    """Bridge between OData and MCP, creating tools from OData metadata."""

    def __init__(self, service_url: str, auth: Optional[Union[Tuple[str, str], Dict[str, str]]] = None, mcp_name: str = "odata-mcp", verbose: bool = False, 
                 tool_prefix: Optional[str] = None, tool_postfix: Optional[str] = None, use_postfix: bool = True, tool_shrink: bool = False):
        self.service_url = service_url
        self.auth = auth
        self.verbose = verbose
        self.tool_shrink = tool_shrink
        self.mcp = FastMCP(name=mcp_name, timeout=120)  # Increased timeout
        self.registered_entity_tools = {}
        self.registered_function_tools = []
        self.use_postfix = use_postfix
        
        # Generate service identifier from service URL (after setting tool_shrink)
        service_id = self._generate_service_identifier(service_url)
        
        if use_postfix:
            self.tool_prefix = ""
            if tool_postfix:
                self.tool_postfix = tool_postfix
            else:
                # Apply shrinking to default postfix if enabled
                if tool_shrink:
                    # For shrink mode: use 4 letters from longest word in service name
                    service_parts = service_id.split('_')
                    longest_word = max(service_parts, key=len) if service_parts else service_id
                    self.tool_postfix = f"_{longest_word[:4].lower()}" if len(longest_word) > 4 else f"_{longest_word.lower()}"
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
            print(f"[{timestamp} Bridge VERBOSE] {message}", file=sys.stderr)
    
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
    
    def _shrink_entity_name(self, entity_name: str) -> str:
        """Shrink entity name progressively to fit within constraints."""
        # Remove common prefixes/namespaces
        parts = entity_name.split('_')
        
        # Filter out common SAP/OData prefixes
        filtered_parts = []
        skip_prefixes = {'BPCM', 'CV', 'ASH', 'FRA', 'IV', 'C', 'I', 'E', 'Z'}
        
        for part in parts:
            if part.upper() not in skip_prefixes and len(part) > 1:
                filtered_parts.append(part)
        
        if filtered_parts:
            # Try different strategies
            # 1. Use the longest meaningful word
            longest = max(filtered_parts, key=len)
            
            # Remove common suffixes
            for suffix in ['Type', 'Set', 'Collection', 'Entity']:
                if longest.endswith(suffix) and len(longest) > len(suffix) + 3:
                    longest = longest[:-len(suffix)]
                    break
            
            return longest
        
        # Fallback: use original name truncated
        return entity_name[:10]
    
    def _apply_tool_shrink(self, base_name: str) -> str:
        """Apply tool name shortening rules."""
        parts = base_name.split('_', 1)
        if len(parts) != 2:
            return base_name
        
        operation, entity_name = parts
        
        # Shorten operation prefixes
        operation_map = {
            'create': 'crt',
            'get': 'get',
            'update': 'upd',
            'delete': 'del',
            'search': 'srch',
            'filter': 'fltr',
            'count': 'cnt',
            'invoke': 'call'
        }
        
        short_op = operation_map.get(operation, operation[:4])
        
        # Shorten entity name
        shortened_entity = self._shrink_entity_name(entity_name)
        new_base = f"{short_op}_{shortened_entity}"
        
        # Check if we need further shortening
        estimated_length = len(self.tool_prefix) + len(new_base) + len(self.tool_postfix)
        
        if estimated_length > 60:  # Leave some margin
            # Progressive shortening of entity name
            if len(shortened_entity) > 10:
                shortened_entity = shortened_entity[:10]
                new_base = f"{short_op}_{shortened_entity}"
        
        return new_base
    
    def _make_tool_name(self, base_name: str) -> str:
        """Generate a tool name with appropriate prefix or postfix, ensuring max 64 chars."""
        # Apply tool shrinking if enabled
        if self.tool_shrink:
            base_name = self._apply_tool_shrink(base_name)
        
        full_name = f"{self.tool_prefix}{base_name}{self.tool_postfix}"
        
        if len(full_name) <= 64:
            return full_name
            
        # Truncate with compact naming strategy
        max_base = 64 - len(self.tool_prefix) - len(self.tool_postfix)
        if max_base <= 0:
            # Prefix/postfix too long, use minimal naming
            if self.use_postfix:
                return f"{base_name[:60]}_svc"
            else:
                return f"svc_{base_name[:60]}"
        
        # Truncate base name intelligently
        if max_base < len(base_name):
            # Try to preserve operation prefix and entity name core
            parts = base_name.split('_', 1)
            if len(parts) == 2:
                op, entity = parts
                remaining = max_base - len(op) - 1  # -1 for underscore
                if remaining > 8:  # Keep reasonable entity name length
                    truncated_base = f"{op}_{entity[:remaining]}"
                else:
                    truncated_base = base_name[:max_base]
            else:
                truncated_base = base_name[:max_base]
        else:
            truncated_base = base_name
            
        return f"{self.tool_prefix}{truncated_base}{self.tool_postfix}"

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
            entity_type = self.metadata.entity_types.get(entity_set.entity_type)
            if not entity_type:
                self._log_verbose(f"Warning: Skipping tools for EntitySet '{es_name}' because EntityType '{entity_set.entity_type}' was not found or defined.")
                continue

            self.registered_entity_tools[es_name] = []
            tool_name = None  # Reset for each tool type

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

            if entity_set.updatable and key_props:  # Need keys to update
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

            if entity_set.deletable and key_props:  # Need keys to delete
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
                    "description": es.description or et_desc or "No description",  # Use entity type desc as fallback
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
            for name, fi in self.metadata.function_imports.items():
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