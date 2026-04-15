# 🏴 Ultra Godot MCP

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4.6+](https://img.shields.io/badge/Godot-4.6+-478cbf?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Tests](https://img.shields.io/badge/Tests-484%20passing-2ea44f)](docs/TESTS.md)
[![Version](https://img.shields.io/badge/Version-3.1.0-6f42c1)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> *"Technique is a compositive or destructive activity, violent, and this is what Aristotle called poiesis, poetry, precisely."* — Gustavo Bueno

**Ultra Godot MCP** — *Plus Ultra*: go beyond.

MCP server for Godot Engine that allows AIs and assistants to control projects directly: create scenes, manipulate nodes, manage resources, and validate code, **all without opening the editor**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Native TSCN parsing** | Reads and writes `.tscn` files directly, no Godot headless |
| 🛠️ **42 tools** | Scenes, nodes, resources, scripts, signals, validation, and debug |
| 🎯 **Unified inspector** | `set_node_properties` handles ALL property types automatically |
| 🔄 **In-memory sessions** | Workspace with dirty tracking, lazy loading, and LRU cache |
| 🛡️ **Poka-Yoke validation** | Prevents errors before writing files |
| 🔎 **Fuzzy search** | Finds nodes tolerating typos with `fuzzywuzzy` |
| 📦 **Templates** | Generates node structures and GDScript boilerplate from templates |
| 🐛 **Debug** | 2 tools that require Godot installed (the rest work without it) |

---

## 🏆 Why Ultra Godot MCP?

### Speed: direct composition vs. intermediation

The main difference: other MCPs launch `godot --headless --script` per operation (2-5s overhead). Ultra Godot MCP reads and writes `.tscn` directly with its native parser — milliseconds.

| Operation | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) (3.1k⭐) | [GoPeak](https://github.com/HaD0Yun/Gopeak-godot-mcp) (125⭐) | Ultra Godot MCP |
|---|---|---|---|
| Read scene | ~2-5s (Godot headless) | ~2-5s (Godot headless) | <10ms (native parser) |
| Add node | ~2-5s | ~2-5s | <5ms |
| Validate project | ~10-30s | ~10-30s | <500ms |

### Full comparison

| Dimension | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) | [GoPeak](https://github.com/HaD0Yun/Gopeak-godot-mcp) | [tugcantopaloglu/godot-mcp](https://github.com/tugcantopaloglu/godot-mcp) | [gdai-mcp](https://github.com/3ddelano/gdai-mcp-plugin-godot) | **Ultra Godot MCP** |
|---|---|---|---|---|---|
| **Tools** | ~15 | 95+ | 149 | ~12 | **42** |
| **Parsing** | Godot headless | Godot headless | Godot headless | Godot plugin | **Native Python** |
| **Speed** | Slow (2-5s/op) | Slow (2-5s/op) | Slow (2-5s/op) | Medium | **<10ms** |
| **No Godot required** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **In-memory sessions** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **LRU Cache** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Poka-Yoke validation** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Fuzzy search** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Templates** | ❌ | ❌ | ❌ | ❌ | **✅** |

> **Note:** GoPeak and tugcantopaloglu have more tools in raw numbers, but each operation requires launching Godot headless. Ultra Godot MCP prioritizes speed: 42 tools (40 without Godot + 2 debug that require it).

### Feature comparison

| Feature | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) | [GoPeak](https://github.com/HaD0Yun/Gopeak-godot-mcp) | [tugcantopaloglu/godot-mcp](https://github.com/tugcantopaloglu/godot-mcp) | [gdai-mcp](https://github.com/3ddelano/gdai-mcp-plugin-godot) | **Ultra Godot MCP** |
|---|---|---|---|---|---|
| **Native TSCN parsing** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **No Godot installed** | ❌ | ❌ | ❌ | ❌ | **✅** (40/42 tools) |
| **In-memory sessions** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **LRU Cache** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Poka-Yoke validation** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Fuzzy search** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Templates** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Unified inspector** | ❌ | ✅ | ❌ | ❌ | **✅** |
| **Resource assignment to nodes** | ❌ (Sprites only) | ✅ (Requires addon) | ✅ | ✅ | **✅ (Automatic)** |
| **Signal connections** | ❌ | ✅ | ✅ | ❌ | **✅** |
| **Resource management** | ❌ | ✅ | ✅ | ✅ | **✅** |
| **UIDs (Godot 4.4+)** | ✅ | ✅ | ✅ | ❌ | **✅** |
| **LSP (autocompletion)** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **DAP (debugger)** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Runtime inspection** | ❌ | ✅ | ❌ | ✅ | ❌ |
| **Screenshots/input** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Asset library** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Project visualizer** | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Export mesh library** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Installation** | `npx` (npm) | `npx` (npm) | npm | Godot addon | **`pip` (Python)** |

> **What we have and they don't:** Native parser, in-memory sessions, LRU cache, Poka-Yoke validation, fuzzy search, templates.
>
> **What they have and we don't:** LSP (GDScript autocompletion), DAP (breakpoint debugger), runtime inspection, screenshots/input injection, asset library, project visualizer.

---

## 📥 Installation

### From PyPI (coming soon)

```bash
pip install godot-mcp
```

### From source

```bash
git clone https://github.com/CerebroCanibalus/Ultra-Godot-MCP-ASL.git
cd Ultra-Godot-MCP-ASL

pip install -e .
# Or with dev dependencies:
pip install -e ".[dev]"
```

### Requirements

- **Python 3.10+**
- **Godot 4.6+** (optional, only for debug tools)

---

## 🚀 Quick Start

### 1. Start the server

```bash
godot-mcp
# Or as module:
python -m godot_mcp.server
```

### 2. Configure in your MCP client

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

### 3. Use with your AI assistant

```
→ "Create a Player scene with CharacterBody2D, CollisionShape2D, and Sprite2D"
→ "Add a movement script to the player"
→ "Connect the body_entered signal from Area2D to the player"
→ "Validate that all project scenes are correct"
```

---

## 🛠️ Tools

### Session
| Tool | Description |
|---|---|
| `start_session` | Create a session for a Godot project |
| `end_session` | Close session and save changes |
| `get_active_session` | Get the current active session |
| `get_session_info` | Information about a session |
| `list_sessions` | List active sessions |
| `commit_session` | Save changes to disk |
| `discard_changes` | Discard changes without saving |

### Scenes
| Tool | Description |
|---|---|
| `create_scene` | Create new `.tscn` scene |
| `get_scene_tree` | Get full node hierarchy |
| `save_scene` | Save scene to disk |
| `list_scenes` | List all project scenes |
| `instantiate_scene` | Instantiate a scene as a child node |
| `modify_scene` | Modify root node type/name of a scene |

### Nodes
| Tool | Description |
|---|---|
| `add_node` | Add a node to a scene |
| `remove_node` | Remove a node |
| `update_node` | Update node properties |
| `rename_node` | Rename a node |
| `move_node` | Reparent a node |
| `duplicate_node` | Duplicate a node and its children |
| `find_nodes` | Find nodes by name or type (with fuzzy matching) |
| `get_node_properties` | Get all properties of a node |

### 🔥 Unified Inspector

```python
set_node_properties(session_id, scene_path, node_path, properties={...})
```

Handles **automatically** all types:

| Type | Example |
|---|---|
| **Textures** | `"texture": "res://sprites/player.png"` → creates ExtResource |
| **Shapes** | `"shape": {"shape_type": "CapsuleShape2D", "radius": 16.0}` → creates SubResource |
| **Scripts** | `"script": "res://scripts/player.gd"` → creates ExtResource |
| **Colors** | `"modulate": {"type": "Color", "r": 1, "g": 0.5, "b": 0.5, "a": 1}` |
| **Vectors** | `"position": {"type": "Vector2", "x": 100, "y": 200}` |
| **Enums** | `"motion_mode": "MOTION_MODE_GROUNDED"` |
| **Simple** | `"text": "Hello", "visible": true` |

### Resources
| Tool | Description |
|---|---|
| `create_resource` | Create `.tres` resource |
| `read_resource` | Read `.tres` properties |
| `update_resource` | Update resource properties |
| `add_ext_resource` | Add external reference to scene |
| `add_sub_resource` | Create embedded resource in scene |
| `list_resources` | List project resources |
| `get_uid` | Get resource UID (Godot 4.4+) |
| `update_project_uids` | Update all project UIDs |

### Scripts & Signals
| Tool | Description |
|---|---|
| `set_script` | Attach `.gd` script to a node |
| `connect_signal` | Connect signal between nodes |

### Project
| Tool | Description |
|---|---|
| `get_project_info` | Project metadata |
| `get_project_structure` | Full structure (scenes, scripts, assets) |
| `find_scripts` | Find `.gd` scripts |
| `find_resources` | Find `.tres` resources |
| `list_projects` | Find Godot projects in a directory |

### Validation
| Tool | Description |
|---|---|
| `validate_tscn` | Validate `.tscn` file (native parser, no Godot) |
| `validate_gdscript` | Validate `.gd` script (native parser, no Godot) |
| `validate_project` | Validate full project (native parser, no Godot) |

### 🔧 Debug
> ⚠️ These 2 tools **do require Godot installed**. They are the only ones that launch the engine.

| Tool | Description |
|---|---|
| `run_debug_scene` | Run scene in headless mode and capture errors, warnings, and prints |
| `check_script_syntax` | Check GDScript syntax with Godot's `--check-only` |

---

## 📚 Documentation

| Document | Content |
|---|---|
| [TOOLS.md](docs/TOOLS.md) | Complete reference for each tool |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Internal design, sessions, and cache |
| [COMMON_ERRORS.md](docs/COMMON_ERRORS.md) | Common errors and solutions |
| [TESTS.md](docs/TESTS.md) | Testing metrics and coverage |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## 🧪 Testing

```bash
pytest tests/              # All tests
pytest --cov=godot_mcp     # With coverage
pytest tests/e2e/          # E2E only
pytest tests/test_server.py -v  # Specific tests
```

**Status:** 484 tests passing · 68 new tests in v3.1.0

---

## 🏗️ Architecture

```
src/godot_mcp/
├── server.py              # FastMCP entry point
├── session_manager.py     # Session management
├── core/                  # Core
│   ├── tscn_parser.py     # Godot scene parser
│   ├── tres_parser.py     # Resource parser
│   ├── tscn_validator.py  # Scene validator
│   ├── gdscript_validator.py  # Script validator
│   ├── cache.py           # LRU cache
│   ├── models.py          # Pydantic models
│   └── project_index.py   # Project index
├── tools/                 # MCP tools
│   ├── scene_tools.py     # Scene operations
│   ├── node_tools.py      # Node operations
│   ├── resource_tools.py  # Resource management
│   ├── session_tools.py   # Session management
│   ├── project_tools.py   # Project operations
│   ├── validation_tools.py  # Validation
│   ├── signal_and_script_tools.py  # Signals & scripts
│   ├── property_tools.py   # Unified inspector
│   └── debug_tools.py     # Debug
└── templates/             # Templates
    ├── node_templates.py  # Node templates
    └── script_templates.py  # Script templates
```

---

## 📄 License

**MIT** — see [LICENSE](LICENSE) for details.

---

<div align="center">

**For the workers and the Iberophones of the world** 🌍

🇪🇸🇲🇽🇦🇷🇨🇴🇵🇪🇨🇱🇻🇪🇧🇴🇪🇨🇬🇹🇭🇳🇳🇮🇵🇾🇸🇻🇺🇾🇩🇴🇵🇷🇬🇶🇵🇭🇦🇩🇧🇿🇵🇹🇧🇷🇦🇴🇲🇿🇨🇻🇬🇼🇸🇹🇹🇱🇲🇴

</div>
