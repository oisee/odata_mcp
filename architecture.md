# OData to MCP Bridge Architecture

## Overview

This project implements a dynamic bridge between OData v2 services and the Model Context Protocol (MCP), automatically generating MCP tools based on OData metadata. The bridge enables AI assistants to interact with OData services through a standardized interface.

## Architecture Components

### 1. Metadata Parser (`MetadataParser`)
- Fetches and parses OData `$metadata` XML document
- Extracts entity types, entity sets, and function imports
- Handles authentication and various OData service implementations
- Falls back to service document discovery if metadata parsing fails

### 2. OData Client (`ODataClient`)
- Handles HTTP communication with the OData service
- Manages CSRF tokens for SAP services
- Provides CRUD operations and query capabilities
- Includes enhanced features:
  - Automatic GUID conversion (base64 ↔ standard format)
  - Response size limiting
  - Selective field retrieval
  - Graph-specific query methods

### 3. MCP Bridge (`ODataMCPBridge`)
- Dynamically generates MCP tools from OData metadata
- Uses Python's `exec()` to create functions with proper signatures
- Registers tools with FastMCP server
- Maps OData operations to MCP tool patterns

### 4. GUID Handler (`ODataGUIDHandler`)
- Converts between base64-encoded binary GUIDs and standard GUID format
- Optimizes responses by converting GUID fields automatically
- Identifies GUID fields based on type and naming patterns

## Data Flow

```
OData Service
     ↓
[1] Metadata Parser
     ├─→ Entity Types
     ├─→ Entity Sets
     └─→ Function Imports
     ↓
[2] MCP Bridge
     ├─→ Generate Tools
     ├─→ Register with FastMCP
     └─→ Create Tool Functions
     ↓
[3] MCP Server
     ├─→ Tool Discovery
     └─→ Tool Execution
     ↓
[4] OData Client
     ├─→ Build OData Query
     ├─→ Execute HTTP Request
     ├─→ Handle CSRF Token
     ├─→ Parse Response
     └─→ Optimize GUIDs
     ↓
[5] Response
```

## Tool Generation Pattern

For each OData entity set, the bridge generates the following MCP tools:

1. **filter_{EntitySet}** - List/filter entities with OData query options
2. **count_{EntitySet}** - Get entity count with optional filtering
3. **search_{EntitySet}** - Full-text search (if supported)
4. **get_{EntitySet}** - Retrieve single entity by key
5. **create_{EntitySet}** - Create new entity (if creatable)
6. **update_{EntitySet}** - Update existing entity (if updatable)
7. **delete_{EntitySet}** - Delete entity (if deletable)

## Concrete Examples: ZMCP_002 Service

### Service Structure

The ZMCP_002 service exposes a graph data model with:

```
Entity Sets:
- ZLLM_00_BINSet  (Binary storage)
- ZLLM_00_NODESet (Graph nodes)
- ZLLM_00_EDGESet (Graph edges)

Function Import:
- BUILD_GRAPH
```

### Entity Type: ZLLM_00_NODE

```xml
<EntityType Name="ZLLM_00_NODE">
  <Key>
    <PropertyRef Name="Seed"/>
    <PropertyRef Name="Id"/>
  </Key>
  <Property Name="Seed" Type="Edm.Int32" Nullable="false"/>
  <Property Name="Id" Type="Edm.Binary" Nullable="false" MaxLength="16"/>
  <Property Name="Node" Type="Edm.String" MaxLength="140"/>
  <Property Name="ObjType" Type="Edm.String" MaxLength="4"/>
  <Property Name="ObjName" Type="Edm.String" MaxLength="40"/>
  <!-- Additional properties... -->
</EntityType>
```

### Generated MCP Tools

#### 1. filter_ZLLM_00_NODESet

**Purpose**: Retrieve and filter graph nodes

**Signature**:
```python
async def filter_ZLLM_00_NODESet(
    *, 
    filter: Optional[str] = None,
    select: Optional[str] = None,
    expand: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    skiptoken: Optional[str] = None
) -> str
```

**Example Usage**:
```json
{
  "tool": "filter_ZLLM_00_NODESet",
  "arguments": {
    "filter": "Seed eq 0 and ObjType eq 'DEVC'",
    "select": "Seed,Node,ObjType,ObjName",
    "top": 10
  }
}
```

**Response** (with GUID optimization):
```json
{
  "results": [
    {
      "Seed": 0,
      "Node": "DEVC.$ZXRAY",
      "ObjType": "DEVC",
      "ObjName": "$ZXRAY",
      "Id": "0242AC10-0004-1FD0-8BE1-D0C2765488C2"  // Converted from base64
    }
  ],
  "pagination": {
    "total_count": 150,
    "has_more": true,
    "next_skip": 10
  }
}
```

#### 2. get_ZLLM_00_NODESet

**Purpose**: Retrieve a specific node by its composite key

**Signature**:
```python
async def get_ZLLM_00_NODESet(
    *,
    Seed: int,
    Id: str,  # Can be base64 or standard GUID
    expand: Optional[str] = None
) -> str
```

**Example Usage**:
```json
{
  "tool": "get_ZLLM_00_NODESet",
  "arguments": {
    "Seed": 0,
    "Id": "0242AC10-0004-1FD0-8BE1-D0C2765488C2"
  }
}
```

#### 3. filter_ZLLM_00_EDGESet

**Purpose**: Retrieve graph edges (relationships)

**Signature**:
```python
async def filter_ZLLM_00_EDGESet(
    *,
    filter: Optional[str] = None,
    select: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None
) -> str
```

**Example Usage** (optimized query):
```json
{
  "tool": "filter_ZLLM_00_EDGESet",
  "arguments": {
    "filter": "Seed eq 0",
    "select": "Seed,Etype",  // Excludes F and T GUIDs for performance
    "top": 100
  }
}
```

### Enhanced Graph Query Methods

The ODataClient includes specialized methods for graph queries:

#### list_nodes()

```python
nodes = await client.list_nodes(
    seed=0,
    max_nodes=100,
    include_guid=False  # Excludes Id field by default for performance
)
```

**OData Query Generated**:
```
GET /ZLLM_00_NODESet?$top=100&$select=Seed,Node,ObjType,ObjName&$filter=Seed eq 0
```

#### list_edges()

```python
edges = await client.list_edges(
    seed=0,
    max_edges=100,
    include_guids=True  # Includes F and T fields
)
```

**OData Query Generated**:
```
GET /ZLLM_00_EDGESet?$top=100&$select=Seed,Etype,F,T&$filter=Seed eq 0
```

## GUID Handling

### Problem
OData services return GUID fields as base64-encoded binary data:
- `Id`: `"AkkEEAAEH9CL4dDCiWvlwg=="`
- Takes significant space in responses
- Not human-readable
- Can cause XML serialization issues

### Solution
Automatic conversion to standard GUID format:
- `Id`: `"02490410-0004-1FD0-8BE1-D0C2896BE5C2"`
- Reduces response size
- Human-readable
- Compatible with standard GUID tools

### Implementation
```python
# Identifies GUID fields from metadata
if prop.type == "Edm.Binary" and any(name in prop.name.upper() for name in ['ID', 'GUID', 'F', 'T']):
    guid_fields.append(prop.name)

# Converts during response parsing
if field in guid_fields and is_base64(value):
    value = base64_to_guid(value)
```

## Response Optimization

### Size Limiting
```python
client = ODataClient(
    metadata, 
    optimize_guids=True,
    max_response_items=1000  # Prevents oversized responses
)
```

### Selective Field Retrieval
Default queries exclude large binary fields:
```python
# Node query - excludes Id by default
params = {
    '$select': 'Seed,Node,ObjType,ObjName',
    '$top': 100
}

# Edge query - excludes F and T by default
params = {
    '$select': 'Seed,Etype',
    '$top': 100
}
```

## Error Handling

### Common Issues and Solutions

1. **Binary GUID in XML**
   - Error: `'AkkEEAAEH9CL4dDCiWvlwg==' is not a valid value`
   - Solution: Automatic base64 to GUID conversion

2. **Response Size**
   - Error: `result exceeds maximum length`
   - Solution: Response truncation and field selection

3. **CSRF Token**
   - Error: `CSRF token validation failed`
   - Solution: Automatic token fetching and retry

4. **Invalid Filter on Binary Fields**
   - Error: `Invalid parametertype used at function 'substring'`
   - Solution: Convert GUIDs before filtering or filter in-memory

## Configuration

### Environment Variables
```bash
ODATA_URL=http://vhcala4hci:50000/sap/opu/odata/sap/ZMCP_002_SRV/
ODATA_USER=username
ODATA_PASS=password
```

### Running the MCP Server
```bash
# With environment variables
python odata_mcp.py

# With command line arguments
python odata_mcp.py --service <url> --user <user> --password <pass> --verbose
```

## MCP Tool Naming Convention

Tools follow a consistent naming pattern:
- `{operation}_{EntitySetName}`
- Operations: filter, count, search, get, create, update, delete
- Example: `filter_ZLLM_00_NODESet`

## Security Considerations

1. **Authentication**: Basic auth credentials are passed to OData service
2. **CSRF Protection**: Automatic token handling for SAP services
3. **Input Validation**: OData query parameters are validated
4. **Response Sanitization**: Responses are JSON-encoded to prevent injection

## Performance Optimizations

1. **Lazy Loading**: Metadata fetched once on startup
2. **Session Reuse**: HTTP session maintained for connection pooling
3. **Selective Queries**: Default field selection reduces payload
4. **Response Caching**: Not implemented (stateless by design)
5. **Batch Operations**: Not implemented (could be future enhancement)

## Future Enhancements

1. **OData v4 Support**: Extend parser for v4 metadata format
2. **Batch Requests**: Support `$batch` for multiple operations
3. **Navigation Properties**: Better support for `$expand`
4. **Complex Types**: Handle nested complex types
5. **Actions/Functions**: Better support for unbound functions
6. **Streaming**: Support for large binary data streams
7. **Delta Queries**: Support for change tracking