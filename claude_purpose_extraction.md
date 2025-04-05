# OData MCP (Message Choreography Processor) Wrapper

## Purpose

The OData MCP Wrapper is a bridge between OData v2 services and the Message Choreography Processor (MCP) pattern. It dynamically generates MCP tools based on OData metadata, allowing seamless interaction with OData services through the MCP interface.

Key features:
- Automatically generates MCP tools from OData metadata
- Supports standard OData query parameters (filter, select, expand, etc.)
- Provides pagination information, entity counts, and search capabilities
- Handles CRUD operations (Create, Read, Update, Delete) for entity sets
- Includes proper error handling and CSRF token management for secure operations

## Architecture

### Core Components

1. **MetadataParser**
   - Fetches and parses OData v2 metadata XML
   - Extracts entity types, entity sets, and function imports
   - Handles fallback mechanisms for incomplete metadata

2. **ODataClient**
   - Manages HTTP communication with the OData service
   - Implements OData protocol operations (list, filter, create, update, delete)
   - Handles authentication, CSRF token management, and error parsing

3. **ODataMCPBridge**
   - Main integration layer connecting OData and MCP
   - Dynamically generates MCP tools based on metadata
   - Creates specific tools for each entity set and function import

4. **Pydantic Models**
   - `EntityProperty`: Represents properties of entity types
   - `EntityType`: Defines entity structure and key properties
   - `EntitySet`: Maps to OData entity collections
   - `FunctionImport`: Represents callable OData functions
   - `ODataMetadata`: Holds the complete service metadata

### Tool Generation

The wrapper dynamically generates several types of tools for each entity set:
- `filter_*`: For listing and filtering entities
- `count_*`: For counting entities
- `search_*`: For text searching within entities
- `get_*`: For retrieving single entities by key
- `create_*`: For creating new entities
- `update_*`: For updating existing entities
- `delete_*`: For removing entities

It also generates tools for each function import defined in the OData service.

### Dynamic Code Generation

A key architectural feature is the use of Python's `exec()` function to dynamically create tool functions with proper signatures matching the OData metadata. This approach creates strongly-typed tools that match the exact structure of the OData service.

### Error Handling

The wrapper includes comprehensive error handling:
- OData-specific error parsing and formatting
- Authentication and authorization error detection
- Fallback mechanisms for partially supported OData services
- Detailed logging with optional verbose mode

### Authentication and Security

- Supports Basic Authentication
- Handles CSRF token management for modifying operations
- Properly sanitizes inputs and handles key formatting

## Usage

The tool can be invoked from the command line with parameters:
```
python odata_mcp.py --service URL [--user USERNAME] [--password PASSWORD] [--verbose]
```

Or using environment variables:
- `ODATA_SERVICE_URL`: OData service endpoint
- `ODATA_USERNAME`: Basic auth username
- `ODATA_PASSWORD`: Basic auth password

The wrapper serves as a bridge that makes any OData v2 service available as an MCP tool set, allowing AI agents to interact with OData services through a standardized interface.