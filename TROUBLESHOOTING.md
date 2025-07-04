# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the OData MCP Bridge.

## Common Issues

### 1. Connection Failures

#### Symptoms
- "Could not fetch metadata" error
- Connection timeout or refused errors
- SSL/TLS certificate errors

#### Solutions

1. **Verify Service URL**
   ```bash
   # Test with curl first
   curl -v https://your-service.com/odata/$metadata
   
   # Use verbose mode for detailed output
   python odata_mcp.py --verbose https://your-service.com/odata/
   ```

2. **Check Authentication**
   ```bash
   # Basic auth
   python odata_mcp.py --user myuser --password mypass https://your-service.com/odata/
   
   # Cookie auth (for SAP systems with SSO)
   python odata_mcp.py --cookie-file cookies.txt https://your-service.com/odata/
   ```

3. **SSL Certificate Issues**
   - For self-signed certificates, you may need to set:
     ```bash
     export PYTHONHTTPSVERIFY=0  # Disable SSL verification (NOT for production!)
     ```

### 2. Tool Generation Issues

#### Symptoms
- No tools appear in MCP client
- Missing entity sets or functions
- "No entity sets were successfully processed" warning

#### Solutions

1. **Check Metadata**
   ```bash
   # Verify metadata is accessible
   curl https://your-service.com/odata/$metadata > metadata.xml
   
   # Use trace mode to see what's being generated
   python odata_mcp.py --trace https://your-service.com/odata/
   ```

2. **Entity Filtering**
   ```bash
   # If too many entities, filter to specific ones
   python odata_mcp.py --entities "Products,Orders" https://your-service.com/odata/
   
   # Use wildcards
   python odata_mcp.py --entities "Product*,Order*" https://your-service.com/odata/
   ```

### 3. SAP-Specific Issues

#### HTTP 501 Not Implemented

**Problem**: Some SAP services return 501 for direct entity access.

**Solution**: Use `$expand` parameter:
```python
# Instead of: get_PurchaseOrderItem(ID='123')
# Use: filter_PurchaseOrderSet($filter="ID eq '123'", $expand="Items")
```

#### Date Format Issues

**Problem**: SAP uses `/Date(milliseconds)/` format.

**Solution**: Legacy date conversion is enabled by default:
```bash
# Disable if causing issues
python odata_mcp.py --no-legacy-dates https://sap-service.com/odata/
```

#### Decimal Field Errors

**Problem**: "Failed to read property 'Amount' at offset" errors.

**Solution**: The bridge automatically converts decimals to strings for SAP compatibility.

### 4. MCP Client Integration

#### Claude Desktop Issues

**Symptoms**: Tools don't appear or validation errors

**Solutions**:

1. **Check Configuration**
   ```json
   {
     "mcpServers": {
       "odata": {
         "command": "python",
         "args": [
           "/path/to/odata_mcp.py",
           "--service",
           "https://your-service.com/odata/"
         ],
         "env": {
           "ODATA_USERNAME": "user",
           "ODATA_PASSWORD": "pass"
         }
       }
     }
   }
   ```

2. **Enable Trace Logging**
   ```bash
   python odata_mcp.py --trace-mcp https://your-service.com/odata/
   # Check logs in /tmp/mcp_trace_*.log (Linux) or %TEMP%\mcp_trace_*.log (Windows)
   ```

### 5. Performance Issues

#### Symptoms
- Slow response times
- Timeouts with large datasets
- Memory issues

#### Solutions

1. **Limit Response Size**
   ```bash
   # Limit items per response
   python odata_mcp.py --max-items 50 https://your-service.com/odata/
   
   # Limit total response size
   python odata_mcp.py --max-response-size 1048576 https://your-service.com/odata/
   ```

2. **Use Selective Queries**
   ```python
   # Use $select to limit fields
   filter_Products($select="ID,Name,Price")
   
   # Use $top for pagination
   filter_Products($top=10, $skip=0)
   ```

### 6. Authentication Problems

#### Cookie Authentication

1. **Export Cookies from Browser**
   - Use browser extension to export cookies in Netscape format
   - Save as `cookies.txt`

2. **Use Cookie File**
   ```bash
   python odata_mcp.py --cookie-file cookies.txt https://your-service.com/odata/
   ```

3. **Direct Cookie String**
   ```bash
   python odata_mcp.py --cookie-string "MYSAPSSO2=abc123; SAP_SESSION=xyz789" https://your-service.com/odata/
   ```

## Debugging Tools

### 1. Verbose Mode

Always start with verbose mode for detailed output:
```bash
python odata_mcp.py --verbose https://your-service.com/odata/
```

### 2. Trace Mode

See all generated tools without starting the server:
```bash
python odata_mcp.py --trace https://your-service.com/odata/
```

### 3. MCP Protocol Tracing

Debug MCP communication issues:
```bash
python odata_mcp.py --trace-mcp https://your-service.com/odata/
```

### 4. Test with Read-Only Mode

Safely explore a service without risk of modifications:
```bash
python odata_mcp.py --read-only https://your-service.com/odata/
```

### 5. Check Service Hints

Get guidance for known problematic services:
```python
# Call odata_service_info tool to see if hints are available
```

## Error Messages

### "FATAL ERROR during initialization"

**Causes**:
- Invalid service URL
- Network connectivity issues
- Authentication failure
- Invalid metadata format

**Debug Steps**:
1. Test URL with curl/browser
2. Check credentials
3. Use --verbose for details
4. Verify metadata format

### "Missing required key parameters"

**Cause**: Entity operation called without required key values

**Solution**: Check entity type definition for required keys:
```python
# Use odata_service_info to see entity structure
# Ensure all key properties are provided
```

### "Response size exceeds maximum allowed"

**Cause**: Response too large for configured limit

**Solution**:
```bash
# Increase limit
python odata_mcp.py --max-response-size 10485760 https://your-service.com/odata/

# Or reduce query scope
filter_LargeEntitySet($top=10, $select="ID,Name")
```

## Platform-Specific Issues

### Windows

- Use forward slashes in paths or escape backslashes
- Set environment variables in the MCP client config
- Trace logs in `%TEMP%\mcp_trace_*.log`

### Linux/WSL

- Ensure Python 3.8+ is installed
- Check file permissions for cookie files
- Trace logs in `/tmp/mcp_trace_*.log`

### macOS

- Similar to Linux
- May need to install certificates: `/Applications/Python*/Install Certificates.command`

## Getting Help

1. **Enable All Debugging**
   ```bash
   python odata_mcp.py --verbose --trace-mcp --verbose-errors https://your-service.com/odata/
   ```

2. **Check Service Hints**
   - Look for `implementation_hints` in service info
   - May contain service-specific workarounds

3. **Report Issues**
   - Include service URL (sanitized)
   - Full error message with --verbose
   - Python version (`python --version`)
   - OData service type (SAP, Microsoft, etc.)

## Quick Diagnostics Checklist

- [ ] Service URL is accessible via browser/curl
- [ ] Metadata endpoint returns valid XML
- [ ] Authentication credentials are correct
- [ ] No firewall/proxy blocking connection
- [ ] Python version 3.8 or higher
- [ ] All required packages installed (`pip install -r requirements.txt`)
- [ ] For SAP: CSRF token handling may be needed
- [ ] For large datasets: pagination parameters used
- [ ] For sensitive services: read-only mode considered