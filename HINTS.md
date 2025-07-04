# OData MCP Bridge - Service Hints Guide

The OData MCP Bridge includes a flexible hint system to help users work with OData services that have known issues or special requirements. This guide explains how to use and customize the hint system.

## Overview

Service hints provide:
- Known issues and limitations of specific OData services
- Workarounds for common problems
- Field formatting guidance
- Example queries that work correctly
- Implementation notes

Hints are displayed in the `odata_service_info` tool response, making them easily accessible when working with a service.

## Using Hints

### Default Behavior

By default, the bridge looks for a `hints.json` file in the same directory as the script:

```bash
python odata_mcp.py https://my-service.com/odata/
```

### Custom Hints File

Use a custom hints file with the `--hints-file` flag:

```bash
python odata_mcp.py --hints-file /path/to/my-hints.json https://my-service.com/odata/
```

### Command Line Hints

Inject hints directly from the command line:

```bash
# Simple text hint
python odata_mcp.py --hint "Remember to use \$expand for navigation properties" https://my-service.com/odata/

# JSON hint
python odata_mcp.py --hint '{"notes":["Custom note"], "workarounds":["Custom workaround"]}' https://my-service.com/odata/
```

### Viewing Hints

Hints appear in the `odata_service_info` tool response:

```json
{
  "service_url": "https://my-service.com/odata/",
  "service_description": "Service description",
  "entity_sets": {...},
  "implementation_hints": {
    "service_type": "SAP OData Service",
    "known_issues": [
      "Some SAP OData services return HTTP 501 Not Implemented for direct entity access"
    ],
    "workarounds": [
      "Use $expand parameter when getting entities by key to avoid 501 errors"
    ],
    "hint_source": "file: hints.json"
  }
}
```

## Hint File Format

The `hints.json` file structure:

```json
{
  "version": "1.0",
  "hints": [
    {
      "pattern": "*/sap/opu/odata/*",
      "priority": 10,
      "service_type": "SAP OData Service",
      "known_issues": [
        "Issue 1",
        "Issue 2"
      ],
      "workarounds": [
        "Workaround 1",
        "Workaround 2"
      ],
      "notes": [
        "Additional note 1",
        "Additional note 2"
      ],
      "field_hints": {
        "FieldName": {
          "type": "Edm.String",
          "format": "10-digit numeric string",
          "example": "1234567890",
          "description": "Field description",
          "required": true
        }
      },
      "entity_hints": {
        "EntitySet": {
          "description": "Entity description",
          "notes": ["Entity-specific notes"],
          "examples": ["Example queries"]
        }
      },
      "function_hints": {
        "FunctionName": {
          "description": "Function description",
          "parameters": [{"name": "param1", "type": "String"}],
          "examples": ["Example calls"]
        }
      },
      "examples": [
        {
          "description": "Get purchase order with details",
          "query": "filter_PurchaseOrderSet with $filter=\"PONumber eq '1234567890'\" and $expand=Items",
          "note": "This bypasses HTTP 501 errors"
        }
      ]
    }
  ]
}
```

### Field Descriptions

- **pattern**: URL pattern with wildcard support (`*` matches any characters, `?` matches single character)
- **priority**: Higher numbers take precedence when multiple patterns match (default: 0)
- **service_type**: Human-readable service type name
- **known_issues**: Array of known problems with the service
- **workarounds**: Array of solutions to known issues
- **notes**: General notes about the service
- **field_hints**: Field-specific guidance (types, formats, examples)
- **entity_hints**: Entity-specific guidance
- **function_hints**: Function-specific guidance
- **examples**: Complete example queries with explanations

## Pattern Matching

The hint system uses pattern matching to determine which hints apply to a service:

### Wildcard Patterns

- `*` - Matches any sequence of characters
- `?` - Matches exactly one character

### Examples

- `*/sap/opu/odata/*` - Matches all SAP OData services
- `*SRA020_PO_TRACKING_SRV*` - Matches services containing this name
- `https://myserver.com/odata/*` - Matches all services on a specific server
- `*Northwind*` - Matches any service with "Northwind" in the URL

### Priority and Merging

When multiple patterns match a service URL:

1. All matching hints are collected
2. CLI hint (if present) is added with priority 1000
3. Hints are sorted by priority (higher first)
4. Hints are merged, with higher priority values overriding lower ones
5. Arrays (known_issues, workarounds, notes) are combined without duplicates
6. Objects (field_hints, entity_hints) are merged with override

## Default Hints

The bridge includes default hints for common services:

### SAP OData Services

Pattern: `*/sap/opu/odata/*`

Provides general guidance for SAP OData services including:
- HTTP 501 workaround using `$expand`
- CSRF token handling
- Date format considerations
- Decimal field handling

### SAP PO Tracking Service

Pattern: `*SRA020_PO_TRACKING_SRV*`

Specific hints for the SAP Purchase Order Tracking service:
- Critical workaround for HTTP 501 errors
- PONumber field formatting requirements (10 characters, left-padded)
- Date filtering format (YYYYMMDD)
- Complete examples using `$expand`

### Northwind Demo

Pattern: `*Northwind*`

Identifies the public Northwind demo service for testing.

## Creating Custom Hints

### Step 1: Identify Issues

Test your OData service and note any issues:
- Error messages
- Formatting requirements
- Required workarounds
- Successful query patterns

### Step 2: Create Hint File

Create a `hints.json` file with your findings:

```json
{
  "version": "1.0",
  "hints": [
    {
      "pattern": "*my-service.com/odata/*",
      "priority": 100,
      "service_type": "My Custom Service",
      "known_issues": [
        "Requires specific date format",
        "Case-sensitive field names"
      ],
      "workarounds": [
        "Use ISO 8601 dates: 2024-01-01T00:00:00Z",
        "Check $metadata for exact field casing"
      ],
      "field_hints": {
        "CreatedDate": {
          "type": "Edm.DateTime",
          "format": "ISO 8601",
          "example": "2024-01-01T00:00:00Z"
        }
      }
    }
  ]
}
```

### Step 3: Test Your Hints

```bash
# Test with your custom hints
python odata_mcp.py --hints-file my-hints.json https://my-service.com/odata/

# Verify hints appear in service info
# Call odata_service_info tool in your MCP client
```

## Best Practices

1. **Be Specific**: Include concrete examples and exact error messages
2. **Prioritize Workarounds**: Focus on solutions rather than just listing problems
3. **Use Examples**: Provide working query examples
4. **Test Patterns**: Verify your patterns match intended services
5. **Document Fields**: Include field types, formats, and examples
6. **Version Control**: Keep hints files in version control with your projects

## Troubleshooting

### Hints Not Appearing

1. Check file path:
   ```bash
   python odata_mcp.py --verbose --hints-file my-hints.json https://service.com/odata/
   ```

2. Verify JSON syntax:
   ```bash
   python -m json.tool < hints.json
   ```

3. Test pattern matching:
   - Ensure your pattern matches the service URL
   - Try broader patterns like `*service.com*`

### Hints Not Merging

- Check priority values (higher priority overrides lower)
- CLI hints always have highest priority (1000)
- Arrays are combined, objects are overridden

## Python Implementation Details

The Python hint system is implemented in `odata_mcp_lib/hint_manager.py` with the following features:

- **HintManager class**: Main manager for loading and processing hints
- **Pattern matching**: Full regex-based wildcard support
- **Priority merging**: Sophisticated merging algorithm
- **Data classes**: Type-safe hint structures (ServiceHint, FieldHint, etc.)
- **Flexible loading**: Searches multiple default locations for hints.json

## Contributing Hints

If you discover issues with public OData services, consider contributing your hints:

1. Test the service thoroughly
2. Document the issues and workarounds
3. Create a hint entry with clear examples
4. Submit a pull request with your hints

Together we can build a comprehensive knowledge base for OData service quirks and workarounds!