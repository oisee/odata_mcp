# OData MCP Wrapper

A bridge between OData v2 services and the Model Context Protocol (MCP), dynamically generating MCP tools based on OData metadata.

## Overview

The OData MCP Wrapper enables seamless integration between OData v2 services and the MCP (MCP). It automatically analyzes OData service metadata and generates corresponding MCP tools, allowing AI agents to interact with OData services through a standardized interface.

### Key Features

- **Modular Architecture**: Split into focused modules for maintainability
- **Enhanced Error Handling**: Comprehensive OData error parsing and propagation
- **Smart Tool Naming**: Service-aware tool naming preserving original names
- **Automatic Tool Generation**: Creates MCP tools from OData metadata
- **Full CRUD Support**: Create, Read, Update, Delete operations for entity sets
- **Query Capabilities**: Standard OData query parameters (filter, select, expand, orderby, etc.)
- **Function Import Support**: Handles OData function imports
- **Authentication**: Basic auth and cookie-based auth with CSRF token management
- **GUID Optimization**: Automatic base64 ↔ standard GUID conversion
- **Response Optimization**: Size limiting and selective field retrieval
- **Legacy Date Support**: Automatic conversion between SAP /Date(milliseconds)/ and ISO 8601
- **Decimal Field Handling**: Automatic numeric to string conversion for Edm.Decimal fields
- **Pagination Hints**: Suggested next call parameters for easy pagination
- **Flexible Response Control**: Options for metadata inclusion and error verbosity
- **Multiple Transport Options**: STDIO (default) and HTTP/SSE for web-based clients
- **Read-Only Modes**: Options to hide modifying operations for safer exploration
- **Service-Specific Hints**: Implementation guidance for known problematic services
- **MCP Protocol Tracing**: Debug logging for troubleshooting client issues

## Installation

### Prerequisites

- Python 3.8+
- [FastMCP](https://github.com/yourusername/fastmcp) package

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/jlowin/odata_mcp.git
   cd odata_mcp
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project directory:

```bash
# OData service URL (required)
ODATA_SERVICE_URL=https://your-odata-service.com/odata/
ODATA_URL=https://your-odata-service.com/odata/  # Alternative

# Basic Authentication (if required)
ODATA_USERNAME=your_username
ODATA_USER=your_username  # Alternative
ODATA_PASSWORD=your_password
ODATA_PASS=your_password  # Alternative

# Cookie Authentication (alternative to basic auth)
ODATA_COOKIE_FILE=/path/to/cookie.txt
ODATA_COOKIE_STRING="session=abc123; token=xyz789"
```

## Usage

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--service` | OData service URL (overrides positional arg and env var) | - |
| `-u, --user` | Username for basic authentication | - |
| `-p, --password` | Password for basic authentication | - |
| `--cookie-file` | Path to cookie file (Netscape format) | - |
| `--cookie-string` | Cookie string (key1=val1; key2=val2) | - |
| `-v, --verbose, --debug` | Enable verbose output to stderr | False |
| `--tool-prefix` | Custom prefix for tool names | - |
| `--tool-postfix` | Custom postfix for tool names | `_for_<service_id>` |
| `--no-postfix` | Use prefix instead of postfix | False |
| `--tool-shrink` | Use shortened tool names | False |
| `--entities` | Comma-separated entities (supports wildcards with *) | All entities |
| `--functions` | Comma-separated functions (supports wildcards with *) | All functions |
| `--sort-tools` | Sort tools alphabetically | True |
| `--no-sort-tools` | Disable alphabetical sorting of tools | - |
| `--pagination-hints` | Add suggested_next_call in pagination responses | False |
| `--legacy-dates` | Convert /Date(ms)/ to/from ISO 8601 | True |
| `--no-legacy-dates` | Disable legacy date format conversion | - |
| `--verbose-errors` | Include detailed error messages | False |
| `--response-metadata` | Include __metadata blocks in responses | False |
| `--max-response-size` | Maximum response size in bytes | 5242880 (5MB) |
| `--max-items` | Maximum items per response | 100 |
| `--trace` | Print all tools and exit (debugging) | False |
| `--trace-mcp` | Enable detailed MCP protocol trace logging | False |
| `--read-only, -ro` | Hide all modifying operations (create, update, delete, functions) | False |
| `--read-only-but-functions, -robf` | Hide create, update, delete but allow functions | False |
| `--enable` | Enable only specific operation types (see Operation Type Filtering) | - |
| `--disable` | Disable specific operation types (see Operation Type Filtering) | - |
| `--hints-file` | Path to hints JSON file | hints.json |
| `--hint` | Direct hint JSON or text to inject | - |
| `--info-tool-name` | Custom name for the service info tool | odata_service_info |
| `--transport` | Transport type: 'stdio' or 'http' (SSE) | stdio |
| `--http-addr` | HTTP server address (with --transport http) | :8080 |

### Service Info Tool

The wrapper automatically creates a service info tool that provides comprehensive metadata about the OData service:

- **Default name**: `odata_service_info` (with service-specific postfix)
- **Alias**: `readme` (automatically created for better discoverability)
- **Custom name**: Use `--info-tool-name` to specify a custom name

This tool is marked as the **RECOMMENDED STARTING POINT** and provides:
- Service URL and description
- Available entity sets and their operations
- Entity types with properties and relationships
- Function imports with parameters
- Implementation hints and known issues
- List of all registered MCP tools

Example:
```bash
# Default naming (creates both odata_service_info and readme aliases)
python odata_mcp.py --service https://example.com/odata/

# Custom naming (no readme alias)
python odata_mcp.py --service https://example.com/odata/ --info-tool-name get_started
```

### Read-Only Modes

The wrapper supports read-only modes for safer exploration of OData services:

- **`--read-only` (`-ro`)**: Hides all modifying operations (create, update, delete, and function imports)
- **`--read-only-but-functions` (`-robf`)**: Hides create, update, and delete operations but still allows function imports

These modes are mutually exclusive and useful when:
- Exploring unfamiliar OData services
- Preventing accidental data modifications
- Creating read-only MCP endpoints for users

### Operation Type Filtering

The wrapper supports fine-grained control over which operation types are generated using `--enable` and `--disable` flags. This helps reduce tool count for services with many entities.

#### Operation Types

- **C**: Create operations
- **S**: Search operations
- **F**: Filter operations (includes count)
- **G**: Get (retrieve single entity) operations
- **U**: Update operations
- **D**: Delete operations
- **A**: Actions/Function imports
- **R**: Read operations (expands to S, F, and G)

#### Examples

```bash
# Enable only read operations (search, filter, get)
python odata_mcp.py --service https://example.com/odata/ --enable "R"

# Enable only filter and get operations
python odata_mcp.py --service https://example.com/odata/ --enable "FG"

# Disable create, update, and delete operations
python odata_mcp.py --service https://example.com/odata/ --disable "CUD"

# Disable actions/function imports
python odata_mcp.py --service https://example.com/odata/ --disable "A"
```

**Notes:**
- Operation codes are case-insensitive
- `--enable` and `--disable` are mutually exclusive
- The special `R` code in `--enable` expands to S, F, and G operations
- This filtering is more flexible than `--read-only` modes as it allows specific operation combinations

### Service-Specific Hints

The wrapper includes a flexible hint system to provide guidance for services with known issues or special requirements:

```bash
# Use default hints.json from script directory
python odata_mcp.py https://my-service.com/odata/

# Use custom hints file
python odata_mcp.py --hints-file /path/to/custom-hints.json https://my-service.com/odata/

# Inject hint directly from command line
python odata_mcp.py --hint "Remember to use \$expand for complex queries" https://my-service.com/odata/

# Combine file and CLI hints (CLI has higher priority)
python odata_mcp.py --hints-file custom.json --hint '{"notes":["Override note"]}' https://my-service.com/odata/
```

Hints are matched by URL patterns and appear in the `odata_service_info` tool response under `implementation_hints`.

Default hints are provided for:
- **SAP OData Services**: General SAP-specific issues and workarounds
- **SAP PO Tracking Service** (SRA020_PO_TRACKING_SRV): Specific guidance for purchase order tracking
- **Northwind Demo Services**: Identifies public demo services

#### Hint File Structure

The hints.json file follows this structure:

```json
{
  "version": "1.0",
  "hints": [
    {
      "pattern": "*/sap/opu/odata/*",
      "priority": 10,
      "service_type": "SAP OData Service",
      "known_issues": [...],
      "workarounds": [...],
      "field_hints": {
        "FieldName": {
          "type": "Edm.String",
          "format": "Expected format",
          "example": "12345"
        }
      },
      "examples": [
        {
          "description": "Example description",
          "query": "filter_EntitySet with $filter=...",
          "note": "Additional note"
        }
      ],
      "notes": [...]
    }
  ]
}
```

Patterns support wildcards (* and ?) and are matched against the service URL. Multiple hints can match; they are merged by priority (higher values override).

### MCP Protocol Tracing

Use `--trace-mcp` to enable detailed protocol debugging. This creates a log file with all MCP messages:
- Linux/WSL: `/tmp/mcp_trace_*.log`
- Windows: `%TEMP%\mcp_trace_*.log`

Useful for diagnosing client compatibility issues.

### Command Line Examples

```bash
# Using environment variables
python odata_mcp.py

# Using command line arguments (basic auth)
python odata_mcp.py --service https://your-service.com/odata/ \
                    --user USERNAME \
                    --password PASSWORD \
                    --verbose

# Using cookie authentication
python odata_mcp.py --service https://your-service.com/odata/ \
                    --cookie-file cookie.txt \
                    --verbose

# Additional options
python odata_mcp.py --tool-prefix myprefix \
                    --tool-postfix myservice \
                    --no-postfix

# Generate tools only for specific entities
python odata_mcp.py --service https://your-service.com/odata/ \
                    --entities "Products,Categories,Orders" \
                    --verbose

# Use wildcards in entity filtering
python odata_mcp.py --service https://your-service.com/odata/ \
                    --entities "Product*,Order*,Customer" \
                    --verbose

# Control tool sorting (default is alphabetical)
python odata_mcp.py --service https://your-service.com/odata/ \
                    --no-sort-tools \
                    --verbose

# Enable pagination hints for easier navigation
python odata_mcp.py --service https://your-service.com/odata/ \
                    --pagination-hints \
                    --verbose

# SAP-specific options for legacy systems
python odata_mcp.py --service https://sap-service.com/odata/ \
                    --legacy-dates \
                    --response-metadata \
                    --verbose-errors

# Debug mode - show all tools without starting server
python odata_mcp.py --service https://your-service.com/odata/ \
                    --trace

# Run with HTTP/SSE transport for web clients
python odata_mcp.py --service https://your-service.com/odata/ \
                    --transport http \
                    --http-addr :8080

# HTTP transport on specific interface
python odata_mcp.py --service https://your-service.com/odata/ \
                    --transport http \
                    --http-addr 127.0.0.1:3000

# Read-only mode - hide all modifying operations
python odata_mcp.py --service https://your-service.com/odata/ \
                    --read-only \
                    --verbose

# Read-only but allow functions
python odata_mcp.py --service https://your-service.com/odata/ \
                    --read-only-but-functions \
                    --verbose

# Enable MCP protocol trace logging for debugging
python odata_mcp.py --service https://your-service.com/odata/ \
                    --trace-mcp \
                    --verbose
```

### Generated Tools

The wrapper dynamically generates MCP tools for each entity set. Use `--entities` to limit tool generation to specific entities only (useful for large services):

1. **List/Filter**: `filter_EntitySetName` - Query entities with filtering, sorting, pagination
2. **Count**: `count_EntitySetName` - Get entity count with optional filtering  
3. **Search**: `search_EntitySetName` - Full-text search (if supported)
4. **Get**: `get_EntitySetName` - Retrieve single entity by key
5. **Create**: `create_EntitySetName` - Create new entity
6. **Update**: `update_EntitySetName` - Update existing entity  
7. **Delete**: `delete_EntitySetName` - Delete entity

### Example Usage

```python
# List entities with filtering
await filter_ProductSet(
    filter="Price gt 20", 
    orderby="Price desc", 
    top=10
)

# Get specific entity
await get_ProductSet(ID="12345")

# Create new entity
await create_ProductSet(
    Name="New Product",
    Price=99.99,
    CategoryID="CAT001"
)

# Update entity
await update_ProductSet(
    ID="12345",
    Price=89.99
)

# Get service information
await odata_service_info()
```

## Transport Options

The OData MCP bridge supports two transport mechanisms:

### 1. STDIO Transport (Default)
- Standard input/output communication
- Used by Claude Desktop and other MCP clients
- No additional configuration required

### 2. HTTP/SSE Transport
- HTTP server with Server-Sent Events
- Enables web-based clients to interact with OData services
- Endpoints:
  - `GET /health` - Health check
  - `GET /sse` - Server-Sent Events stream
  - `POST /rpc` - JSON-RPC endpoint

#### Using HTTP/SSE Transport

```bash
# Start with default port 8080
python odata_mcp.py --transport http --service https://your-service.com/odata/

# Use custom port
python odata_mcp.py --transport http --http-addr :3000 --service https://your-service.com/odata/

# Bind to specific interface
python odata_mcp.py --transport http --http-addr 192.168.1.100:8080 --service https://your-service.com/odata/
```

#### Testing HTTP/SSE Transport

1. **Using the provided HTML client:**
   ```bash
   # Start the server
   python odata_mcp.py --transport http --service https://services.odata.org/V2/Northwind/Northwind.svc/
   
   # Open examples/sse_client.html in a web browser
   ```

2. **Using the test script:**
   ```bash
   ./test_http_transport.sh
   ```

3. **Using curl:**
   ```bash
   # Test health endpoint
   curl http://localhost:8080/health
   
   # Test RPC endpoint
   curl -X POST http://localhost:8080/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
   ```

> ⚠️ **Security Warning**: The HTTP/SSE transport does not include authentication. Only use it in secure, trusted environments or behind a reverse proxy with proper authentication.

## Architecture

The project uses a modular architecture for maintainability:

```
odata_mcp_lib/                    # Core modular library
├── __init__.py                   # Clean API exports
├── constants.py                  # OData type mappings & namespaces
├── models.py                     # Pydantic data models
├── guid_handler.py               # GUID conversion utilities
├── metadata_parser.py            # OData metadata parsing
├── client.py                     # HTTP client with error handling
├── bridge.py                     # MCP bridge implementation
├── name_shortener.py             # Tool name shortening logic
└── transport/                    # Transport implementations
    ├── __init__.py               # Transport base classes
    ├── stdio.py                  # STDIO transport
    └── http_sse.py               # HTTP/SSE transport

odata_mcp.py                      # Main executable
examples/
├── sse_client.html               # Web-based SSE client
test_odata_mcp.py                 # Test suite
test_http_transport.sh            # HTTP transport test script
```

### Key Components

- **MetadataParser**: Fetches and parses OData `$metadata` XML
- **ODataClient**: Manages HTTP communication and CSRF tokens
- **ODataMCPBridge**: Generates MCP tools from metadata
- **GUIDHandler**: Converts between base64 and standard GUID formats

## Testing

```bash
# Run unit tests
python test_odata_mcp.py

# Run with live service (requires valid OData service)
RUN_LIVE_TESTS=true python test_odata_mcp.py
```

## Import Compatibility

### New Code (Recommended)
```python
from odata_mcp_lib import MetadataParser, ODataClient, ODataMCPBridge
```

### Legacy Code (Backward Compatible)
```python
from odata_mcp_compat import MetadataParser, ODataClient, ODataMCPBridge
```

## TODO & Roadmap

### High Priority
- [ ] Enhanced testing suite with comprehensive coverage
- [ ] Module-specific unit tests leveraging new architecture
- [ ] CI/CD pipeline setup for automated testing
- [ ] Performance benchmarking and optimization

### Short-term Goals (3-6 months)
- [ ] OData v4 support
- [ ] Enhanced batch operations
- [x] Cookie-based authentication (completed)
- [ ] OAuth 2.0 authentication
- [ ] Response caching for performance
- [ ] Input validation improvements

### Medium-term Goals (6-12 months)
- [ ] Schema validation for input/output data
- [ ] Advanced query capabilities (complex filters, aggregations)
- [ ] Navigation property enhancements
- [ ] Custom tool generation templates

### Long-term Goals (12+ months)
- [ ] GraphQL interface layer
- [ ] Cross-service federation
- [ ] Advanced security features (field-level security, data masking)
- [ ] Comprehensive monitoring and metrics
- [ ] Horizontal scaling support

### Recently Completed ✅
- [x] **Modular Architecture**: Split monolithic codebase into 7 focused modules
- [x] **Enhanced Error Handling**: Comprehensive OData error parsing
- [x] **Smart Tool Naming**: Service-aware naming preserving original names
- [x] **Backward Compatibility**: Zero breaking changes maintained
- [x] **Code Cleanup**: Removed redundant files and improved organization
- [x] **GUID Optimization**: Automatic base64 ↔ standard format conversion
- [x] **Response Optimization**: Size limiting and field selection
- [x] **Cookie Authentication**: Support for SSO/MYSAPSSO2 tokens (see [COOKIE_AUTH.md](COOKIE_AUTH.md))
- [x] **Legacy Date Support**: SAP /Date(milliseconds)/ format conversion
- [x] **Decimal Field Handling**: Automatic conversion for Edm.Decimal types
- [x] **Pagination Hints**: Suggested next call parameters for easy pagination
- [x] **Enhanced Trace Mode**: Comprehensive debugging output
- [x] **Feature Parity**: Matched Go implementation features
- [x] **HTTP/SSE Transport**: Web-based client support via Server-Sent Events
- [x] **Transport Abstraction**: Clean interface for multiple transport types
- [x] **Read-Only Modes**: Options to hide modifying operations (--read-only, --read-only-but-functions)
- [x] **Service Hints**: Implementation guidance for known problematic services
- [x] **MCP Trace Logging**: Protocol debugging support with --trace-mcp

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Verify OData service URL and network connectivity
   - Check authentication credentials
   - Use `--verbose` for detailed error information

2. **Import Errors**
   - Use `from odata_mcp_lib import ...` for new imports
   - Use `from odata_mcp_compat import ...` for legacy compatibility

3. **Tool Generation Issues**
   - Ensure service metadata is accessible
   - Check for valid entity sets in the metadata
   - Review verbose logs for parsing errors

4. **GUID/Binary Field Issues**
   - GUID fields are automatically converted from base64
   - Binary fields may be excluded by default for performance

### Performance Tips

- Use `$select` to limit returned fields
- Apply `$top` for pagination
- Use `$filter` to reduce result sets
- Consider excluding binary fields for large datasets

## Additional Documentation

- [Architecture Guide](ARCHITECTURE.md) - System design and module structure
- [Implementation Guide](IMPLEMENTATION_GUIDE.md) - Development patterns and guidelines
- [Cookie Authentication](COOKIE_AUTH.md) - Detailed cookie auth documentation

## License

Copyright (c) 2025. All rights reserved.

---

**Project Status**: Production Ready ✅  
**Architecture**: Modular and Maintainable ✅  
**Version**: 1.3 (Refactored)
