# OData MCP Implementation Guide

This guide provides a comprehensive blueprint for reimplementing the OData MCP wrapper in Go or any other language. It covers architectural decisions, algorithms, patterns, and practical considerations learned from the Python implementation.

## Table of Contents

1. [Overview](#overview)
2. [Core Architecture](#core-architecture)
3. [Component Implementation Guide](#component-implementation-guide)
4. [Key Algorithms](#key-algorithms)
5. [MCP Protocol Integration](#mcp-protocol-integration)
6. [Error Handling Strategy](#error-handling-strategy)
7. [Performance Optimizations](#performance-optimizations)
8. [Testing Approach](#testing-approach)
9. [Language-Specific Considerations](#language-specific-considerations)

## Overview

The OData MCP wrapper acts as a bridge between the Model Context Protocol (MCP) and OData services. It dynamically generates tools based on OData metadata, handling authentication, CSRF tokens, and data transformations.

### Key Design Principles

1. **Stateless Operation**: Each request is independent
2. **Dynamic Tool Generation**: Tools created from metadata at runtime
3. **Type Safety**: Strong typing throughout the pipeline
4. **Error Resilience**: Graceful degradation and clear error messages
5. **Performance Optimization**: Response limiting, GUID optimization
6. **Extensibility**: Modular design for easy enhancement

## Core Architecture

### Component Diagram

```
┌─────────────────┐
│   CLI Entry     │
│  (odata_mcp)    │
└────────┬────────┘
         │
┌────────▼────────┐
│  MCP Bridge     │ ◄── Main orchestrator
│ (ODataMCPBridge)│
└────────┬────────┘
         │
    ┌────┴────┬─────────┬──────────┬───────────┬──────────┐
    │         │         │          │           │          │
┌───▼──┐ ┌───▼───┐ ┌───▼───┐ ┌────▼────┐ ┌───▼───┐ ┌────▼────┐
│Parser│ │Client │ │Models │ │Constants│ │ GUID  │ │  Name   │
│      │ │       │ │       │ │         │ │Handler│ │Shortener│
└──────┘ └───────┘ └───────┘ └─────────┘ └───────┘ └─────────┘
```

### Data Flow

1. **Initialization**: Parse metadata → Build entity models → Generate tools
2. **Request Processing**: MCP request → Tool execution → OData call → Response transformation
3. **Response Flow**: OData response → Type conversion → GUID optimization → MCP response

## Component Implementation Guide

### 1. Metadata Parser (`metadata_parser.py`)

**Purpose**: Parse OData $metadata XML and extract entity definitions, relationships, and function imports.

**Implementation Requirements**:

```go
// Go interface example
type MetadataParser interface {
    Parse() (*ServiceMetadata, error)
    fetchMetadata() ([]byte, error)
    parseEntityTypes(xml []byte) (map[string]*EntityType, error)
    parseAssociations(xml []byte) ([]Association, error)
    parseFunctionImports(xml []byte) ([]FunctionImport, error)
}

type ServiceMetadata struct {
    ServiceURL    string
    EntityTypes   map[string]*EntityType
    EntitySets    map[string]*EntitySet
    Associations  []Association
    FunctionImports []FunctionImport
}
```

**Key Algorithms**:

1. **XML Namespace Handling**:
   - Extract namespace from root element
   - Handle both OData v3 and v4 namespaces
   - Build namespace map for XPath queries

2. **Entity Type Parsing**:
   ```python
   # Pseudocode for entity type extraction
   for each EntityType in Schema:
       entity = new EntityType(name, namespace)
       for each Property:
           if Property is NavigationProperty:
               entity.addNavigation(name, target, multiplicity)
           else:
               entity.addProperty(name, type, nullable, key)
       store entity in map
   ```

3. **Key Property Detection**:
   - Check for Key elements within EntityType
   - Mark properties as keys
   - Handle composite keys

### 2. OData Client (`client.py`)

**Purpose**: Execute OData operations with authentication, CSRF handling, and response processing.

**Implementation Requirements**:

```go
type ODataClient interface {
    // Entity operations
    GetEntity(entitySet string, key string, params QueryParams) (interface{}, error)
    CreateEntity(entitySet string, data map[string]interface{}) (interface{}, error)
    UpdateEntity(entitySet string, key string, data map[string]interface{}) error
    DeleteEntity(entitySet string, key string) error
    
    // Query operations
    QueryEntities(entitySet string, params QueryParams) (*QueryResult, error)
    CountEntities(entitySet string, filter string) (int, error)
    
    // Function imports
    CallFunction(name string, params map[string]interface{}) (interface{}, error)
}
```

**Critical Implementation Details**:

1. **CSRF Token Management**:
   ```go
   // Algorithm for CSRF token handling
   func (c *Client) ensureCSRFToken() error {
       if c.csrfToken != "" {
           return nil
       }
       
       // Fetch token with HEAD request
       resp, err := c.httpClient.Head(c.serviceURL)
       if err != nil {
           return err
       }
       
       token := resp.Header.Get("X-CSRF-Token")
       if token != "" {
           c.csrfToken = token
           c.csrfCookies = resp.Cookies()
       }
       return nil
   }
   ```

2. **Authentication Handling**:
   - Support both basic auth (username/password) and cookie auth
   - For cookie auth, automatically disable SSL verification
   - Maintain session cookies across requests

3. **Response Processing**:
   ```go
   // Handle OData response format
   type ODataResponse struct {
       D struct {
           Results []interface{} `json:"results"`
           Count   string        `json:"__count"`
           Next    string        `json:"__next"`
       } `json:"d"`
   }
   ```

### 3. GUID Handler (`guid_handler.py`)

**Purpose**: Optimize GUID handling by converting between base64 and standard formats.

**Implementation Algorithm**:

```go
func OptimizeGUIDs(data interface{}) interface{} {
    switch v := data.(type) {
    case map[string]interface{}:
        // Check if it's a GUID structure
        if isGUIDStructure(v) {
            return convertGUIDToBase64(v)
        }
        // Recursively process map
        for key, value := range v {
            v[key] = OptimizeGUIDs(value)
        }
        return v
    case []interface{}:
        // Process array elements
        for i, item := range v {
            v[i] = OptimizeGUIDs(item)
        }
        return v
    case string:
        // Try to parse as base64 GUID
        if guid, ok := parseBase64GUID(v); ok {
            return formatStandardGUID(guid)
        }
        return v
    default:
        return v
    }
}

func isGUIDStructure(m map[string]interface{}) bool {
    // Check for __metadata.type ending with "Edm.Guid"
    if metadata, ok := m["__metadata"].(map[string]interface{}); ok {
        if typeStr, ok := metadata["type"].(string); ok {
            return strings.HasSuffix(typeStr, "Edm.Guid")
        }
    }
    return false
}
```

### 4. Name Shortener (`name_shortener.py`)

**Purpose**: Create concise, meaningful tool names from entity names.

**Key Algorithms**:

1. **Domain Keyword Mapping**:
   ```go
   var domainKeywords = map[string]string{
       "SCREENING": "Scrn",
       "ADDRESS": "Addr",
       "INVESTIGATION": "Inv",
       "BUSINESS": "Biz",
       // ... more mappings
   }
   ```

2. **Progressive Shortening Algorithm**:
   ```go
   func ShortenEntityName(name string, targetLength int) string {
       // Stage 1: Tokenization
       tokens := tokenize(name) // Split on _, -, ., space
       
       // Stage 2: Find longest meaningful token
       longestToken := findLongestMeaningfulToken(tokens)
       
       // Stage 3: CamelCase decomposition
       words := decomposeCamelCase(longestToken)
       
       // Stage 4: Semantic filtering
       filtered := filterGenericWords(words)
       
       // Stage 5: Progressive reduction
       result := progressiveWordReduction(filtered, targetLength)
       
       // Stage 6: Vowel removal if still too long
       if len(result) > targetLength {
           result = removeVowels(result)
       }
       
       return result
   }
   ```

### 5. MCP Bridge (`bridge.py`)

**Purpose**: Orchestrate tool generation and handle MCP protocol communication.

**Tool Generation Pattern**:

```go
func (b *Bridge) generateToolsForEntity(entitySet *EntitySet) {
    entityName := entitySet.Name
    
    // Generate standard CRUD tools
    tools := []ToolDefinition{
        {
            Name: fmt.Sprintf("filter_%s", entityName),
            Description: fmt.Sprintf("Query and filter %s entities", entityName),
            Parameters: generateFilterParameters(),
            Handler: b.createFilterHandler(entitySet),
        },
        {
            Name: fmt.Sprintf("get_%s", entityName),
            Description: fmt.Sprintf("Get a single %s entity by key", entityName),
            Parameters: generateGetParameters(entitySet),
            Handler: b.createGetHandler(entitySet),
        },
        // ... more tools
    }
    
    // Register tools with MCP
    for _, tool := range tools {
        b.mcp.RegisterTool(tool)
    }
}
```

## Key Algorithms

### 1. Dynamic Parameter Generation

```go
func generateParametersFromProperties(props []Property) []Parameter {
    params := []Parameter{}
    
    for _, prop := range props {
        param := Parameter{
            Name:        prop.Name,
            Type:        mapODataTypeToLanguageType(prop.Type),
            Required:    prop.IsKey || !prop.Nullable,
            Description: generatePropertyDescription(prop),
        }
        
        // Handle special types
        if prop.Type == "Edm.DateTime" {
            param.Format = "date-time"
        }
        
        params = append(params, param)
    }
    
    return params
}
```

### 2. OData Query Building

```go
func buildODataQuery(params map[string]interface{}) string {
    query := url.Values{}
    
    // Standard OData parameters
    if filter, ok := params["filter"].(string); ok {
        query.Set("$filter", filter)
    }
    if orderby, ok := params["orderby"].(string); ok {
        query.Set("$orderby", orderby)
    }
    if top, ok := params["top"].(int); ok {
        query.Set("$top", strconv.Itoa(top))
    }
    if skip, ok := params["skip"].(int); ok {
        query.Set("$skip", strconv.Itoa(skip))
    }
    
    // Handle select with response optimization
    if selectFields, ok := params["select"].(string); ok {
        query.Set("$select", selectFields)
    } else {
        // Auto-select non-navigation properties
        query.Set("$select", generateDefaultSelect(entityType))
    }
    
    return query.Encode()
}
```

### 3. Error Response Parsing

```go
func parseODataError(respBody []byte) error {
    // Try OData v3 format
    var v3Error struct {
        Error struct {
            Code    string `json:"code"`
            Message struct {
                Value string `json:"value"`
            } `json:"message"`
        } `json:"error"`
    }
    
    if err := json.Unmarshal(respBody, &v3Error); err == nil && v3Error.Error.Code != "" {
        return fmt.Errorf("OData error %s: %s", v3Error.Error.Code, v3Error.Error.Message.Value)
    }
    
    // Try OData v4 format
    var v4Error struct {
        Error struct {
            Code    string `json:"code"`
            Message string `json:"message"`
        } `json:"error"`
    }
    
    if err := json.Unmarshal(respBody, &v4Error); err == nil && v4Error.Error.Code != "" {
        return fmt.Errorf("OData error %s: %s", v4Error.Error.Code, v4Error.Error.Message)
    }
    
    // Fallback to raw error
    return fmt.Errorf("OData error: %s", string(respBody))
}
```

## MCP Protocol Integration

### Tool Registration

```go
type MCPTool struct {
    Name        string
    Description string
    InputSchema json.RawMessage
    Handler     func(params json.RawMessage) (json.RawMessage, error)
}

func (b *Bridge) registerWithMCP() {
    // Register service info tool
    b.mcp.RegisterTool(MCPTool{
        Name:        "odata_service_info",
        Description: "Get information about the OData service",
        InputSchema: json.RawMessage(`{"type": "object", "properties": {}}`),
        Handler:     b.handleServiceInfo,
    })
    
    // Register entity tools
    for _, entitySet := range b.metadata.EntitySets {
        b.generateToolsForEntity(entitySet)
    }
}
```

### Request/Response Handling

```go
func (b *Bridge) handleMCPRequest(request MCPRequest) MCPResponse {
    switch request.Method {
    case "tools/list":
        return b.listTools()
    case "tools/call":
        return b.callTool(request.Params)
    default:
        return MCPResponse{
            Error: &MCPError{
                Code:    -32601,
                Message: "Method not found",
            },
        }
    }
}
```

## Error Handling Strategy

### Error Categories

1. **Network Errors**: Connection failures, timeouts
2. **Authentication Errors**: 401/403 responses
3. **OData Errors**: Business logic violations, validation failures
4. **Protocol Errors**: Malformed requests, unsupported operations
5. **System Errors**: Memory issues, file I/O problems

### Error Response Format

```go
type ErrorResponse struct {
    Error struct {
        Type    string `json:"type"`    // network, auth, odata, protocol, system
        Code    string `json:"code"`    // HTTP status or OData error code
        Message string `json:"message"` // Human-readable message
        Details interface{} `json:"details,omitempty"` // Additional context
    } `json:"error"`
}
```

## Performance Optimizations

### 1. Response Size Limiting

```go
const (
    MaxResponseItems = 1000
    MaxFieldLength = 50000 // Characters
)

func optimizeResponse(data interface{}) interface{} {
    // Limit array sizes
    if arr, ok := data.([]interface{}); ok && len(arr) > MaxResponseItems {
        return arr[:MaxResponseItems]
    }
    
    // Truncate large strings
    if str, ok := data.(string); ok && len(str) > MaxFieldLength {
        return str[:MaxFieldLength] + "... (truncated)"
    }
    
    return data
}
```

### 2. Selective Field Retrieval

```go
func generateDefaultSelect(entityType *EntityType) string {
    fields := []string{}
    
    for _, prop := range entityType.Properties {
        // Skip navigation properties and large fields
        if !prop.IsNavigation && !isLargeFieldType(prop.Type) {
            fields = append(fields, prop.Name)
        }
    }
    
    return strings.Join(fields, ",")
}
```

### 3. Connection Pooling

```go
func createHTTPClient() *http.Client {
    transport := &http.Transport{
        MaxIdleConns:        10,
        MaxIdleConnsPerHost: 5,
        IdleConnTimeout:     90 * time.Second,
        DisableCompression:  false,
    }
    
    return &http.Client{
        Transport: transport,
        Timeout:   30 * time.Second,
    }
}
```

## Testing Approach

### Unit Testing Strategy

```go
// Test metadata parsing
func TestMetadataParser(t *testing.T) {
    parser := NewMetadataParser(mockServiceURL, mockAuth)
    parser.httpClient = mockHTTPClient // Inject mock
    
    metadata, err := parser.Parse()
    assert.NoError(t, err)
    assert.NotNil(t, metadata)
    assert.Len(t, metadata.EntitySets, expectedCount)
}

// Test GUID optimization
func TestGUIDOptimization(t *testing.T) {
    testCases := []struct {
        name     string
        input    interface{}
        expected interface{}
    }{
        {
            name:     "Base64 to standard",
            input:    "AQIDBAUGAAAAAAAAAAAAAAAAAA==",
            expected: "01020304-0506-0000-0000-000000000000",
        },
        // More test cases...
    }
    
    for _, tc := range testCases {
        t.Run(tc.name, func(t *testing.T) {
            result := OptimizeGUIDs(tc.input)
            assert.Equal(t, tc.expected, result)
        })
    }
}
```

### Integration Testing

```go
// Test with real OData service
func TestIntegration(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping integration test")
    }
    
    bridge := NewBridge(testServiceURL, testAuth)
    
    // Test tool generation
    tools := bridge.ListTools()
    assert.NotEmpty(t, tools)
    
    // Test entity query
    result, err := bridge.CallTool("filter_Products", map[string]interface{}{
        "filter": "Price gt 10",
        "top":    5,
    })
    assert.NoError(t, err)
    assert.NotNil(t, result)
}
```

## Language-Specific Considerations

### Go Implementation

1. **Type System**:
   - Use interfaces for flexibility
   - Leverage struct tags for JSON marshaling
   - Use type assertions carefully with OData dynamic responses

2. **Concurrency**:
   - Use goroutines for parallel metadata parsing
   - Implement proper context handling for cancellation
   - Use sync.Once for one-time initialization

3. **Error Handling**:
   - Return explicit errors, not panic
   - Use error wrapping for context
   - Implement custom error types

### Python to Go Migration Checklist

1. **Replace dynamic typing**:
   - Python: `auth: Union[Tuple[str, str], Dict[str, str]]`
   - Go: Create AuthConfig interface with BasicAuth and CookieAuth implementations

2. **Handle JSON unmarshaling**:
   - Python: Direct dictionary access
   - Go: Define structs or use map[string]interface{} with type assertions

3. **Async to sync/concurrent**:
   - Python: `async def` with asyncio
   - Go: Regular functions with goroutines where beneficial

4. **Package structure**:
   ```
   odata-mcp/
   ├── cmd/
   │   └── odata-mcp/
   │       └── main.go
   ├── internal/
   │   ├── bridge/
   │   ├── client/
   │   ├── parser/
   │   ├── models/
   │   ├── guid/
   │   └── shortener/
   ├── pkg/
   │   └── mcp/
   ├── go.mod
   └── go.sum
   ```

### General Implementation Tips

1. **Configuration Management**:
   - Support environment variables
   - Allow CLI flag overrides
   - Validate configuration early

2. **Logging Strategy**:
   - Use structured logging
   - Different log levels for different components
   - Include context (entity names, operation types)

3. **Security Considerations**:
   - Never log credentials
   - Sanitize error messages
   - Validate all inputs
   - Use secure defaults

4. **Extensibility Points**:
   - Custom authentication providers
   - Response transformers
   - Tool name generators
   - Error handlers

## Example Implementation Flow

Here's a complete example of handling a filter request:

```go
// 1. MCP receives request
request := MCPRequest{
    Method: "tools/call",
    Params: {
        Name: "filter_Products",
        Arguments: {
            "filter": "Price gt 20",
            "orderby": "Name",
            "top": 10
        }
    }
}

// 2. Bridge routes to handler
func (b *Bridge) handleFilterProducts(args map[string]interface{}) (interface{}, error) {
    // 3. Build OData query
    query := buildODataQuery(args)
    
    // 4. Execute request
    response, err := b.client.QueryEntities("Products", query)
    if err != nil {
        return nil, fmt.Errorf("query failed: %w", err)
    }
    
    // 5. Optimize response
    optimized := b.optimizeResponse(response)
    
    // 6. Return formatted result
    return map[string]interface{}{
        "entities": optimized.Results,
        "count":    len(optimized.Results),
        "hasMore":  optimized.NextLink != "",
    }, nil
}
```

## Conclusion

This implementation guide provides the blueprint for recreating the OData MCP wrapper in any language. The key is maintaining the architectural principles while adapting to language-specific idioms and capabilities. Focus on modularity, error handling, and performance optimization to create a robust implementation.