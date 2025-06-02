# CRUD Operations with OData MCP Bridge

This guide explains how to enable and use Create, Read, Update, and Delete (CRUD) operations with the OData MCP Bridge, particularly for SAP systems where these operations may be restricted by default.

## Overview

The OData MCP Bridge already includes full CRUD support:
- **Create**: `create_{entity_set}` tools
- **Read**: `filter_{entity_set}`, `get_{entity_set}`, `search_{entity_set}`, `count_{entity_set}` tools
- **Update**: `update_{entity_set}` tools
- **Delete**: `delete_{entity_set}` tools

However, many OData services (especially SAP) mark entity sets as read-only in their metadata, which prevents the registration of create/update/delete tools.

## The Challenge

SAP OData services often include metadata annotations like:
```xml
<EntitySet Name="PROGRAMSet" sap:creatable="false" sap:updatable="false" sap:deletable="false">
```

This causes the MCP bridge to skip registering the CRUD tools for these entity sets.

## Solutions

### Solution 1: Direct Metadata Override (Programmatic)

Use the example script `example_create_program.py` which shows how to override metadata after parsing:

```python
# Parse metadata
parser = MetadataParser(service_url, auth)
metadata = parser.parse()

# Override restrictions
metadata.entity_sets["PROGRAMSet"].creatable = True
metadata.entity_sets["PROGRAMSet"].updatable = True
metadata.entity_sets["PROGRAMSet"].deletable = True

# Create client with modified metadata
client = ODataClient(metadata, auth)
```

### Solution 2: Environment Variable Override (Coming Soon)

Set environment variables to override specific entity sets:
```bash
export ODATA_OVERRIDE_READONLY=true  # Enable all CRUD operations globally
# OR
export ODATA_OVERRIDE_PROGRAMSet_creatable=true
export ODATA_OVERRIDE_PROGRAMSet_deletable=true
```

### Solution 3: Custom MCP Bridge Wrapper

Use the `ODataMCPBridgeWithOverrides` class from `odata_mcp_with_overrides.py`:

```python
from odata_mcp_with_overrides import ODataMCPBridgeWithOverrides

bridge = ODataMCPBridgeWithOverrides(
    service_url=service_url,
    auth=auth,
    override_readonly=True,  # Force all entities to be writable
    entity_overrides={
        "PROGRAMSet": {"creatable": True, "deletable": True},
        "CLASSSet": {"creatable": True, "updatable": True}
    }
)
```

## Example: Creating an ABAP Program

Once CRUD tools are enabled, you can use them via MCP:

### Via MCP Tool Call:
```json
{
  "tool": "create_PROGRAMSet_for_demo_v2",
  "parameters": {
    "Program": "ZVIBE_002_TEST",
    "Title": "Test Program",
    "SourceCode": "REPORT ZVIBE_002_TEST.\nWRITE :/ 'Hello World'.",
    "Package": "$TMP",
    "ProgramType": "1"
  }
}
```

### Via Python Script:
```bash
python example_create_program.py
```

## Important Notes

1. **Authorization**: Even if you override metadata restrictions, the actual OData service must still allow these operations. You may get authorization errors if your user lacks the necessary permissions.

2. **Service Support**: Not all OData services support CRUD operations. Some are truly read-only by design.

3. **Data Validation**: The OData service may enforce additional validation rules not visible in the metadata.

4. **Transaction Handling**: Some operations may require explicit transaction handling or activation steps (e.g., ABAP programs need activation after creation).

## Testing CRUD Operations

1. First, check what operations are available:
   ```bash
   # List available tools
   mcp list-tools
   ```

2. Test create operation:
   ```bash
   # Run the example script
   python example_create_program.py
   ```

3. Verify creation:
   ```bash
   # Use the filter tool to list programs
   mcp call filter_PROGRAMSet_for_demo_v2 --filter "startswith(Program, 'ZVIBE_')"
   ```

## Troubleshooting

1. **"Entity set not configured as creatable"**: The metadata marks the entity as read-only. Use one of the override solutions above.

2. **"403 Forbidden" or "401 Unauthorized"**: Your user lacks permissions. Check with your SAP administrator.

3. **"400 Bad Request"**: The data you're sending doesn't match the service's expectations. Check required fields and data types.

4. **"Method not allowed"**: The OData service doesn't support the HTTP method. This might indicate the service is truly read-only.

## Implementation Details

The create/update/delete implementations in `odata_mcp.py`:

- **Create**: Uses POST to the entity set URL with JSON data
- **Update**: Uses MERGE (preferred) or PUT to the entity URL with key
- **Delete**: Uses DELETE to the entity URL with key

All operations handle CSRF tokens automatically when required by the service.