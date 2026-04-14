# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [3.1.0] - 2026-04-14

### Added
- **Fuzzy search** for nodes with `fuzzywuzzy` (typo tolerance)
- **Node templates** (`node_templates.py`) for quick generation of common structures
- **Script templates** (`script_templates.py`) for GDScript boilerplate
- **E2E tests** (`tests/e2e/`) with complete user workflows
- **Server tests** (`test_server.py`) - verification of 42 tool registration
- **Template tests** (`test_templates.py`) - 35 validation tests
- **Fuzzy search tests** (`test_fuzzy_search.py`) - 11 tests
- **Test documentation** (`docs/TESTS.md`) with coverage metrics
- `debug_tools` for session debugging

### Improved
- **Unified inspector** (`set_node_properties`) now handles ALL property types
- Automatic TSCN file validation before writing (Poka-Yoke)
- Sessions with dirty tracking and optimized lazy loading
- External resource handling (ExtResource) with automatic deduplication

### Fixed
- Return format of `list_scenes` (now `list[dict]` with `path` and `name`)
- Exceptions in `script_templates.py` (`KeyError` for missing templates)
- TSCN file header validation

---

## [3.0.0] - 2026-04-10

### Added
- **Unified inspector** (`set_node_properties`) - configure ANY inspector property
- **Automatic validation** of TSCN, GDScript, and full projects
- **UID management** (Godot 4.4+)
- **Signal connections** between nodes
- **Script attachment** to nodes in one step (`set_script`)
- **SubResources** embedded in scenes
- **Project index** with automatic detection

### Improved
- TSCN parser rewritten with full section support
- Lightweight sessions with in-memory workspace
- LRU cache for repetitive operations
- Expanded documentation (`TOOLS.md`, `ARCHITECTURE.md`, `COMMON_ERRORS.md`)

---

## [2.0.0] - 2026-04-05

### Added
- **Native TSCN parsing** without Godot headless
- **20+ MCP tools** for scene, node, and resource management
- **Sessions** with persistent in-memory state
- **Project management** (create, explore, validate)
- **Jinja2 templates** for code generation
- **Cache** for query optimization

### Changed
- Migration from Node.js to Python with FastMCP
- Modular architecture with `core/`, `tools/`, `templates/`

---

## [1.0.0] - 2026-03-28

### Added
- First MCP Server version in Node.js
- Basic scene and node support
- Initial TSCN parser
