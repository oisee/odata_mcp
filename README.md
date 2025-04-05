# OData MCP Wrapper

A bridge between OData v2 services and the Message Choreography Processor (MCP) pattern, dynamically generating MCP tools based on OData metadata.

## Overview

The OData MCP Wrapper enables seamless integration between OData v2 services and the Message Choreography Processor (MCP) pattern. It automatically analyzes OData service metadata and generates corresponding MCP tools, allowing AI agents to interact with OData services through a standardized interface.

### Key Features

- Automatically generates MCP tools from OData metadata
- Supports standard OData query parameters (filter, select, expand, orderby, etc.)
- Provides pagination information, entity counts, and search capabilities
- Handles CRUD operations (Create, Read, Update, Delete) for entity sets
- Supports function imports defined in the OData service
- Manages authentication, CSRF tokens, and error handling
- Provides detailed logging with optional verbose mode

## Architecture

The wrapper consists of several key components:

1. **MetadataParser**: Fetches and parses OData v2 metadata XML
2. **ODataClient**: Manages HTTP communication with the OData service
3. **ODataMCPBridge**: Main integration layer connecting OData and MCP
4. **Pydantic Models**: Structured data models for metadata components

The wrapper dynamically generates several types of tools for each entity set:
- `filter_*`: For listing and filtering entities
- `count_*`: For counting entities
- `search_*`: For text searching within entities
- `get_*`: For retrieving single entities by key
- `create_*`: For creating new entities
- `update_*`: For updating existing entities
- `delete_*`: For removing entities

It also generates tools for each function import defined in the OData service.

For more detailed information about the architecture, see [claude_purpose_extraction.md](claude_purpose_extraction.md).

## Installation

### Prerequisites

- Python 3.6+
- [FastMCP](https://github.com/yourusername/fastmcp) package
- Required Python packages (install via pip):
  - requests
  - lxml
  - pydantic
  - python-dotenv

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/odata_mcp.git
   cd odata_mcp
   ```

2. Install dependencies:
   ```bash
   pip install requests lxml pydantic python-dotenv
   ```

3. Ensure you have access to the FastMCP module

## Configuration

The wrapper can be configured using command-line arguments or environment variables.

### Environment Variables

Create a `.env` file in the project directory with the following variables:

```
# OData service URL (required)
ODATA_SERVICE_URL=https://your-odata-service.com/odata/

# Authentication (if required)
ODATA_USERNAME=your_username
ODATA_PASSWORD=your_password
```

## Usage

### Command Line

Run the wrapper using:

```bash
python odata_mcp.py --service https://your-odata-service.com/odata/ [--user USERNAME] [--password PASSWORD] [--verbose]
```

Or, if you've configured environment variables:

```bash
python odata_mcp.py
```

### Configuration Options

- `--service`: URL of the OData service (overrides environment variable)
- `--user` / `-u`: Username for basic authentication (overrides environment variable)
- `--password` / `-p`: Password for basic authentication (overrides environment variable)
- `--verbose` / `--debug`: Enable verbose output to stderr

### Using Generated Tools

Once the wrapper is running, the dynamically generated MCP tools become available:

1. **List or Filter Entities**:
   ```python
   await filter_EntitySetName(filter="PropertyName eq 'Value'", top=10, orderby="PropertyName desc")
   ```

2. **Get Entity Count**:
   ```python
   await count_EntitySetName(filter="PropertyName eq 'Value'")
   ```

3. **Search Entities**:
   ```python
   await search_EntitySetName(search_term="search phrase", top=10)
   ```

4. **Get Single Entity**:
   ```python
   await get_EntitySetName(ID="key_value", expand="NavigationProperty")
   ```

5. **Create Entity**:
   ```python
   await create_EntitySetName(PropertyName1="Value1", PropertyName2="Value2")
   ```

6. **Update Entity**:
   ```python
   await update_EntitySetName(ID="key_value", PropertyName="NewValue")
   ```

7. **Delete Entity**:
   ```python
   await delete_EntitySetName(ID="key_value")
   ```

8. **Invoke Function**:
   ```python
   await FunctionName(Param1="Value1", Param2="Value2")
   ```

9. **Get Service Info**:
   ```python
   await odata_service_info()
   ```

## Testing

Run the test suite with:

```bash
python -m unittest test_odata_mcp.py
```

To run live integration tests that connect to a real OData service:

```bash
RUN_LIVE_TESTS=true python -m unittest test_odata_mcp.py
```

The live integration tests require a valid OData service URL in your `.env` file or environment.

## Examples

### Basic Usage

```python
# Import necessary modules
from mcp.server.fastmcp import FastMCP
import asyncio

# Create an instance of the MCP client
mcp_client = FastMCP(name="odata-mcp-client")

# Connect to an OData service
service_info = await mcp_client.invoke("odata_service_info")
print(f"Connected to OData service: {service_info['service_url']}")

# List products with filtering and ordering
products = await mcp_client.invoke("filter_Products", 
                                  filter="Price gt 20", 
                                  orderby="Price desc", 
                                  top=5)
print(f"Found {len(products['results'])} expensive products")

# Get a specific product
product = await mcp_client.invoke("get_Products", ID="10")
print(f"Product details: {product['Name']} - ${product['Price']}")

# Create a new category
new_category = await mcp_client.invoke("create_Categories", 
                                      Name="New Category", 
                                      Description="Example category created through OData MCP")
print(f"Created category with ID: {new_category['ID']}")
```

## Roadmap

- Support for OData v4 services
- Enhanced batch operations
- Support for additional authentication methods (OAuth, SAML)
- Improved caching for better performance
- Schema validation for input/output data

## Troubleshooting

### Common Issues

1. **Connection failures**:
   - Verify the OData service URL is correct
   - Ensure network connectivity and permissions
   - Check authentication credentials if required

2. **Missing entity sets or tools**:
   - The service metadata might be incomplete
   - Run with `--verbose` to see detailed information about the parsing process

3. **Operation failures**:
   - Check for constraints in the OData service
   - Verify required properties for create/update operations
   - Ensure key values are correctly formatted

### Logging

Enable verbose logging with the `--verbose` flag to see detailed information about:
- Metadata parsing
- HTTP requests and responses
- Tool registration
- Error details

## License

Copyright (c) 2025