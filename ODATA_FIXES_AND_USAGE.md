# OData MCP Fixes and Usage Guide

This document explains the fixes applied to the OData MCP wrapper and provides guidance on proper usage with SAP OData services.

## Issues Fixed

### 1. URL Encoding for Special Characters in Key Values

**Problem**: SAP program names like `/IWFND/SUTIL_GW_CLIENT` contain forward slashes that need to be URL encoded when used in OData URLs.

**Fix**: Added proper URL encoding in the `_build_key_string` method in `client.py`:

```python
# Before
key_value_str = str(key_value).replace("'", "''")
return f"('{key_value_str}')"

# After  
encoded_value = quote(str(key_value), safe='')
return f"('{encoded_value}')"
```

**Result**: Forward slashes are now properly encoded as `%2F`:
- `/IWFND/SUTIL_GW_CLIENT` → `('%2FIWFND%2FSUTIL_GW_CLIENT')`

### 2. Search Functionality Limitations

**Problem**: The `$search` system query option is not supported by many SAP OData services.

**Solution**: Use OData v2 filter expressions instead of `$search`.

### 3. Filter Function Support

**Problem**: Modern OData functions like `contains()` are not supported in OData v2.

**Solution**: Use OData v2 compatible functions like `substringof()`.

## Correct OData v2 Filter Syntax

### Substring Search (instead of contains)

```odata
# ❌ Not supported in OData v2
filter: "contains(Class, 'REST_HTTP_CLIENT')"

# ✅ Correct OData v2 syntax
filter: "substringof('REST_HTTP_CLIENT', Class) eq true"
```

### Common Search Patterns

#### Find classes containing specific text:
```odata
# Find classes with "REST" in the name
filter: "substringof('REST', Class) eq true"

# Find classes with "HTTP" in title or class name
filter: "substringof('HTTP', Class) eq true or substringof('HTTP', Title) eq true"
```

#### Find classes in specific packages:
```odata
# Find classes in /IWFND package
filter: "startswith(Class, '/IWFND') eq true"

# Find classes in /IWCOR package  
filter: "startswith(Class, '/IWCOR') eq true"
```

#### Find classes with specific endings:
```odata
# Find client classes
filter: "endswith(Class, '_CLIENT') eq true"

# Find test classes
filter: "substringof('TEST', Class) eq true"
```

#### Complex filters:
```odata
# Find Gateway-related HTTP clients
filter: "substringof('GW', Class) eq true and substringof('HTTP', Class) eq true"

# Find classes in multiple packages
filter: "startswith(Class, '/IWFND') eq true or startswith(Class, '/IWCOR') eq true"
```

## Updated Usage Examples

### Searching for SAP Classes

```bash
# ✅ Correct way to find REST HTTP clients
abap_vibe_code:filter_CLASSSet_for_Z000 (MCP)(filter: "substringof('REST_HTTP_CLIENT', Class) eq true", select: "Class,Title", top: 10)

# ✅ Find Gateway client classes
abap_vibe_code:filter_CLASSSet_for_Z000 (MCP)(filter: "substringof('GW_CLIENT', Class) eq true", select: "Class,Title", top: 10)

# ✅ Find classes in IWFND package
abap_vibe_code:filter_CLASSSet_for_Z000 (MCP)(filter: "startswith(Class, '/IWFND') eq true", select: "Class,Title", top: 15)
```

### Getting Specific Programs

```bash
# ✅ Now works with special characters
abap_vibe_code:get_PROGRAMSet_for_Z000 (MCP)(Program: "/IWFND/SUTIL_GW_CLIENT")

# ✅ Works with any SAP program name
abap_vibe_code:get_PROGRAMSet_for_Z000 (MCP)(Program: "/UI5/FLP_LAUNCHER")
```

### Finding Functions

```bash
# ✅ Find functions containing specific text
abap_vibe_code:filter_FUNCTIONSet_for_Z000 (MCP)(filter: "substringof('IWFND', Function) eq true", select: "Function,Title", top: 15)

# ✅ Find HTTP-related functions
abap_vibe_code:filter_FUNCTIONSet_for_Z000 (MCP)(filter: "substringof('HTTP', Function) eq true or substringof('HTTP', Title) eq true", select: "Function,Title", top: 10)
```

## OData v2 Function Reference

### String Functions
- `substringof('text', field) eq true` - Check if field contains text
- `startswith(field, 'text') eq true` - Check if field starts with text  
- `endswith(field, 'text') eq true` - Check if field ends with text
- `length(field) gt 10` - Check field length
- `tolower(field) eq 'text'` - Case-insensitive comparison
- `toupper(field) eq 'TEXT'` - Convert to uppercase

### Logical Operators
- `and` - Logical AND
- `or` - Logical OR  
- `not` - Logical NOT

### Comparison Operators
- `eq` - Equal
- `ne` - Not equal
- `gt` - Greater than
- `ge` - Greater than or equal
- `lt` - Less than
- `le` - Less than or equal

## Testing

Run the test suites to verify the fixes:

```bash
# Test URL encoding fix
python test_url_encoding_fix.py

# Test comprehensive OData functionality
python test_odata_functionality.py

# Run all tests
python test_odata_mcp.py
```

## Migration Guide

If you were using the old incorrect syntax, here's how to migrate:

### Search Operations
```bash
# Old (doesn't work)
abap_vibe_code:search_CLASSSet_for_Z000 (MCP)(search_term: "/IWCOR/CL_REST_HTTP_CLIENT")

# New (works)
abap_vibe_code:filter_CLASSSet_for_Z000 (MCP)(filter: "substringof('REST_HTTP_CLIENT', Class) eq true")
```

### Filter Operations  
```bash
# Old (doesn't work)
abap_vibe_code:filter_CLASSSet_for_Z000 (MCP)(filter: "contains(Class, 'REST_HTTP_CLIENT')")

# New (works)
abap_vibe_code:filter_CLASSSet_for_Z000 (MCP)(filter: "substringof('REST_HTTP_CLIENT', Class) eq true")
```

### Get Operations with Special Characters
```bash
# Old (would fail)
abap_vibe_code:get_PROGRAMSet_for_Z000 (MCP)(Program: "/IWFND/SUTIL_GW_CLIENT")

# New (works - same syntax, but now with proper URL encoding)
abap_vibe_code:get_PROGRAMSet_for_Z000 (MCP)(Program: "/IWFND/SUTIL_GW_CLIENT")
```

## Best Practices

1. **Always use OData v2 compatible filter syntax** with SAP systems
2. **Use `substringof()` instead of `contains()`** for text search
3. **Use `startswith()` and `endswith()`** for prefix/suffix matching  
4. **Combine multiple conditions** with `and`/`or` operators
5. **Use `select` parameter** to limit returned fields and improve performance
6. **Use `top` parameter** to limit the number of results

## Performance Tips

- Use specific filters to reduce result set size
- Use `select` to only return needed fields
- Use `top` to limit results (default is usually 1000)
- Consider using `$skip` for pagination when needed

## Common SAP Package Prefixes

When searching for SAP classes, programs, or functions, these prefixes are common:

- `/IWFND/` - Gateway Foundation 
- `/IWCOR/` - Gateway Core
- `/IWBEP/` - Gateway Business Entity Provider
- `/UI5/` - UI5 applications
- `/SAP/BC/` - SAP Business Connector
- `CL_` - Class prefix
- `IF_` - Interface prefix
- `Z*` or `Y*` - Customer namespace