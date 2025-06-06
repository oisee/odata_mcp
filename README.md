# OData MCP Wrapper

A bridge between OData v2 services and the Message Choreography Processor (MCP) pattern, dynamically generating MCP tools based on OData metadata.

## Overview

The OData MCP Wrapper enables seamless integration between OData v2 services and the Message Choreography Processor (MCP) pattern. It automatically analyzes OData service metadata and generates corresponding MCP tools, allowing AI agents to interact with OData services through a standardized interface.

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

### Command Line

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
└── bridge.py                     # MCP bridge implementation

odata_mcp.py                      # Main executable
odata_mcp_compat.py               # Backward compatibility layer
test_odata_mcp.py                 # Test suite
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