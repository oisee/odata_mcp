# Quick Reference Guide

## Common Commands

### Basic Usage
```bash
# Using environment variable
export ODATA_URL=https://service.com/odata/
python odata_mcp.py

# Using command line
python odata_mcp.py --service https://service.com/odata/

# With authentication
python odata_mcp.py --user myuser --password mypass https://service.com/odata/
```

### Authentication Options
```bash
# Basic auth
python odata_mcp.py -u admin -p secret https://service.com/odata/

# Cookie file
python odata_mcp.py --cookie-file cookies.txt https://service.com/odata/

# Cookie string
python odata_mcp.py --cookie-string "session=abc123" https://service.com/odata/
```

### Read-Only Modes
```bash
# Hide all modifications
python odata_mcp.py --read-only https://service.com/odata/
python odata_mcp.py -ro https://service.com/odata/  # short form

# Hide CRUD but allow functions
python odata_mcp.py --read-only-but-functions https://service.com/odata/
python odata_mcp.py -robf https://service.com/odata/  # short form
```

### Tool Naming
```bash
# Custom prefix
python odata_mcp.py --no-postfix --tool-prefix "myapp" https://service.com/odata/

# Custom postfix
python odata_mcp.py --tool-postfix "prod" https://service.com/odata/

# Shortened names
python odata_mcp.py --tool-shrink https://service.com/odata/
```

### Entity/Function Filtering
```bash
# Specific entities
python odata_mcp.py --entities "Products,Orders,Customers" https://service.com/odata/

# Wildcards
python odata_mcp.py --entities "Product*,Order*" https://service.com/odata/

# Function filtering
python odata_mcp.py --functions "Get*,Create*" https://service.com/odata/
```

### Debugging
```bash
# Verbose output
python odata_mcp.py --verbose https://service.com/odata/

# Show all tools and exit
python odata_mcp.py --trace https://service.com/odata/

# MCP protocol trace
python odata_mcp.py --trace-mcp https://service.com/odata/
```

### Performance Tuning
```bash
# Limit response size
python odata_mcp.py --max-response-size 1048576 --max-items 50 https://service.com/odata/

# Enable pagination hints
python odata_mcp.py --pagination-hints https://service.com/odata/
```

### SAP-Specific
```bash
# Full SAP compatibility
python odata_mcp.py \
  --legacy-dates \
  --verbose-errors \
  --response-metadata \
  https://sap-service.com/odata/
```

### Hints System
```bash
# Default hints.json
python odata_mcp.py https://service.com/odata/

# Custom hints file
python odata_mcp.py --hints-file my-hints.json https://service.com/odata/

# CLI hint
python odata_mcp.py --hint "Use \$expand for complex queries" https://service.com/odata/
```

## Environment Variables

```bash
# Service URL
export ODATA_URL=https://service.com/odata/
export ODATA_SERVICE_URL=https://service.com/odata/  # alternative

# Basic auth
export ODATA_USERNAME=myuser
export ODATA_USER=myuser  # alternative
export ODATA_PASSWORD=mypass
export ODATA_PASS=mypass  # alternative

# Cookie auth
export ODATA_COOKIE_FILE=/path/to/cookies.txt
export ODATA_COOKIE_STRING="session=abc123; token=xyz789"
```

## Tool Naming Patterns

### Default Pattern
- `filter_EntitySet_for_service`
- `get_EntitySet_for_service`
- `create_EntitySet_for_service`
- `update_EntitySet_for_service`
- `delete_EntitySet_for_service`
- `FunctionName_for_service`

### With --tool-shrink
- `filter_Entity_svc`
- `get_Entity_svc`
- `create_Entity_svc`
- `upd_Entity_svc`
- `del_Entity_svc`
- `Function_svc`

## Common OData Query Parameters

```python
# Filtering
filter_Products($filter="Price gt 100")
filter_Products($filter="Category eq 'Electronics'")
filter_Products($filter="startswith(Name, 'iPhone')")

# Selecting fields
filter_Products($select="ID,Name,Price")

# Sorting
filter_Products($orderby="Price desc")
filter_Products($orderby="Category,Price desc")

# Pagination
filter_Products($top=10, $skip=20)

# Expanding relations
get_Order($expand="Items,Customer")

# Counting
filter_Products($filter="Price gt 100", $count=True)
```

## Troubleshooting Commands

```bash
# Test metadata access
curl https://service.com/odata/\$metadata

# Full debugging
python odata_mcp.py \
  --verbose \
  --verbose-errors \
  --trace-mcp \
  https://service.com/odata/

# Safe exploration
python odata_mcp.py \
  --read-only \
  --trace \
  https://service.com/odata/
```

## MCP Client Configuration

### Claude Desktop
```json
{
  "mcpServers": {
    "odata": {
      "command": "python",
      "args": [
        "/path/to/odata_mcp.py",
        "--service", "https://service.com/odata/",
        "--read-only",
        "--tool-shrink"
      ],
      "env": {
        "ODATA_USERNAME": "user",
        "ODATA_PASSWORD": "pass"
      }
    }
  }
}
```

## Flag Reference

| Short | Long | Description |
|-------|------|-------------|
| `-u` | `--user` | Username |
| `-p` | `--password` | Password |
| `-v` | `--verbose` | Verbose output |
| `-ro` | `--read-only` | Hide all modifications |
| `-robf` | `--read-only-but-functions` | Hide CRUD, allow functions |

## Quick Fixes

### HTTP 501 Error (SAP)
```python
# Instead of: get_Entity(ID='123')
# Use: filter_EntitySet($filter="ID eq '123'", $expand="Details")
```

### Date Filtering (SAP)
```python
# Use YYYYMMDD format
filter_Orders($filter="CreatedDate ge '20240101' and CreatedDate le '20241231'")
```

### Large Responses
```python
# Add pagination
filter_LargeSet($top=50, $skip=0)

# Select only needed fields
filter_LargeSet($select="ID,Name", $top=50)
```

### Authentication Failed
```bash
# Check credentials
curl -u user:pass https://service.com/odata/

# Try cookie auth
python odata_mcp.py --cookie-file cookies.txt https://service.com/odata/
```