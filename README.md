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

## Installation

### Prerequisites

- Python 3.8+
- [FastMCP](https://github.com/yourusername/fastmcp) package

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/odata_mcp.git
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
| `--transport` | Transport type: 'stdio' or 'http' (SSE) | stdio |
| `--http-addr` | HTTP server address (with --transport http) | :8080 |

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

## License

Copyright (c) 2025. All rights reserved.

---

**Project Status**: Production Ready ✅  
**Architecture**: Modular and Maintainable ✅  
**Version**: 1.3 (Refactored)