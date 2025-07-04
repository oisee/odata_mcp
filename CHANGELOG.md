# Changelog

All notable changes to the Python OData MCP Bridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Read-only mode flags** (`--read-only`/`-ro` and `--read-only-but-functions`/`-robf`)
  - Hide all modifying operations (create, update, delete) in read-only mode
  - Allow function imports in read-only-but-functions mode
  - Mutually exclusive flags for clear operation control
- **Flexible hint system** for service-specific guidance
  - JSON-based hint configuration with wildcard pattern matching (* and ?)
  - `--hints-file` flag to load custom hint files (defaults to hints.json in script directory)
  - `--hint` flag for direct CLI hint injection (JSON or plain text)
  - Priority-based hint merging for multiple matching patterns
  - Default hints for SAP OData services, SAP PO Tracking service, and Northwind demo
  - Hints appear in `odata_service_info` tool response under `implementation_hints`
  - Comprehensive hint manager module (`odata_mcp_lib/hint_manager.py`)
- **MCP trace logging** (`--trace-mcp`) for debugging protocol communication
  - Infrastructure for capturing MCP messages
  - Saves trace logs to platform-specific temp directories
  - Helps diagnose client compatibility issues
- **HTTP/SSE transport support** (`--transport http`)
  - Server-Sent Events transport in addition to stdio
  - Configurable HTTP server address with `--http-addr`
  - Web-based client support
- **Enhanced response features**
  - Response size limits with `--max-response-size` (default: 5MB)
  - Item count limits with `--max-items` (default: 100)
  - Pagination hints with `--pagination-hints`
  - Response metadata inclusion with `--response-metadata`
  - Verbose error messages with `--verbose-errors`
- **Legacy date format support** (`--legacy-dates`, enabled by default)
  - Automatic conversion between SAP /Date(milliseconds)/ and ISO 8601 formats
  - `--no-legacy-dates` flag to disable conversion
- **Decimal field handling**
  - Automatic conversion of numeric values to strings for Edm.Decimal fields
  - Prevents SAP OData v2 "Failed to read property" errors

### Changed
- **Modular architecture**
  - Split monolithic codebase into focused modules
  - Improved maintainability and testability
  - Clean separation of concerns
- **Enhanced error handling**
  - Comprehensive OData error parsing
  - Detailed error context with verbose mode
  - Better error propagation throughout the stack
- **Improved tool naming**
  - Smart service-aware tool naming
  - Configurable prefix/postfix options
  - Automatic shortening for long names

### Fixed
- **GUID handling**
  - Automatic base64 to standard GUID format conversion
  - Proper handling of binary fields
- **Authentication issues**
  - Improved cookie file parsing
  - Better CSRF token management
  - Support for various authentication methods

## [2.0.0] - 2024-01-15

### Changed
- Complete refactoring into modular architecture
- Backward compatibility maintained through compatibility layer

### Added
- Transport abstraction layer
- Name shortening utilities
- Comprehensive test suite
- Enhanced trace mode

## [1.0.0] - 2023-12-01

### Added
- Initial Python implementation
- OData v2 support
- Dynamic tool generation
- Basic and cookie authentication
- SAP OData extensions
- CRUD operations
- Query support
- Function imports