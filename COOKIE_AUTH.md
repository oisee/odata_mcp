# Cookie Authentication for OData MCP

This document describes the cookie authentication support added to the OData MCP wrapper.

## Overview

The OData MCP wrapper now supports cookie-based authentication in addition to basic authentication. This is particularly useful for:

- Services that use Single Sign-On (SSO)
- SAP systems with MYSAPSSO2 tokens
- Services with complex authentication flows
- Testing with browser-obtained sessions

## Usage

### 1. Cookie File Authentication

Provide a cookie file in Netscape format (as exported by browser extensions):

```bash
python odata_mcp.py --service <service_url> --cookie-file cookie.txt
```

### 2. Cookie String Authentication

Provide cookies directly as a string:

```bash
python odata_mcp.py --service <service_url> --cookie-string "session=abc123; token=xyz789"
```

### 3. Environment Variables

Set cookie authentication via environment variables:

```bash
# Using cookie file
export ODATA_COOKIE_FILE="/path/to/cookie.txt"

# Using cookie string
export ODATA_COOKIE_STRING="session=abc123; token=xyz789"

python odata_mcp.py --service <service_url>
```

## Cookie File Format

The cookie file should be in Netscape format:

```
# Netscape HTTP Cookie File
# This is a comment
.example.com	TRUE	/	FALSE	1234567890	session	abc123
.example.com	TRUE	/	TRUE	1234567890	auth_token	xyz789
```

Or simple key=value format:

```
session=abc123
auth_token=xyz789
MYSAPSSO2=base64encodedtoken
```

## Implementation Details

### Changed Files

1. **odata_mcp.py**
   - Added `--cookie-file` and `--cookie-string` CLI arguments
   - Added cookie parsing functions
   - Added environment variable support for cookies

2. **odata_mcp_lib/client.py**
   - Modified `__init__` to accept Union[Tuple[str, str], Dict[str, str]] for auth
   - Added cookie authentication handling
   - Automatically disables SSL verification for cookie auth

3. **odata_mcp_lib/metadata_parser.py**
   - Similar changes to support cookie authentication

4. **odata_mcp_lib/bridge.py**
   - Updated type hints to support cookie auth

### Authentication Priority

1. CLI arguments (--cookie-file, --cookie-string, --user)
2. Environment variables (ODATA_COOKIE_FILE, ODATA_COOKIE_STRING, ODATA_USER/PASS)
3. .env file variables

### Security Considerations

- Cookie files should be kept secure and not committed to version control
- SSL verification is automatically disabled when using cookies (for internal servers)
- Cookies may expire and need periodic updates

## Testing

Test cookie authentication with:

```bash
# Test if cookies work with the service
python test_cookie_auth.py cookie.txt <service_url>

# Run unit tests
python test_odata_mcp.py
```

## Example

Complete example with SAP system:

```bash
# Export cookies from browser using Cookie-Editor extension
# Save to cookie.txt

# Use with OData MCP
python odata_mcp.py \
  --service "https://sapdev15.redmond.corp.microsoft.com:8422/sap/opu/odata/sap/ZSCR_105_RTS_OD_SRV/" \
  --cookie-file cookie.txt

# The MCP will now use cookie authentication for all OData requests
```

## Troubleshooting

1. **SSL Certificate Errors**: SSL verification is automatically disabled for cookie auth
2. **401 Unauthorized**: Cookies may have expired, re-export from browser
3. **Cookie Format Issues**: Ensure proper Netscape format or use simple key=value format
4. **Missing Cookies**: Check that required cookies (e.g., MYSAPSSO2, SAP_SESSIONID) are present