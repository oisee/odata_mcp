"""
OData v2 client for making API requests with CSRF token handling and response optimization.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests

from .constants import ODATA_PRIMITIVE_TYPES
from .models import EntityType, ODataMetadata
from .guid_handler import ODataGUIDHandler


class ODataClient:
    """Client for interacting with an OData v2 service."""

    def __init__(self, metadata: ODataMetadata, auth: Optional[Tuple[str, str]] = None, 
                 verbose: bool = False, optimize_guids: bool = True,
                 max_response_items: int = 1000):
        self.metadata = metadata
        self.auth = auth
        self.verbose = verbose
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
            'Content-Type': 'application/json'  # For POST/PUT/MERGE
        })
        # SAP specific header for CSRF token handling if needed
        self.csrf_token = None
        
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
            # Use service root URL for CSRF token fetch
            service_root = self.metadata.service_url.rstrip('/')
            
            # Clear any existing CSRF token
            self.csrf_token = None
            
            self._log_verbose(f"Attempting CSRF token fetch from service root: {service_root}")
            
            # Create headers for CSRF fetch - minimal set as per SAP standard
            csrf_headers = {
                'X-CSRF-Token': 'Fetch'
            }
            
            # Use GET request to service root to fetch CSRF token
            # Let session handle auth and existing cookies
            response = self.session.get(service_root, headers=csrf_headers, timeout=30)
            
            # Check for CSRF token in response headers (case-insensitive)
            csrf_token = None
            for header_name, header_value in response.headers.items():
                if header_name.lower() == 'x-csrf-token':
                    csrf_token = header_value
                    break
            
            if csrf_token and csrf_token.lower() not in ['fetch', 'required']:
                self.csrf_token = csrf_token
                self._log_verbose(f"CSRF token fetched successfully: {csrf_token[:20]}...")
                return True
            else:
                self._log_verbose(f"No valid CSRF token from {service_root} (got: '{csrf_token}')")
                return False
            
        except requests.exceptions.RequestException as req_e:
            self._log_verbose(f"Failed to fetch CSRF token: {req_e}")
            return False
        except Exception as e:
            self._log_verbose(f"Unexpected error fetching CSRF token: {e}")
            return False

    def _make_request(self, method: str, url: str, requires_csrf: bool = False, **kwargs) -> requests.Response:
        """Internal helper to make requests, handling CSRF."""
        modifying_methods = ['POST', 'PUT', 'MERGE', 'PATCH', 'DELETE']
        is_modifying = method.upper() in modifying_methods

        # For modifying operations that require CSRF, always fetch a fresh token
        if is_modifying and requires_csrf:
            if not self._fetch_csrf_token():
                self._log_verbose("Failed to fetch CSRF token, proceeding without it")

        # Prepare headers
        request_headers = self.session.headers.copy()
        if 'headers' in kwargs:
            request_headers.update(kwargs.pop('headers'))

        # Add CSRF token if we have one
        if is_modifying and requires_csrf and self.csrf_token:
            request_headers['X-CSRF-Token'] = self.csrf_token
            self._log_verbose(f"Adding CSRF token to request: {self.csrf_token[:20]}...")

        kwargs['headers'] = request_headers

        # Make the request
        try:
            response = self.session.request(method, url, **kwargs)
        except Exception as e:
            self._log_verbose(f"Request failed with exception: {e}")
            raise

        # Handle CSRF token issues
        csrf_failed = (
            response.status_code == 403 and
            is_modifying and requires_csrf and
            ('CSRF token validation failed' in response.text or
             'csrf' in response.text.lower() or
             response.headers.get('x-csrf-token', '').lower() == 'required')
        )

        if csrf_failed and not hasattr(response, '_csrf_retry_attempted'):
            self._log_verbose("CSRF token validation failed, attempting to refetch...")
            # Clear the invalid token
            self.csrf_token = None
            if self._fetch_csrf_token():
                # Mark this response to avoid infinite retry
                response._csrf_retry_attempted = True
                request_headers['X-CSRF-Token'] = self.csrf_token
                kwargs['headers'] = request_headers
                
                self._log_verbose("Retrying request with new CSRF token...")
                response = self.session.request(method, url, **kwargs)
            else:
                error_detail = f"CSRF token required but refetch failed. Status: {response.status_code}"
                if response.text:
                    error_detail += f". Response: {response.text[:500]}"
                raise requests.exceptions.RequestException(error_detail, response=response)

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
            else:  # Assume numeric or boolean which don't need quotes
                # Format boolean as true/false lowercase
                if py_type == bool:
                    return f"({str(key_value).lower()})"
                return f"({key_value})"
        else:  # Composite key
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
            # First check if response has content
            if not response.content:
                return f"Empty response with status {response.status_code}"
            
            error_data = response.json()
            
            # Common OData v2 error structures
            if 'error' in error_data:
                error_obj = error_data['error']
                
                # Check for message field
                if 'message' in error_obj:
                    msg_obj = error_obj['message']
                    if isinstance(msg_obj, dict):
                        # Handle nested message objects
                        if 'value' in msg_obj:
                            return msg_obj['value']
                        elif 'lang' in msg_obj and 'value' in msg_obj:
                            return msg_obj['value']
                        else:
                            # Return the entire message object as JSON
                            return json.dumps(msg_obj)
                    elif isinstance(msg_obj, str):
                        return msg_obj
                
                # Check for code and message at error level
                if 'code' in error_obj and isinstance(error_obj.get('message'), str):
                    return f"{error_obj['code']}: {error_obj['message']}"
                
                # SAP specific inner error structure
                if 'innererror' in error_obj:
                    inner_error = error_obj['innererror']
                    
                    # Check for errordetails array (SAP specific)
                    if 'errordetails' in inner_error and isinstance(inner_error['errordetails'], list):
                        details = []
                        for detail in inner_error['errordetails']:
                            if isinstance(detail, dict):
                                # Prefer message, then code, then severity
                                msg = detail.get('message', detail.get('code', detail.get('severity', '')))
                                if msg:
                                    details.append(str(msg))
                        if details:
                            return "; ".join(details)
                    
                    # Check for application error details
                    if 'application' in inner_error:
                        app_error = inner_error['application']
                        if isinstance(app_error, dict):
                            # Look for various message fields
                            for field in ['message_text', 'message', 'error_text', 'text']:
                                if field in app_error and app_error[field]:
                                    return str(app_error[field])
                    
                    # Direct message in innererror
                    if 'message' in inner_error:
                        return str(inner_error['message'])
                
                # If we still don't have a message, return the whole error object
                return json.dumps(error_obj)
            
            # Check for other common error patterns
            if 'Message' in error_data:  # Capital M
                return str(error_data['Message'])
            
            if 'ExceptionMessage' in error_data:
                return str(error_data['ExceptionMessage'])
            
            # If no standard error structure, return formatted JSON
            return json.dumps(error_data, indent=2)[:1000]  # Limit length

        except json.JSONDecodeError:
            # Not JSON, try to extract meaningful text
            text = response.text.strip()
            if text:
                # Look for common error patterns in text
                if text.startswith('<?xml'):
                    # Try to extract error from XML
                    import re
                    # Look for <message> or <error> tags
                    match = re.search(r'<(?:message|error|Message|Error)>([^<]+)</(?:message|error|Message|Error)>', text)
                    if match:
                        return match.group(1)
                    # Look for message attribute
                    match = re.search(r'message=["\']([^"\']+)["\']', text)
                    if match:
                        return match.group(1)
                    return "XML error response (details in response body)"
                else:
                    # Return first 500 chars of text
                    return text[:500]
            else:
                return f"Empty response with status {response.status_code}"
                
        except Exception as e:
            # Catch any other parsing errors
            self._log_verbose(f"Warning: Exception while parsing OData error response: {e}")
            # Try to at least return status and some content
            try:
                return f"Error parsing response (status {response.status_code}): {response.text[:200]}"
            except:
                return f"Error parsing response (status {response.status_code})"

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
                if self.verbose:  # Only warn if verbose
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
                    suggested_next['$skip'] = next_skip  # Override skip
                    # Ensure $skiptoken is removed if $skip is present
                    if '$skiptoken' in suggested_next: del suggested_next['$skiptoken']

                elif '$skiptoken' in query_params:
                    next_token = query_params['$skiptoken'][0]
                    pagination['next_skiptoken'] = next_token
                    suggested_next['$skiptoken'] = next_token  # Add skiptoken
                    # Ensure $skip is removed if $skiptoken is present
                    if '$skip' in suggested_next: del suggested_next['$skip']

                # Try to convert $top to int if present
                if '$top' in suggested_next:
                    try: suggested_next['$top'] = int(suggested_next['$top'])
                    except (ValueError, TypeError): del suggested_next['$top']  # Remove if invalid

                pagination['suggested_next_call'] = suggested_next

            except Exception as e:
                if self.verbose:  # Only warn if verbose
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
                except (ValueError, TypeError): pass  # Keep num_results if $top is invalid

            if total_count > current_skip + num_results:
                pagination['has_more'] = True
                next_skip_val = current_skip + (current_top if current_top > 0 and num_results >= current_top else num_results)  # Calculate next skip
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
                elif results is None:  # Handle null result explicitly
                    results = []
                else:  # Likely a single result (count <= 1), wrap in list for consistency
                    results = [results]

            final_response = {"results": results}
            if pagination:
                final_response["pagination"] = pagination

            return final_response

        except requests.exceptions.RequestException as e:
            # Error, print regardless of verbosity
            if e.response:
                error_details = self._parse_odata_error(e.response)
                status_code = e.response.status_code
            else:
                # No response object - connection error, timeout, etc.
                error_details = str(e)
                status_code = 'N/A'
            print(f"ERROR: Error listing/filtering {entity_set_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData request failed ({status_code}): {error_details}") from e
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
            elif response.status_code in [404, 400, 405]:  # Not Found, Bad Request, Method Not Allowed likely means /$count unsupported
                raise ValueError(f"/$count endpoint not supported or filter invalid (Status: {response.status_code}).")
            else:
                # Raise error for other unexpected statuses
                response.raise_for_status()

        except (requests.exceptions.RequestException, ValueError, TypeError) as e:
            # Fallback for services that don't support /$count but support $inlinecount
            self._log_verbose(f"Warning: /$count failed or not supported for {entity_set_name} ({e}). Falling back to $inlinecount.")
            try:
                # Request 0 items but with inline count
                list_params = {'$top': 0}  # $inlinecount=allpages added by list_or_filter_entities
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
        return -1  # Should not be reached

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
            if e.response:
                error_details = self._parse_odata_error(e.response)
                status_code = e.response.status_code
            else:
                # No response object - connection error, timeout, etc.
                error_details = str(e)
                status_code = 'N/A'
            print(f"ERROR: Error getting {entity_set_name} with key {key_values}: {e}", file=sys.stderr)
            raise ValueError(f"OData request failed ({status_code}): {error_details}") from e
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
        params = {}  # No query params for POST

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
                return self._parse_odata_response(response)  # Will raise error if status is 4xx/5xx
        except requests.exceptions.RequestException as e:
            # Error, print regardless of verbosity
            if e.response:
                error_details = self._parse_odata_error(e.response)
                status_code = e.response.status_code
            else:
                # No response object - connection error, timeout, etc.
                error_details = str(e)
                status_code = 'N/A'
            print(f"ERROR: Error creating entity in {entity_set_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData POST request failed ({status_code}): {error_details}") from e
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
        params = {}  # No query params for MERGE/PUT/PATCH

        try:
            # Prefer MERGE for partial updates (standard in OData v2/v3)
            self._log_verbose(f"Requesting: MERGE {url} with data {entity_data}")
            response = await asyncio.to_thread(
                self._make_request, 'MERGE', url, params=params, json=entity_data, requires_csrf=True
            )
            # Some servers might expect PATCH or PUT
            if response.status_code == 405:  # Method Not Allowed, try PUT
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
            if e.response:
                error_details = self._parse_odata_error(e.response)
                status_code = e.response.status_code
            else:
                # No response object - connection error, timeout, etc.
                error_details = str(e)
                status_code = 'N/A'
            print(f"ERROR: Error updating entity in {entity_set_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData update request failed ({status_code}): {error_details}") from e
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
            if e.response:
                error_details = self._parse_odata_error(e.response)
                status_code = e.response.status_code
            else:
                # No response object - connection error, timeout, etc.
                error_details = str(e)
                status_code = 'N/A'
            print(f"ERROR: Error deleting entity from {entity_set_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData DELETE request failed ({status_code}): {error_details}") from e
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
        query['$format'] = ['json']  # Ensure format is in query

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
                current_query.update({k: v[0] for k, v in query.items()})  # Flatten format param

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
            if e.response:
                error_details = self._parse_odata_error(e.response)
                status_code = e.response.status_code
            else:
                # No response object - connection error, timeout, etc.
                error_details = str(e)
                status_code = 'N/A'
            print(f"ERROR: Error invoking function {function_name}: {e}", file=sys.stderr)
            raise ValueError(f"OData function request failed ({status_code}): {error_details}") from e
        except Exception as e:
            # Error, print regardless of verbosity
            print(f"ERROR: Unexpected error during function {function_name}: {e}", file=sys.stderr)
            raise