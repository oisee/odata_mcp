# OData to MCP Bridge - Visual Architecture

## System Architecture Diagram

```mermaid
graph TB
    subgraph "AI Assistant"
        A[MCP Client]
    end
    
    subgraph "OData MCP Bridge"
        B[FastMCP Server]
        C[Tool Registry]
        D[ODataMCPBridge]
        E[MetadataParser]
        F[ODataClient]
        G[GUIDHandler]
        
        B --> C
        C --> D
        D --> E
        D --> F
        F --> G
    end
    
    subgraph "OData Service (ZMCP_002)"
        H[Metadata Endpoint]
        I[Entity Sets]
        J[Function Imports]
        
        I --> K[ZLLM_00_NODESet]
        I --> L[ZLLM_00_EDGESet]
        I --> M[ZLLM_00_BINSet]
        J --> N[BUILD_GRAPH]
    end
    
    A -.->|Tool Discovery| B
    A -->|Tool Invocation| B
    E -->|GET /$metadata| H
    F -->|CRUD Operations| I
    F -->|Function Calls| J
```

## Tool Generation Flow

```mermaid
sequenceDiagram
    participant MP as MetadataParser
    participant MD as Metadata
    participant BR as ODataMCPBridge
    participant MCP as FastMCP
    
    MP->>MD: Parse $metadata XML
    MD->>BR: Entity Types & Sets
    
    loop For each Entity Set
        BR->>BR: Generate filter tool
        BR->>BR: Generate count tool
        BR->>BR: Generate search tool
        BR->>BR: Generate get tool
        BR->>BR: Generate CRUD tools
        BR->>MCP: Register tools
    end
    
    BR->>MCP: Register service_info tool
```

## Request Flow Example

```mermaid
sequenceDiagram
    participant AI as AI Assistant
    participant MCP as MCP Server
    participant BR as Bridge
    participant CL as ODataClient
    participant GH as GUIDHandler
    participant OD as OData Service
    
    AI->>MCP: filter_ZLLM_00_NODESet(top=5)
    MCP->>BR: Execute tool
    BR->>CL: list_or_filter_entities()
    CL->>CL: Build OData query
    CL->>OD: GET /ZLLM_00_NODESet?$top=5
    OD->>CL: JSON response with base64 GUIDs
    CL->>GH: optimize_response()
    GH->>GH: Convert base64 to GUIDs
    GH->>CL: Optimized response
    CL->>BR: Formatted result
    BR->>MCP: JSON string
    MCP->>AI: Tool response
```

## Data Transformation Pipeline

```
Raw OData Response          Optimized Response
─────────────────          ─────────────────
{                          {
  "d": {                     "results": [{
    "results": [{              "Seed": 0,
      "Seed": 0,               "Id": "0242AC10-0004-1FD0-8BE1-D0C2",
      "Id": "AkkEEAA...",      "Node": "DEVC.$ZXRAY",
      "Node": "DEVC.$ZXRAY",   "ObjType": "DEVC"
      "ObjType": "DEVC"      }],
    }]                       "_truncated": false,
  }                          "pagination": {
}                              "total_count": 100,
                              "has_more": true
                            }
                          }
```

## Entity Relationships in ZMCP_002

```mermaid
erDiagram
    NODE ||--o{ EDGE : "has"
    NODE {
        int Seed PK
        binary Id PK
        string Node
        string ObjType
        string ObjName
    }
    
    EDGE {
        int Seed PK
        binary F PK "From Node"
        binary T PK "To Node"
        string Etype PK
    }
    
    BIN {
        string Bin PK
        string Name PK
        binary V
        datetime Ts
    }
```