# OData MCP Tool Naming

## Problem Solved

Previously, all OData MCP servers used identical tool names like `odata_service_info`, `filter_Products`, etc. This caused confusion when multiple OData services were configured, as Claude couldn't distinguish which service a tool belonged to.

## Solution: Service-Specific Tool Names

Tools are now named with service-specific identifiers to ensure uniqueness across multiple OData MCP servers.

## Naming Patterns

### Default: Postfix Pattern (Recommended)
```
{base_tool_name}_for_{service_identifier}
```

**Examples:**
- `odata_service_info_for_northwind_v2`
- `filter_Products_for_northwind_v2`
- `count_Categories_for_northwind_v2`
- `odata_service_info_for_zmcp_002`
- `filter_ZLLM_00_NODESet_for_zmcp_002`

### Alternative: Prefix Pattern
```
{service_identifier}_{base_tool_name}
```

**Examples:**
- `northwind_v2_odata_service_info`
- `northwind_v2_filter_Products`
- `zmcp_002_filter_ZLLM_00_NODESet`

## Service Identifier Generation

The system automatically generates service identifiers from OData service URLs:

| Service URL | Service ID | Tool Example |
|-------------|------------|--------------|
| `https://services.odata.org/V2/Northwind/Northwind.svc/` | `northwind_v2` | `odata_service_info_for_northwind_v2` |
| `https://services.odata.org/V4/Northwind/Northwind.svc/` | `northwind_v4` | `odata_service_info_for_northwind_v4` |
| `https://services.odata.org/TripPinRESTierService/` | `trippin` | `odata_service_info_for_trippin` |
| `https://services.odata.org/V2/OData/OData.svc/` | `demo_v2` | `odata_service_info_for_demo_v2` |
| `http://vhcala4hci:50000/sap/opu/odata/sap/ZMCP_002_SRV/` | `zmcp_002` | `odata_service_info_for_zmcp_002` |

## Configuration Options

### Command Line Arguments

```bash
# Default: Use postfix pattern
python odata_mcp.py --service <url>

# Use prefix pattern instead
python odata_mcp.py --service <url> --no-postfix

# Custom postfix
python odata_mcp.py --service <url> --tool-postfix "_custom_suffix"

# Custom prefix (with --no-postfix)
python odata_mcp.py --service <url> --tool-prefix "custom_prefix_" --no-postfix
```

### Programmatic Configuration

```python
# Default postfix pattern
bridge = ODataMCPBridge(service_url, auth)

# Custom postfix
bridge = ODataMCPBridge(service_url, auth, tool_postfix="_for_my_service")

# Prefix pattern
bridge = ODataMCPBridge(service_url, auth, use_postfix=False)

# Custom prefix
bridge = ODataMCPBridge(service_url, auth, tool_prefix="myservice_", use_postfix=False)
```

## MCP Server Configuration

Update your MCP configuration to use unique service names:

```json
{
  "mcpServers": {
    "odata-sap": {
      "command": "/path/to/python",
      "args": [
        "/path/to/odata_mcp.py",
        "--service", "http://sap-server/odata/ZMCP_002_SRV/",
        "--user", "username",
        "--pass", "password"
      ]
    },
    "odata-northwind-v2": {
      "command": "/path/to/python", 
      "args": [
        "/path/to/odata_mcp.py",
        "--service", "https://services.odata.org/V2/Northwind/Northwind.svc/"
      ]
    },
    "odata-demo": {
      "command": "/path/to/python",
      "args": [
        "/path/to/odata_mcp.py", 
        "--service", "https://services.odata.org/V2/OData/OData.svc/"
      ]
    }
  }
}
```

## Benefits

1. **Clear Service Identification**: Tool names immediately show which OData service they belong to
2. **No Naming Conflicts**: Multiple OData services can coexist without tool name collisions  
3. **Better Organization**: Related tools are grouped by service identifier
4. **Improved Debugging**: Easier to identify which service is being called
5. **Backward Compatibility**: Can disable with custom configuration if needed

## Complete Tool Set Example

For a Northwind v2 service, the complete tool set would be:

```
odata_service_info_for_northwind_v2
filter_Products_for_northwind_v2
count_Products_for_northwind_v2
search_Products_for_northwind_v2
get_Products_for_northwind_v2
create_Products_for_northwind_v2
update_Products_for_northwind_v2
delete_Products_for_northwind_v2
filter_Categories_for_northwind_v2
count_Categories_for_northwind_v2
get_Categories_for_northwind_v2
...
```

This makes it crystal clear that these tools operate on the Northwind v2 service specifically.