# OAuth 2.0 Authentication Guide for OData MCP

This guide covers OAuth 2.0 authentication implementation in the OData MCP wrapper, including setup, testing, and troubleshooting.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Testing Guide](#testing-guide)
- [Supported Services](#supported-services)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Overview

OAuth 2.0 support was added to enable secure, modern authentication with enterprise OData services. This implementation addresses [GitHub Discussion #9](https://github.com/oisee/odata_mcp/discussions/9) requesting OIDC authentication for SAP backends and other OAuth-protected services.

### Key Features
- ✅ Client Credentials Flow (server-to-server authentication)
- ✅ Automatic token refresh when tokens expire
- ✅ Built-in support for Microsoft Graph API
- ✅ Compatible with SAP OIDC configuration
- ✅ Secure token management with expiration tracking
- ✅ Verbose logging for debugging OAuth issues

### Authentication Priority
The wrapper supports multiple authentication methods with the following priority:
1. **OAuth 2.0** (if credentials provided)
2. **Cookie Authentication** (if cookie file/string provided)
3. **Basic Authentication** (username/password)
4. **Anonymous** (no authentication)

## Architecture

### Components

#### 1. OAuthTokenManager (`odata_mcp_lib/oauth_handler.py`)
Core OAuth implementation managing token lifecycle:
```python
class OAuthTokenManager:
    - __init__(client_id, client_secret, token_url, scope)
    - get_authorization_header() -> Dict[str, str]
    - _get_valid_token() -> str
    - _fetch_token()
    - refresh_access_token()
```

#### 2. OAuthConfig Helper
Provides pre-configured OAuth endpoints:
```python
class OAuthConfig:
    - from_environment() -> Optional[Dict]
    - microsoft_graph(tenant_id) -> Dict
    - sap_oauth(sap_host) -> Dict
```

#### 3. Integration Points
OAuth is integrated throughout the stack:
- **MetadataParser**: Adds OAuth headers when fetching `$metadata`
- **ODataClient**: Includes OAuth headers in all API requests
- **ODataMCPBridge**: Passes OAuth manager to parser and client
- **Main Script**: Handles OAuth CLI arguments and environment variables

## Configuration

### Environment Variables

Create a `.env` file or export these variables:

```bash
# Required OAuth credentials
export OAUTH_CLIENT_ID="your-application-client-id"
export OAUTH_CLIENT_SECRET="your-application-client-secret"
export OAUTH_TOKEN_URL="https://login.microsoftonline.com/tenant/oauth2/v2.0/token"

# Optional scope (defaults vary by service)
export OAUTH_SCOPE="https://graph.microsoft.com/.default"

# Alternative prefixed variables (also supported)
export ODATA_OAUTH_CLIENT_ID="your-client-id"
export ODATA_OAUTH_CLIENT_SECRET="your-secret"
export ODATA_OAUTH_TOKEN_URL="your-token-url"
export ODATA_OAUTH_SCOPE="your-scope"
```

### Command Line Options

```bash
# Full OAuth configuration
python odata_mcp.py \
    --service https://your-service.com/odata/ \
    --oauth-client-id YOUR_CLIENT_ID \
    --oauth-client-secret YOUR_CLIENT_SECRET \
    --oauth-token-url https://oauth.provider.com/token \
    --oauth-scope "scope1 scope2" \
    --verbose

# Microsoft Graph with tenant
python odata_mcp.py \
    --service https://graph.microsoft.com/v1.0/ \
    --oauth-client-id YOUR_CLIENT_ID \
    --oauth-client-secret YOUR_CLIENT_SECRET \
    --oauth-tenant YOUR_TENANT_ID
```

## Testing Guide

### 1. Basic OAuth Functionality Test

Test the OAuth implementation without needing real credentials:

```bash
# Run the test suite with mock OAuth
python test_oauth.py --skip-graph

# Expected output:
# 🚀 OAuth Test Suite
# ⏭️  Skipping Graph API tests
# ✅ OAuth properly failed as expected: Exception
# 📊 Test Results: 1/1 passed
```

### 2. Microsoft Graph API Test

#### Prerequisites
1. Azure AD Application with:
   - Client ID
   - Client Secret
   - Appropriate Graph API permissions

#### Setup Azure AD Application

1. **Create App Registration**:
   ```
   Azure Portal → Azure Active Directory → App registrations → New registration
   - Name: "OData MCP Test App"
   - Supported account types: "Single tenant"
   - Redirect URI: Not needed for client credentials
   ```

2. **Add API Permissions**:
   ```
   API permissions → Add permission → Microsoft Graph → Application permissions
   - User.Read.All (to read users)
   - Group.Read.All (to read groups)
   - Directory.Read.All (for comprehensive testing)
   → Grant admin consent
   ```

3. **Create Client Secret**:
   ```
   Certificates & secrets → New client secret
   - Description: "OData MCP Testing"
   - Expires: 24 months
   - Copy the secret value immediately (shown only once)
   ```

#### Run Graph API Test

```bash
# Set credentials
export OAUTH_CLIENT_ID="your-app-client-id"
export OAUTH_CLIENT_SECRET="your-client-secret"
export OAUTH_TENANT="your-tenant-id"  # or "common"

# Test OAuth token acquisition
python test_oauth.py

# Test with actual Graph service
python odata_mcp.py \
    --service https://graph.microsoft.com/v1.0/ \
    --oauth-client-id $OAUTH_CLIENT_ID \
    --oauth-client-secret $OAUTH_CLIENT_SECRET \
    --oauth-tenant $OAUTH_TENANT \
    --trace

# Verify specific Graph endpoints
python odata_mcp.py \
    --service https://graph.microsoft.com/v1.0/ \
    --oauth-client-id $OAUTH_CLIENT_ID \
    --oauth-client-secret $OAUTH_CLIENT_SECRET \
    --entities "users,groups" \
    --verbose
```

### 3. Public Service Test (Without OAuth)

Verify OAuth doesn't break non-OAuth services:

```bash
# Test Northwind (public, no auth)
python odata_mcp.py \
    --service https://services.odata.org/V2/Northwind/Northwind.svc/ \
    --entities "Products,Categories" \
    --trace

# Should work without any authentication
```

### 4. SAP OAuth Test

For SAP systems with OIDC enabled:

```bash
# SAP OAuth configuration
export OAUTH_CLIENT_ID="sap-client-id"
export OAUTH_CLIENT_SECRET="sap-client-secret"
export OAUTH_TOKEN_URL="https://your-sap.com:8443/sap/bc/sec/oauth2/token"
export OAUTH_SCOPE="odata_read odata_write"

# Test SAP service
python odata_mcp.py \
    --service https://your-sap.com:8443/sap/opu/odata/sap/YOUR_SERVICE/ \
    --verbose
```

### 5. Token Refresh Test

Test automatic token refresh:

```bash
# Create a test script to verify token refresh
cat > test_token_refresh.py << 'EOF'
import time
from odata_mcp_lib.oauth_handler import OAuthTokenManager

# Create manager with short expiry simulation
manager = OAuthTokenManager(
    client_id="test-client",
    client_secret="test-secret",
    token_url="https://example.com/token",
    verbose=True
)

# Simulate expired token
manager._expires_at = time.time() - 100

try:
    # This should trigger token refresh
    headers = manager.get_authorization_header()
    print("Token refresh test completed")
except Exception as e:
    print(f"Expected error (no real endpoint): {e}")
EOF

python test_token_refresh.py
```

## Supported Services

### Microsoft Graph
```bash
# v1.0 endpoint (stable)
--service https://graph.microsoft.com/v1.0/

# Beta endpoint (preview features)
--service https://graph.microsoft.com/beta/

# National clouds
--service https://graph.microsoft.us/v1.0/  # US Government
--service https://graph.microsoft.de/v1.0/  # Germany
--service https://microsoftgraph.chinacloudapi.cn/v1.0/  # China
```

### SAP Systems
```bash
# SAP S/4HANA Cloud
--service https://my-api.s4hana.cloud.sap/sap/opu/odata/sap/API_SERVICE/

# SAP Business Technology Platform
--service https://api.btp.sap.com/odata/v2/service/

# On-premise SAP with OAuth
--service https://sap.company.com:8443/sap/opu/odata/sap/SERVICE/
```

### Custom OAuth Services
Any OData service supporting OAuth 2.0 client credentials flow:
```bash
--oauth-token-url https://auth.custom.com/oauth2/token
--oauth-scope "custom_scope read write"
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Token Acquisition Failed
**Error**: `OAuth token fetch failed: ...`

**Solutions**:
- Verify client ID and secret are correct
- Check token URL is accessible: `curl -I <token_url>`
- Ensure network connectivity and proxy settings
- Verify firewall rules allow HTTPS to token endpoint

**Debug**:
```bash
# Enable verbose logging
python odata_mcp.py --service <url> --oauth-client-id <id> \
    --oauth-client-secret <secret> --verbose

# Test token endpoint directly
curl -X POST <token_url> \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials&client_id=<id>&client_secret=<secret>"
```

#### 2. Invalid Client Credentials
**Error**: `401 Unauthorized` or `invalid_client`

**Solutions**:
- Double-check client ID and secret
- Ensure secret hasn't expired (Azure AD secrets expire)
- Verify app registration is active
- Check tenant ID matches app registration

#### 3. Insufficient Permissions
**Error**: `403 Forbidden` or `insufficient_scope`

**Solutions**:
- Add required API permissions in Azure Portal
- Grant admin consent for permissions
- Verify scope parameter matches granted permissions
- Check application vs delegated permissions

#### 4. Token Expired
**Error**: `401 Token Expired`

**Solutions**:
- Token refresh is automatic, but check:
  - Network connectivity to token endpoint
  - Refresh token (if used) hasn't expired
  - Client credentials still valid

#### 5. Scope Issues
**Error**: `invalid_scope`

**Solutions**:
- Microsoft Graph: Use `https://graph.microsoft.com/.default`
- SAP: Typically `odata_read odata_write`
- Custom: Check service documentation for required scopes

### Debug Mode

Enable comprehensive debugging:

```bash
# Maximum verbosity
python odata_mcp.py \
    --service <service_url> \
    --oauth-client-id <id> \
    --oauth-client-secret <secret> \
    --verbose \
    --trace-mcp \
    --trace

# Check generated headers
python -c "
from odata_mcp_lib.oauth_handler import OAuthTokenManager
manager = OAuthTokenManager(
    'client_id', 'secret', 'token_url', verbose=True
)
print(manager.get_authorization_header())
"
```

## Security Considerations

### Best Practices

1. **Never commit credentials**:
   ```bash
   # Add to .gitignore
   .env
   *.secret
   oauth_config.json
   ```

2. **Use environment variables** instead of command-line arguments:
   ```bash
   # Good (credentials not in shell history)
   export OAUTH_CLIENT_SECRET="secret"
   python odata_mcp.py --service <url>
   
   # Avoid (visible in process list)
   python odata_mcp.py --oauth-client-secret "secret"
   ```

3. **Rotate secrets regularly**:
   - Azure AD: Create new secret before old expires
   - Monitor secret expiration dates
   - Use shortest viable expiration period

4. **Minimize token scope**:
   - Request only necessary permissions
   - Use separate apps for different environments
   - Regular audit of granted permissions

5. **Secure token storage**:
   - Tokens are only stored in memory
   - No persistent token caching implemented
   - Tokens cleared on process exit

### Production Deployment

For production use:

1. **Use managed identities** where possible (Azure):
   ```python
   # Future enhancement: Support managed identity
   from azure.identity import DefaultAzureCredential
   ```

2. **Implement token caching** for performance:
   ```python
   # Planned: Redis-based token cache
   ```

3. **Add retry logic** for token acquisition:
   ```python
   # Current: Single attempt
   # Planned: Exponential backoff retry
   ```

4. **Monitor token metrics**:
   - Token acquisition failures
   - Refresh frequency
   - Expiration patterns

## Verification Checklist

### Implementation Verification

- [x] OAuth token acquisition works
- [x] Tokens are included in HTTP headers
- [x] Token refresh on expiration
- [x] Microsoft Graph endpoint detection
- [x] SAP OAuth configuration support
- [x] Environment variable loading
- [x] Command-line argument parsing
- [x] Verbose logging for debugging
- [x] Backward compatibility maintained
- [x] Error handling for OAuth failures

### Testing Verification

- [x] Unit test for OAuth handler
- [x] Integration test script created
- [x] Mock OAuth test passes
- [x] Non-OAuth services still work
- [x] Documentation complete
- [x] Security considerations documented

## Related Documentation

- [README.md](README.md) - Main documentation with OAuth section
- [COOKIE_AUTH.md](COOKIE_AUTH.md) - Cookie authentication guide
- [test_oauth.py](test_oauth.py) - OAuth test suite
- [GitHub Discussion #9](https://github.com/oisee/odata_mcp/discussions/9) - Original feature request

## Support

For OAuth-related issues:
1. Check this troubleshooting guide
2. Enable verbose mode for debugging
3. Report issues at [GitHub Issues](https://github.com/oisee/odata_mcp/issues)
4. Include sanitized logs (remove secrets)