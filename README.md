# 🚀 Godot MCP Server

*Model Context Protocol server for Godot Engine with native TSCN parsing*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Godot 4.6+](https://img.shields.io/badge/Godot-4.6+-478cbf.svg)](https://godotengine.org/)
[![Tests](https://img.shields.io/badge/Tests-156%20passing-brightgreen.svg)](tests/)
[![Version](https://img.shields.io/badge/Version-3.1.0-purple.svg)](https://github.com/)

---

## 🎮 Descripción

**Godot MCP Server** es un servidor MCP (Model Context Protocol) diseñado para integrar Godot Engine con sistemas de IA. Soporta Godot 4.6+ y ofrece parsing nativo de archivos `.tscn` sin necesidad de iniciar el editor.

### ✨ Características

| Categoría | Descripción |
|-----------|-------------|
| ⚡ **Parsing nativo** | Lee/escribe archivos `.tscn` directamente, sin Godot Editor |
| 🛠️ **20+ herramientas** | Gestión completa de escenas, nodos, recursos y propiedades |
| 🎯 **Inspector unificado** | `set_node_properties` maneja TODAS las propiedades de cualquier nodo |
| 🔄 **Sesiones** | Workspace en memoria con dirty tracking y lazy loading |
| 🐛 **Validación automática** | Poka-Yoke previene errores antes de escribir archivos |
| 📦 **Gestión de proyectos** | Creación, exploración y estructura de proyectos |

---

## 📥 Instalación

```bash
# Instalar en modo desarrollo
pip install -e .
```

---

## 🚀 Uso Rápido

```python
from godot_mcp.tools.session_tools import start_session
from godot_mcp.tools.node_tools import add_node
from godot_mcp.tools.property_tools import set_node_properties

# 1. Iniciar sesión
result = start_session(project_path="/ruta/al/proyecto")
session_id = result["session_id"]

# 2. Crear escena y añadir nodos
add_node(session_id, scene_path="Player.tscn", parent_path=".",
         node_type="CharacterBody2D", node_name="Player")

# 3. Configurar propiedades del inspector
set_node_properties(session_id, scene_path="Player.tscn",
    node_path="Player",
    properties={
        "motion_mode": "MOTION_MODE_GROUNDED",
        "up_direction": {"type": "Vector2", "x": 0, "y": -1},
    })

# 4. Añadir colisión con shape automático
add_node(session_id, scene_path="Player.tscn", parent_path="Player",
         node_type="CollisionShape2D", node_name="Collision")

set_node_properties(session_id, scene_path="Player.tscn",
    node_path="Collision",
    properties={
        "shape": {"shape_type": "CapsuleShape2D", "radius": 16.0, "height": 32.0}
    })
```

---

## 🛠️ Herramientas Disponibles

### Sesión
| Herramienta | Descripción |
|-------------|-------------|
| `start_session` | Crear sesión para un proyecto |
| `end_session` | Cerrar sesión |
| `get_session_info` | Info de sesión |
| `list_sessions` | Listar sesiones activas |

### Escenas
| Herramienta | Descripción |
|-------------|-------------|
| `create_scene` | Crear nueva escena `.tscn` |
| `get_scene_tree` | Obtener jerarquía de nodos |
| `save_scene` | Guardar escena |
| `list_scenes` | Listar escenas del proyecto |
| `instantiate_scene` | Instanciar escena como nodo |

### Nodos
| Herramienta | Descripción |
|-------------|-------------|
| `add_node` | Añadir nodo a escena |
| `remove_node` | Eliminar nodo |
| `update_node` | Actualizar propiedades (básico) |
| `get_node_properties` | Obtener propiedades de un nodo |
| `rename_node` | Renombrar nodo |
| `move_node` | Reparentar nodo |
| `duplicate_node` | Duplicar nodo |
| `find_nodes` | Buscar nodos por nombre/tipo |

### 🔥 Inspector Unificado
| Herramienta | Descripción |
|-------------|-------------|
| `set_node_properties` | **Configurar CUALQUIER propiedad del inspector** |

Esta herramienta maneja automáticamente:
- **Texturas** → `{"texture": "res://sprite.png"}` (crea ExtResource)
- **Shapes** → `{"shape": {"radius": 16.0}}` (crea SubResource)
- **Scripts** → `{"script": "res://player.gd"}` (crea ExtResource)
- **Colores** → `{"modulate": {"type": "Color", "r": 1, "g": 0.5, "b": 0.5, "a": 1}}`
- **Vectores** → `{"position": {"type": "Vector2", "x": 100, "y": 200}}`
- **Valores simples** → `{"text": "Hello", "visible": true}`

### Recursos
| Herramienta | Descripción |
|-------------|-------------|
| `create_resource` | Crear recurso `.tres` |
| `read_resource` | Leer propiedades de `.tres` |
| `update_resource` | Actualizar recurso |
| `get_uid` | Obtener UID de recurso |
| `update_project_uids` | Actualizar UIDs del proyecto |
| `list_resources` | Listar recursos del proyecto |
| `add_ext_resource` | Añadir referencia externa a escena |
| `add_sub_resource` | Crear recurso embebido en escena |

### Scripts y Señales
| Herramienta | Descripción |
|-------------|-------------|
| `set_script` | Adjuntar script `.gd` a un nodo |
| `connect_signal` | Conectar señales entre nodos |

### Proyecto
| Herramienta | Descripción |
|-------------|-------------|
| `get_project_info` | Info del proyecto |
| `get_project_structure` | Estructura completa |
| `find_scripts` | Buscar scripts `.gd` |
| `find_resources` | Buscar recursos `.tres` |
| `list_projects` | Buscar proyectos Godot |

### Validación
| Herramienta | Descripción |
|-------------|-------------|
| `validate_tscn` | Validar archivo `.tscn` |
| `validate_gdscript` | Validar script `.gd` |
| `validate_project` | Validar proyecto completo |

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [`docs/TOOLS.md`](docs/TOOLS.md) | Referencia completa de todas las herramientas |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Diseño de sesiones y arquitectura interna |
| [`docs/COMMON_ERRORS.md`](docs/COMMON_ERRORS.md) | Errores comunes y soluciones |
| [`AGENTS.md`](AGENTS.md) | Subagentes especializados |

---

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest tests/

# Con coverage
pytest --cov=godot_mcp tests/
```

---

## 📄 Licencia

**MIT**. Consulta el archivo [LICENSE](LICENSE).

---

<div align="center">

*Desarrollado con ❤️ por Lenin y todos los iberófonos* 🇪🇸🇲🇽🇦🇷🇨🇴

</div>
