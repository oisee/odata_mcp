# Security Policy

## Overview

The OData MCP Bridge handles sensitive data including authentication credentials and business data. This document outlines security considerations and best practices.

## Credential Security

### Never Commit Credentials

**IMPORTANT**: Never commit files containing real credentials to version control.

Files to exclude:
- `.env` files with passwords
- Cookie files (`*.txt`, `*.cookies`)
- Configuration files with embedded credentials
- Log files that may contain sensitive data

### Secure Credential Storage

1. **Environment Variables**
   ```bash
   # Use environment variables for credentials
   export ODATA_USERNAME=myuser
   export ODATA_PASSWORD=mypass
   python odata_mcp.py https://service.com/odata/
   ```

2. **Secure Cookie Files**
   ```bash
   # Set appropriate permissions
   chmod 600 cookies.txt
   
   # Use cookie file
   python odata_mcp.py --cookie-file cookies.txt https://service.com/odata/
   ```

3. **MCP Client Configuration**
   ```json
   {
     "mcpServers": {
       "odata": {
         "command": "python",
         "args": ["/path/to/odata_mcp.py"],
         "env": {
           "ODATA_USERNAME": "user",
           "ODATA_PASSWORD": "pass"
         }
       }
     }
   }
   ```

## Network Security

### SSL/TLS Verification

Always use HTTPS for OData services:
```bash
# Good
python odata_mcp.py https://secure-service.com/odata/

# Avoid
python odata_mcp.py http://insecure-service.com/odata/
```

### Proxy Considerations

When using proxies, ensure they're trusted:
```bash
export HTTPS_PROXY=https://trusted-proxy.company.com:8080
python odata_mcp.py https://service.com/odata/
```

## Access Control

### Read-Only Mode

Use read-only mode for exploration and testing:
```bash
# Completely hide modifying operations
python odata_mcp.py --read-only https://production.com/odata/

# Allow functions but hide CRUD
python odata_mcp.py --read-only-but-functions https://production.com/odata/
```

### Entity Filtering

Limit exposure to specific entities:
```bash
# Only expose specific entities
python odata_mcp.py --entities "PublicData,Reports" https://service.com/odata/

# Exclude sensitive entities
python odata_mcp.py --entities "Products,Orders" https://service.com/odata/
```

## Data Protection

### Response Size Limits

Prevent excessive data exposure:
```bash
# Limit response size
python odata_mcp.py --max-response-size 1048576 --max-items 50 https://service.com/odata/
```

### Metadata Filtering

Control metadata exposure:
```bash
# Exclude metadata from responses
python odata_mcp.py https://service.com/odata/  # metadata excluded by default

# Include metadata (only if needed)
python odata_mcp.py --response-metadata https://service.com/odata/
```

## Logging and Debugging

### Trace Logs

Be careful with trace logs as they may contain sensitive data:

```bash
# MCP trace logs may contain credentials and data
python odata_mcp.py --trace-mcp https://service.com/odata/

# Clean up trace logs after debugging
rm /tmp/mcp_trace_*.log  # Linux
del %TEMP%\mcp_trace_*.log  # Windows
```

### Verbose Output

Verbose mode may expose sensitive information:
```bash
# Use carefully in production
python odata_mcp.py --verbose https://service.com/odata/
```

## Best Practices

### Development vs Production

1. **Development**
   - Use test/sandbox OData services
   - Read-only access to production data
   - Separate credentials for dev/test

2. **Production**
   - Minimal permissions (principle of least privilege)
   - Read-only mode where possible
   - Entity filtering to limit exposure
   - Regular credential rotation

### Authentication Methods

1. **Basic Authentication**
   - Use HTTPS always
   - Consider token-based auth if available
   - Rotate passwords regularly

2. **Cookie Authentication**
   - Secure cookie file permissions (600)
   - Don't share cookie files
   - Regenerate cookies periodically

### Service Account Guidelines

- Create dedicated service accounts for MCP
- Grant minimal required permissions
- Use read-only accounts when possible
- Monitor service account usage
- Implement IP whitelisting if supported

## Security Checklist

Before deploying:

- [ ] No credentials in source code
- [ ] `.gitignore` includes sensitive files
- [ ] Using HTTPS for all connections
- [ ] Appropriate file permissions set
- [ ] Read-only mode enabled for production
- [ ] Entity filtering configured
- [ ] Response size limits set
- [ ] Trace logging disabled
- [ ] Service account has minimal permissions
- [ ] Regular security reviews scheduled

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** create a public issue
2. Email security concerns to: [security@example.com]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Compliance Considerations

When handling sensitive data:

- Ensure compliance with data protection regulations (GDPR, CCPA, etc.)
- Implement audit logging if required
- Consider data residency requirements
- Review organizational security policies
- Implement data retention policies

## Transport Security

### HTTP/SSE Transport Warning

The HTTP transport does not include authentication:

```bash
# Only use on trusted networks
python odata_mcp.py --transport http --http-addr 127.0.0.1:8080 https://service.com/odata/

# Never expose to internet without additional security
# BAD: python odata_mcp.py --transport http --http-addr 0.0.0.0:8080
```

Consider:
- Using reverse proxy with authentication
- Implementing firewall rules
- Using VPN for remote access
- Keeping HTTP transport localhost-only

## Updates and Patches

- Keep Python and dependencies updated
- Monitor for security advisories
- Test updates in non-production first
- Review changelog for security fixes