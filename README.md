# 🏴 Ultra Godot MCP

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4.6+](https://img.shields.io/badge/Godot-4.6+-478cbf?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Tests](https://img.shields.io/badge/Tests-489%20passing-2ea44f)](docs/TESTS.md)
[![Version](https://img.shields.io/badge/Version-4.4.0-6f42c1)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> *"Technique is a compositional or destructive activity, violent, and this is what Aristotle called poiesis, poetry, precisely."* — Gustavo Bueno

**Ultra Godot MCP** — *Plus Ultra*: go beyond.

MCP Server for Godot Engine that allows AIs and assistants to control projects directly: create scenes, manipulate nodes, manage resources, validate code, export builds, debug with breakpoints, and analyze project architecture — **all without installing addons in your Godot project**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Native TSCN Parsing** | Read and write `.tscn` files directly, without Godot headless |
| 🛠️ **99 tools** | 7 layers: Core (45) + CLI Bridge (16) + LSP/DAP (10) + Intelligence (7) + Skeleton (6) + Array Ops (2) + Resource Builder (9) |
| 🎯 **Unified Inspector** | `set_node_properties` handles ALL property types automatically |
| 🔄 **In-memory Sessions** | Workspace with dirty tracking, lazy loading and LRU cache |
| ⚡ **Persistent Godot headless** | Godot process running in background per session (10x faster) |
| 🛡️ **Poka-Yoke Validation** | Prevents errors before writing files |
| 🔎 **Fuzzy Search** | Find nodes tolerating typos with `fuzzywuzzy` |
| 📦 **Templates** | Generate node structures and GDScript scripts from templates |
| 🔧 **Native LSP/DAP** | Autocomplete, hover, breakpoints, stepping — no addons, just Godot Editor open |
| 📊 **Project Intelligence** | Dependency graph, signal graph, code analysis, metrics |
| 🎬 **Export & Screenshot** | Export builds, capture frames, record movies |
| 🐛 **Debug** | 2 tools require Godot installed (the rest work without it) |

---

## 🏆 vs Other Godot MCPs

### Speed: Direct Composition vs. Intermediation

The main difference: other MCPs launch `godot --headless --script` for every operation (2-5s overhead). Ultra Godot MCP reads and writes `.tscn` directly with its native parser — milliseconds. And when it needs Godot, it keeps the process alive in the background — 10x faster.

| Operation | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) (3.1k⭐) | [GoPeak](https://github.com/GoD0Yun/Gopeak-godot-mcp) (139⭐) | [GodotIQ](https://godotiq.com) | Ultra Godot MCP |
|---|---|---|---|---|
| Read scene | ~2-5s (Godot headless) | ~2-5s (Godot headless) | ~2-5s (WebSocket) | **<10ms** (native parser) |
| Add node | ~2-5s | ~2-5s | ~2-5s | **<5ms** |
| Validate project | ~10-30s | ~10-30s | ~10-30s | **<500ms** |
| Execute GDScript | ~5s | ~5s | ~5s | **<1s** (persistent headless) |
| Autocomplete | ❌ | ✅ (LSP) | ❌ | **✅ (native LSP)** |
| Breakpoints | ❌ | ✅ (DAP) | ❌ | **✅ (native DAP)** |

### Complete Comparison

| Dimension | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) | [GoPeak](https://github.com/GoD0Yun/Gopeak-godot-mcp) | [GodotIQ](https://godotiq.com) | **Ultra Godot MCP** |
|---|---|---|---|---|
| **Tools** | ~15 | 110+ | 36 (22 free + 14 Pro) | **99** |
| **Price** | Free | Free (MIT) | $19 Pro | **Free (MIT)** |
| **Addon required** | ❌ | ✅ (GDScript) | ✅ (18/22 tools) | **❌ Zero addon** |
| **WebSocket** | ❌ | ✅ (4 ports) | ✅ (port 6007) | **❌ Zero WebSocket** |
| **Parsing** | Godot headless | Godot headless | Godot headless | **Native Python** |
| **Speed** | Slow (2-5s/op) | Slow (2-5s/op) | Slow (2-5s/op) | **<10ms / <1s** |
| **Without Godot installed** | ❌ | ❌ | ❌ | **✅ (70+/98 tools)** |
| **In-memory sessions** | ❌ | ❌ | ❌ | **✅** |
| **LRU Cache** | ❌ | ❌ | ❌ | **✅** |
| **Poka-Yoke Validation** | ❌ | ❌ | ❌ | **✅** |
| **Fuzzy Search** | ❌ | ❌ | ❌ | **✅** |
| **Templates** | ❌ | ❌ | ❌ | **✅** |
| **LSP (autocomplete)** | ❌ | ✅ | ❌ | **✅** |
| **DAP (debugger)** | ❌ | ✅ | ❌ | **✅** |
| **Runtime inspection** | ❌ | ✅ | ✅ | **✅ (headless)** |
| **Export builds** | ❌ | ✅ | ❌ | **✅** |
| **Screenshots** | ❌ | ✅ | ✅ | **✅ (frame capture)** |
| **Dependency graph** | ❌ | ❌ | ✅ (Pro) | **✅ (free)** |
| **Signal graph** | ❌ | ❌ | ✅ (Pro) | **✅ (free)** |
| **Code analysis** | ❌ | Basic | ✅ (Pro) | **✅ (free)** |
| **Project metrics** | ❌ | ❌ | ✅ (Pro) | **✅ (free)** |
| **Spanish docs** | ❌ | ❌ | ❌ | **✅** |
| **Installation** | `npx` (npm) | `npx` (npm) | `pip` (Python) | **`pip` (Python)** |

> **Note:** GoPeak has more tools in number (110+), but requires GDScript addon + WebSocket + 4 ports. Ultra Godot MCP prioritizes **zero-config**: 99 tools that work without touching your Godot project.

### Feature Comparison

| Feature | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) | [GoPeak](https://github.com/HaD0Yun/Gopeak-godot-mcp) | [GodotIQ](https://godotiq.com) | **Ultra Godot MCP** |
|---|---|---|---|---|
| **Native TSCN parser** | ❌ | ❌ | ❌ | **✅** |
| **Zero addon** | ❌ | ❌ | ❌ | **✅** |
| **Zero WebSocket** | ❌ | ❌ | ❌ | **✅** |
| **In-memory sessions** | ❌ | ❌ | ❌ | **✅** |
| **LRU Cache** | ❌ | ❌ | ❌ | **✅** |
| **Poka-Yoke Validation** | ❌ | ❌ | ❌ | **✅** |
| **Fuzzy Search** | ❌ | ❌ | ❌ | **✅** |
| **Templates** | ❌ | ❌ | ❌ | **✅** |
| **Unified Inspector** | ❌ | ✅ | ❌ | **✅** |
| **Resource assignment to nodes** | ❌ (Sprites only) | ✅ (Requires addon) | ✅ | **✅ (Automatic)** |
| **Signal connection** | ❌ | ✅ | ✅ | **✅** |
| **Resource management** | ❌ | ✅ | ✅ | **✅** |
| **UIDs (Godot 4.4+)** | ✅ | ✅ | ✅ | **✅** |
| **LSP (autocomplete)** | ❌ | ✅ | ❌ | **✅** |
| **DAP (debugger)** | ❌ | ✅ | ❌ | **✅** |
| **Runtime inspection** | ❌ | ✅ (live) | ✅ (live) | **✅ (headless)** |
| **Export builds** | ❌ | ✅ | ❌ | **✅** |
| **Screenshots/input** | ❌ | ✅ (instant) | ✅ (instant) | **✅ (frame capture)** |
| **Dependency graph** | ❌ | ❌ | ✅ (Pro $19) | **✅ (free)** |
| **Signal graph** | ❌ | ❌ | ✅ (Pro $19) | **✅ (free)** |
| **Code analysis** | ❌ | Basic | ✅ (Pro $19) | **✅ (free)** |
| **Asset library** | ❌ | ✅ (CC0) | ❌ | ❌ |
| **Project visualizer** | ❌ | ✅ | ❌ | ❌ |
| **Spanish docs** | ❌ | ❌ | ❌ | **✅** |

> **What we have and they don't:** Native parser, zero addon, zero WebSocket, in-memory sessions, LRU cache, Poka-Yoke validation, fuzzy search, templates, LSP/DAP without addons, free dependency graph, free signal graph, free code analysis, Spanish docs.
>
> **What they have and we don't:** Instant editor screenshots (requires addon), input injection (requires addon), asset library (CC0), project visualizer.

### 🌎 For the Spanish and Portuguese-speaking Community

The Godot community in Spanish and Portuguese is huge, but AI tools for game development are designed exclusively in English. Ultra Godot MCP is born from that reality:

- **Spanish Documentation**: guides, errors and technical reference in your language
- **Created by and for** developers from Spain, Mexico, Argentina, Colombia, Brazil, Portugal and all of Ibero-America
- **No language barrier**: because making games shouldn't require speaking English

---

## 📥 Installation

### From PyPI (coming soon)

```bash
pip install godot-mcp
```

### From Source

```bash
git clone https://github.com/CerebroCanibalus/ultra-godot-mcp.git
cd ultra-godot-mcp

pip install -e .
# Or with dev dependencies:
pip install -e ".[dev]"
```

### Requirements

- **Python 3.10+**
- **Godot 4.6+** (optional, only for CLI Bridge, LSP/DAP and debug tools)

---

## 🚀 Quick Start

### 1. Start the Server

```bash
godot-mcp
# Or as a module:
python -m godot_mcp.server
```

### 2. Configure in your MCP Client

```json
{
  "mcpServers": {
    "godot": {
      "command": "python",
      "args": ["-m", "godot_mcp.server"],
      "cwd": "/path/to/your/godot-project"
    }
  }
}
```

### 3. Configure LSP/DAP (optional, for autocomplete and debugging)

LSP (Language Server Protocol) and DAP (Debug Adapter Protocol) are **native Godot features** — no additional installation required. You just need:

**Enable LSP (autocomplete, hover, symbols):**
1. Open your project in Godot Editor
2. Go to `Editor > Editor Settings > Network > Language Server`
3. Enable **"Enable Language Server"**
4. Verify the port is **6005**
5. Restart Godot Editor

**Enable DAP (breakpoints, stepping):**
1. Go to `Editor > Editor Settings > Network > Debug Adapter`
2. Enable **"Enable Debug Adapter"**
3. Verify the port is **6006**
4. Restart Godot Editor

> **Note:** LSP/DAP only works when Godot Editor is **open** with your project loaded. If you don't need it, the other 77 tools work without it.

### 4. Use with your AI Assistant

```
→ "Create a Player scene with CharacterBody2D, CollisionShape2D and Sprite2D"
→ "Add a movement script to the player"
→ "Connect the body_entered signal from Area2D to the player"
→ "Validate that all scenes in the project are correct"
→ "Export the project for Windows in release mode"
→ "Set a breakpoint at line 15 of player.gd and show me the variables"
→ "Analyze the code complexity of the project"
```

---

## 🛠️ Tools

### Layer 1: Core (45 tools) — No Godot Required

#### Session
| Tool | Description |
|---|---|
| `start_session` | Create session for a Godot project |
| `end_session` | Close session and save changes |
| `get_active_session` | Get the current active session |
| `get_session_info` | Information about a session |
| `list_sessions` | List active sessions |
| `commit_session` | Save changes to disk |
| `discard_changes` | Discard changes without saving |

#### Scenes
| Tool | Description |
|---|---|
| `create_scene` | Create new `.tscn` scene (supports `inherits` for inherited scenes) |
| `get_scene_tree` | Get complete node hierarchy |
| `save_scene` | Save scene to disk |
| `list_scenes` | List all scenes in the project |
| `instantiate_scene` | Instantiate a scene as child node (supports `editable_children`) |
| `modify_scene` | Modify root type/name of a scene |
| `set_editable_paths` | Mark instance children as editable (Godot 4.x) |
| `remove_ext_resource` | Remove orphaned ExtResource |
| `remove_sub_resource` | Remove orphaned SubResource |

#### Nodes
| Tool | Description |
|---|---|
| `add_node` | Add node (supports `unique_name_in_owner`, `owner`) |
| `remove_node` | Remove node |
| `update_node` | Update node properties |
| `rename_node` | Rename node |
| `move_node` | Reparent node |
| `duplicate_node` | Duplicate node and its children |
| `find_nodes` | Find nodes by name or type (with fuzzy matching) |
| `get_node_properties` | Get all properties of a node |
| `add_node_groups` | Add groups to a node |
| `remove_node_groups` | Remove groups from a node |

#### 🔥 Unified Inspector

```python
set_node_properties(session_id, scene_path, node_path, properties={...})
```

Automatically handles **all** types:

| Type | Example |
|---|---|
| **Textures** | `"texture": "res://sprites/player.png"` → creates ExtResource |
| **Shapes** | `"shape": {"shape_type": "CapsuleShape2D", "radius": 16.0}` → creates SubResource |
| **Scripts** | `"script": "res://scripts/player.gd"` → creates ExtResource |
| **Colors** | `"modulate": {"type": "Color", "r": 1, "g": 0.5, "b": 0.5, "a": 1}` |
| **Vectors** | `"position": {"type": "Vector2", "x": 100, "y": 200}` |
| **Enums** | `"motion_mode": "MOTION_MODE_GROUNDED"` |
| **Simple** | `"text": "Hello", "visible": true` |

#### Resources
| Tool | Description |
|---|---|
| `create_resource` | Create `.tres` resource |
| `read_resource` | Read properties of a `.tres` |
| `update_resource` | Update resource properties |
| `add_ext_resource` | Add external reference to scene |
| `add_sub_resource` | Create embedded resource in scene |
| `list_resources` | List project resources |
| `get_uid` | Get resource UID (Godot 4.4+) |
| `update_project_uids` | Update all project UIDs |

#### Scripts and Signals
| Tool | Description |
|---|---|
| `set_script` | Attach `.gd` script to a node |
| `connect_signal` | Connect signal (validates methods in scripts) |
| `disconnect_signal` | Disconnect signal |
| `list_signals` | List all signal connections |

#### Project
| Tool | Description |
|---|---|
| `get_project_info` | Project metadata |
| `get_project_structure` | Complete structure (scenes, scripts, assets) |
| `find_scripts` | Find `.gd` scripts |
| `find_resources` | Find `.tres` resources |
| `list_projects` | Find Godot projects in a directory |

#### Validation
| Tool | Description |
|---|---|
| `validate_tscn` | Validate `.tscn` file (native parser, no Godot) |
| `validate_gdscript` | Validate `.gd` script (Godot 4.6 API + real syntax with Godot) |
| `validate_project` | Validate complete project (native parser, no Godot) |

### Layer 2: Godot CLI Bridge (16 tools) — Requires Godot

#### Export
| Tool | Description |
|---|---|
| `export_project` | Export project with configured preset |
| `list_export_presets` | List available export presets |
| `validate_export_preset` | Validate that a preset exists and is valid |
| `get_export_log` | Get log from last export |

#### Runtime
| Tool | Description |
|---|---|
| `run_gdscript` | Execute arbitrary GDScript code in headless mode |
| `get_scene_info_runtime` | Get info from scene loaded at runtime |
| `get_performance_metrics` | FPS, draw calls, memory, nodes (runs scene for N seconds) |
| `test_scene_load` | Verify that a scene loads without errors |
| `get_classdb_info` | Get Godot ClassDB information |
| `call_group_runtime` | Call method on group of nodes in loaded scene |

#### Import
| Tool | Description |
|---|---|
| `reimport_assets` | Reimport project assets |
| `get_import_settings` | Get import settings for an asset |

#### Screenshot
| Tool | Description |
|---|---|
| `capture_scene_frame` | Capture specific frame from running scene |
| `capture_scene_sequence` | Capture sequence of frames |

#### Movie
| Tool | Description |
|---|---|
| `write_movie` | Record video of running scene |
| `write_movie_with_script` | Record video with setup script |

### Layer 3: LSP/DAP Native (10 tools) — Requires Godot Editor open

#### LSP (Language Server Protocol)
| Tool | Description |
|---|---|
| `lsp_get_completions` | GDScript autocomplete at specific position |
| `lsp_get_hover` | Hover documentation for symbol |
| `lsp_get_symbols` | All symbols in a file (classes, methods, variables) |
| `lsp_get_diagnostics` | Errors and warnings in a file |

#### DAP (Debug Adapter Protocol)
| Tool | Description |
|---|---|
| `dap_start_debugging` | Start debugging session |
| `dap_set_breakpoint` | Set breakpoint at file and line |
| `dap_continue` | Continue execution |
| `dap_step_over` | Step over (execute line without entering functions) |
| `dap_step_into` | Step into (enter functions) |
| `dap_get_stack_trace` | Get stack trace with variables |

### Layer 4: Project Intelligence (7 tools) — No Godot Required

#### Dependency Graph
| Tool | Description |
|---|---|
| `get_dependency_graph` | Dependency graph between project files |
| `find_unused_assets` | Find unreferenced assets |

#### Signal Graph
| Tool | Description |
|---|---|
| `get_signal_graph` | Signal connections graph (emitter → receiver) |
| `find_orphan_signals` | Detect signals connected to non-existent methods |

#### Code Analysis
| Tool | Description |
|---|---|
| `analyze_script` | Complexity metrics, functions, classes, issues |
| `find_code_smells` | Code smells: long functions, high complexity, magic numbers |
| `get_project_metrics` | Aggregated metrics for complete project |

### 🔧 Debug
> ⚠️ These 2 tools **require Godot installed**. They are the only ones that launch the engine.

| Tool | Description |
|---|---|
| `run_debug_scene` | Run scene in headless mode and capture errors, warnings and prints |
| `check_script_syntax` | Check GDScript syntax with Godot `--check-only` |

### Layer 5: Skeleton (6 tools) — No Godot Required

#### Skeleton2D
| Tool | Description |
|---|---|
| `create_skeleton2d` | Create Skeleton2D node in scene |
| `add_bone2d` | Add Bone2D to skeleton |
| `setup_polygon2d_skinning` | Bind Polygon2D to skeleton for deformation |

#### Skeleton3D
| Tool | Description |
|---|---|
| `create_skeleton3d` | Create Skeleton3D node in scene |
| `add_bone_attachment3d` | Bind nodes to skeleton bones |
| `setup_mesh_skinning` | Bind MeshInstance3D to skeleton |

### Layer 6: Array Operations (2 tools) — No Godot Required

| Tool | Description |
|---|---|
| `scene_array_operation` | Modify arrays in scenes (append/remove/replace/insert/clear) |
| `preview_array_operation` | Preview array changes without applying them |

### Layer 7: Resource Builder (9 tools) — No Godot Required

#### Generic
| Tool | Description |
|---|---|
| `build_resource` | Create any generic SubResource |
| `build_nested_resource` | Create resource hierarchies with cross-references |

#### Animation
| Tool | Description |
|---|---|
| `create_animation` | Create Animation with keyframe tracks |
| `create_state_machine` | Create AnimationNodeStateMachine with states and transitions |

#### AnimationTree
| Tool | Description |
|---|---|
| `create_blend_space_1d` | Create BlendSpace1D (idle→walk→run) |
| `create_blend_space_2d` | Create BlendSpace2D (4-way directions) |
| `create_blend_tree` | Create BlendTree (blend graph) |

#### Assets
| Tool | Description |
|---|---|
| `create_sprite_frames` | Create SpriteFrames (frame-by-frame animations) |
| `create_tile_set` | Create TileSet (atlas + collisions) |

---

## 📚 Documentation

| Document | Content |
|---|---|
| [TOOLS.md](docs/TOOLS.md) | Complete reference for all 99 tools |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Internal design, sessions and cache |
| [ARCHITECTURE_v4.md](docs/ARCHITECTURE_v4.md) | Architecture v4.0.0 (4 layers) |
| [CLEANUP_v4.md](docs/CLEANUP_v4.md) | Cleanup analysis and session integration |
| [COMMON_ERRORS.md](docs/COMMON_ERRORS.md) | Common errors and solutions |
| [TESTS.md](docs/TESTS.md) | Testing metrics and coverage |
| [CHANGELOG.md](CHANGELOG.md) | Version history (v4.4.0) |

---

## 🧪 Testing

```bash
pytest tests/              # All tests
pytest --cov=godot_mcp     # With coverage
pytest tests/e2e/          # E2E only
pytest tests/test_server.py -v  # Specific tests
```

**Status:** 489 tests passing · 22 modules registered in v4.4.0

---

## 🏗️ Architecture

```
src/godot_mcp/
├── server.py                    # FastMCP entry point (22 modules registered)
├── session_manager.py           # Session management + Godot headless
├── core/                        # Core
│   ├── api/                     # Godot APIs (external data)
│   │   ├── __init__.py          # GodotAPI + NodeAPI classes
│   │   ├── godot_api_4.6.json   # Godot 4.6.1 API (GDScript)
│   │   └── godot_nodes_4.6.json # Godot 4.6.1 node types (TSCN)
│   ├── tscn_parser.py           # Godot scene parser (v4.4: StringName, Vector2i/3i, Rect2i, editable paths, unique_id)
│   ├── tres_parser.py           # Resource parser
│   ├── tscn_validator.py        # Scene validator (v2.0)
│   ├── gdscript_validator.py    # Script validator (v2.0)
│   ├── cache.py                 # LRU cache
│   ├── models.py                # Pydantic models
│   └── project_index.py         # Project index
├── tools/                       # Layers 1, 5, 6, 7
│   ├── scene_tools.py           # Scene operations
│   ├── node_tools.py            # Node operations
│   ├── resource_tools.py        # Resource management
│   ├── session_tools.py         # Session management
│   ├── project_tools.py         # Project operations
│   ├── validation_tools.py      # Validation
│   ├── signal_and_script_tools.py  # Signals and scripts
│   ├── property_tools.py        # Unified inspector
│   ├── debug_tools.py           # Debug
│   ├── skeleton_tools.py        # Layer 5: Skeleton2D/3D
│   ├── array_tools.py           # Layer 6: Array Operations
│   └── resource_builder_tools.py # Layer 7: Resource Builder (9 tools)
├── godot_cli/                   # Layer 2: CLI Bridge (v4.0.0)
│   ├── base.py                  # GodotCLIWrapper
│   ├── export_tools.py          # Export builds
│   ├── runtime_tools.py         # Runtime headless
│   ├── import_tools.py          # Reimport assets
│   ├── screenshot_tools.py      # Frame capture
│   └── movie_tools.py           # Movie recording
├── lsp_dap/                     # Layer 3: LSP/DAP Native (v4.0.0)
│   ├── client.py                # JSON-RPC client
│   ├── lsp_tools.py             # Language Server Protocol
│   └── dap_tools.py             # Debug Adapter Protocol
├── intelligence/                # Layer 4: Project Intelligence (v4.0.0)
│   ├── dependency_tools.py      # Dependency graph
│   ├── signal_graph_tools.py    # Signal graph
│   └── code_analysis_tools.py   # Code analysis
└── templates/                   # Templates
    ├── node_templates.py        # Node templates
    └── script_templates.py      # Script templates
```

---

## 📄 License

**MIT** — see [LICENSE](LICENSE) for details.

---

<div align="center">

**For the workers and the Iberophone peoples of the world** 🌍

🇪🇸🇲🇽🇦🇷🇨🇴🇵🇪🇨🇱🇻🇪🇧🇴🇪🇨🇬🇹🇭🇳🇳🇮🇵🇾🇸🇻🇺🇾🇩🇴🇵🇷🇬🇶🇵🇭🇦🇩🇧🇿🇵🇹🇧🇷🇦🇴🇲🇿🇨🇻🇬🇼🇸🇹🇹🇱🇲🇴

</div>