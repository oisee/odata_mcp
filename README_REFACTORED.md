# OData MCP Wrapper - Refactored Version

This is the refactored, modular version of the OData MCP Wrapper that has been split into separate modules for better maintainability.

## Project Structure

```
odata_mcp_lib/
├── __init__.py           # Main exports
├── constants.py          # Constants and type mappings
├── models.py            # Pydantic data models
├── guid_handler.py      # GUID conversion utilities
├── metadata_parser.py   # OData metadata parsing
├── client.py           # OData HTTP client
└── bridge.py           # MCP bridge implementation

odata_mcp_refactored.py  # Main executable script
test_odata_mcp.py       # Unit tests
```

## Key Improvements

### 1. Modular Architecture
- Split the monolithic file into focused modules
- Each module has a single responsibility
- Better code organization and maintainability

### 2. Enhanced Error Handling
- Improved error message propagation from OData services
- Better handling of connection errors and timeouts
- More detailed error reporting instead of "No details available"

### 3. Smart Tool Naming
- Simple service identification from OData URLs preserving original naming:
  - SAP services: `/sap/opu/odata/sap/ZODD_000_SRV` → `ZODD_000_SRV`
  - .svc endpoints: `/MyService.svc` → `MyService_svc`
  - Generic services: `/odata/TestService` → `TestService`
  - Host-based: `service.example.com` → `service_example_com`

### 4. Clean Codebase
- Removed redundant and backup files
- Updated imports to use the new modular structure
- Consolidated test files

## Usage

The refactored version maintains the same API as the original:

```bash
python odata_mcp.py --service https://your-odata-service.com/odata --verbose
```

## Backward Compatibility

**✅ No migration needed!** The refactored version maintains full backward compatibility:

- `odata_mcp.py` - Main executable (now modular, same API)
- Existing programs continue to work without changes
- For new code, you can use either:
  ```python
  # Option 1: Use the modular library directly (recommended)
  from odata_mcp_lib import MetadataParser, ODataClient, ODataMCPBridge
  
  # Option 2: Use the compatibility layer (for existing code)
  from odata_mcp_compat import MetadataParser, ODataClient, ODataMCPBridge
  ```

## Testing

Run the test suite:

```bash
python test_odata_mcp.py
```

For live integration tests:

```bash
RUN_LIVE_TESTS=true python test_odata_mcp.py
```