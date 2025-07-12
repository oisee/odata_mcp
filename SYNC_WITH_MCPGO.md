# Sync with Go Implementation

This document tracks changes made to the Go implementation that need to be ported to the Python implementation.

## Recent Changes (July 2025)

### 1. URL Encoding Fix for OData Filters (Commit: 600e8ca)

**Issue**: OData servers (especially SAP CAP backends) don't accept `+` for spaces in URL parameters. They require `%20` according to RFC 3986.

**Fix**: Replace `+` with `%20` in all URL query parameters.

**Implementation**:
```go
// Helper function to encode query parameters properly
func encodeQueryParams(params url.Values) string {
    encoded := params.Encode()
    // Replace '+' with '%20' for OData compatibility
    return strings.ReplaceAll(encoded, "+", "%20")
}
```

**Python equivalent needed**:
```python
# In Python, after using urllib.parse.urlencode()
def encode_query_params(params):
    encoded = urllib.parse.urlencode(params)
    # Replace '+' with '%20' for OData compatibility
    return encoded.replace('+', '%20')
```

**Tests to update**: 
- Change expected filter encodings from `Program+eq+%27TEST%27` to `Program%20eq%20%27TEST%27`

### 2. HTTP/SSE Security Restrictions (Commit: 1caf20f)

**Issue**: HTTP/SSE transport has no authentication and was bindable to all network interfaces by default - major security risk!

**Changes**:
1. **Default binding changed**: From `:8080` (all interfaces) to `localhost:8080` (localhost only)
2. **Added localhost validation**: Refuses to start on non-localhost addresses unless explicitly allowed
3. **Added expert flag**: `--i-am-security-expert-i-know-what-i-am-doing` required for network exposure
4. **Security warnings**: Clear warnings when attempting unsafe configurations

**Implementation**:
```go
// Check if address is localhost-only
func isLocalhostAddr(addr string) bool {
    if strings.HasPrefix(addr, ":") {
        return false  // ":8080" binds to all interfaces
    }
    
    host := addr
    if idx := strings.LastIndex(addr, ":"); idx != -1 {
        host = addr[:idx]
        host = strings.Trim(host, "[]")  // Handle IPv6 [::1]
    }
    
    return host == "localhost" || 
           host == "127.0.0.1" || 
           host == "::1" || 
           host == ""  // empty defaults to localhost
}
```

**Python equivalent needed**:
```python
def is_localhost_addr(addr: str) -> bool:
    """Check if address is localhost-only"""
    if addr.startswith(":"):
        return False  # ":8080" binds to all interfaces
    
    # Extract host part
    if ":" in addr:
        host = addr.rsplit(":", 1)[0]
        # Handle IPv6 addresses like [::1]
        host = host.strip("[]")
    else:
        host = addr
    
    return host in ("localhost", "127.0.0.1", "::1", "")
```

**Security checks to add**:
```python
if transport == "http":
    if not expert_mode and not is_localhost_addr(http_addr):
        print("\n⚠️  SECURITY WARNING ⚠️")
        print("HTTP/SSE transport is UNPROTECTED - no authentication!")
        print(f"Current address '{http_addr}' is not localhost.")
        print("\nTo bind to localhost, use:")
        print("  --http-addr localhost:8080")
        print("  --http-addr 127.0.0.1:8080")
        print("\nIf you REALLY need network exposure, use:")
        print("  --i-am-security-expert-i-know-what-i-am-doing")
        sys.exit(1)
```

**New CLI arguments**:
- `--http-addr`: Default changed from `:8080` to `localhost:8080`
- `--i-am-security-expert-i-know-what-i-am-doing`: Boolean flag to allow non-localhost binding

**Documentation updates**:
- Add security warnings about HTTP/SSE transport
- Update examples to use localhost addresses
- Add Skynet disclaimer about the dangers of exposed MCP services

## Summary

Both changes are critical for security and compatibility:
1. URL encoding fix ensures compatibility with all OData servers
2. HTTP security restrictions prevent accidental exposure of unauthenticated services

The Python implementation should prioritize these changes, especially the security restrictions for HTTP transport.