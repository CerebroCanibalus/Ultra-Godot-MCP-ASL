# 🏴 Ultra Godot MCP

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4.6+](https://img.shields.io/badge/Godot-4.6+-478cbf?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Tests](https://img.shields.io/badge/Tests-484%20passing-2ea44f)](docs/TESTS.md)
[![Version](https://img.shields.io/badge/Version-3.1.0-6f42c1)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> *"La técnica es una actividad compositora o destructora, violenta, y esto es lo que Aristóteles llamaba la poiesis, la poesía, precisamente."* — Gustavo Bueno

**Ultra Godot MCP** — *Plus Ultra*: ir más allá.

Este servidor MCP no delega la creación: la **potencia**. Opera directamente sobre la materia de tu proyecto Godot — escenas, nodos, recursos, scripts — sin intermediarios, sin lanzar el editor, sin esperar. La técnica como extensión del poder operatorio del desarrollador.

---

## ✨ Capacidades

| Capacidad | Descripción |
|---|---|
| 🔍 **Parsing nativo TSCN** | Lee y escribe archivos `.tscn` directamente — composición sin Godot headless |
| 🛠️ **38 herramientas** | El arsenal completo: escenas, nodos, recursos, scripts, señales, validación |
| 🎯 **Inspector unificado** | `set_node_properties` transforma TODOS los tipos de propiedad en una sola operación |
| 🔄 **Sesiones en memoria** | Workspace con dirty tracking y cache LRU — el estado persiste, no se reconstruye |
| 🛡️ **Validación Poka-Yoke** | Previene el error antes de que se materialice en el archivo |
| 🔎 **Búsqueda fuzzy** | Encuentra nodos tolerando typos — la intención importa más que la forma |
| 📦 **Templates** | Genera estructuras de nodos y scripts GDScript desde plantillas reutilizables |

---

## 🏆 Frente a otros MCPs de Godot

### Composición directa vs. intermediación

La diferencia fundamental es material: otros MCPs **intermedian** — lanzan `godot --headless --script` por cada operación, añadiendo 2-5 segundos de overhead. Ultra Godot MCP **compone directamente** — su parser nativo lee y escribe `.tscn` en milisegundos.

| Operación | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) (3.1k⭐) | [GoPeak](https://github.com/GoD0Yun/Gopeak-godot-mcp) (125⭐) | Ultra Godot MCP |
|---|---|---|---|
| Leer escena | ~2-5s (Godot headless) | ~2-5s (Godot headless) | <10ms (parser nativo) |
| Añadir nodo | ~2-5s | ~2-5s | <5ms |
| Validar proyecto | ~10-30s | ~10-30s | <500ms |

### Comparativa completa

| Dimensión | [godot-mcp](https://github.com/Coding-Solo/godot-mcp) | [GoPeak](https://github.com/GoD0Yun/Gopeak-godot-mcp) | [tugcantopaloglu/godot-mcp](https://github.com/tugcantopaloglu/godot-mcp) | [gdai-mcp](https://github.com/3ddelano/gdai-mcp-plugin-godot) | **Ultra Godot MCP** |
|---|---|---|---|---|---|
| **Herramientas** | ~15 | 95+ | 149 | ~12 | **38** |
| **Parsing** | Godot headless | Godot headless | Godot headless | Plugin Godot | **Nativo Python** |
| **Velocidad** | Lento (2-5s/op) | Lento (2-5s/op) | Lento (2-5s/op) | Medio | **<10ms** |
| **Sin Godot instalado** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Sesiones en memoria** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Cache LRU** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Validación Poka-Yoke** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Búsqueda fuzzy** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Templates** | ❌ | ❌ | ❌ | ❌ | **✅** |
| **Documentación en español** | ❌ | ❌ | ❌ | ❌ | **✅** |

> **Nota:** GoPeak y tugcantopaloglu tienen más herramientas en número bruto, pero cada operación requiere lanzar Godot headless. Ultra Godot MCP prioriza **composición directa**: menos intermediación, más velocidad. 38 herramientas que operan a velocidad de parser nativo, no 149 que esperan al editor.

### 🌎 Hecho para la comunidad hispanohablante y lusófona

La comunidad de Godot en español y portugués es enorme. Las herramientas de IA para desarrollo de juegos, sin embargo, están diseñadas exclusivamente en inglés. Ultra Godot MCP **compone desde nuestra realidad material**:

- **Documentación en español**: guías, errores y referencia técnica en tu idioma
- **Creado por y para** desarrolladores de España, México, Argentina, Colombia, Brasil, Portugal y toda Iberoamérica
- **Sin barrera idiomática**: porque hacer juegos no debería requerir hablar inglés

---

## 📥 Instalación

### Desde PyPI (próximamente)

```bash
pip install godot-mcp
```

### Desde fuente

```bash
git clone https://github.com/lenin-iberofono/godot-mcp.git
cd godot-mcp

pip install -e .
# O con dependencias de desarrollo:
pip install -e ".[dev]"
```

### Requisitos

- **Python 3.10+**
- **Godot 4.6+** (solo para validación con `--check-only`, opcional)

---

## 🚀 Puesta en marcha

### 1. Iniciar el servidor

```bash
godot-mcp
# O como módulo:
python -m godot_mcp.server
```

### 2. Configurar en tu cliente MCP

```json
{
  "mcpServers": {
    "godot": {
      "command": "python",
      "args": ["-m", "godot_mcp.server"],
      "cwd": "/ruta/a/tu/proyecto-godot"
    }
  }
}
```

### 3. Operar

Una vez configurado, tu asistente compone sobre tu proyecto:

```
→ "Crea una escena Player con CharacterBody2D, CollisionShape2D y Sprite2D"
→ "Añade un script de movimiento al jugador"
→ "Conecta la señal body_entered del Area2D al jugador"
→ "Valida que todas las escenas del proyecto estén correctas"
```

---

## 🛠️ Herramientas

### Sesión
| Herramienta | Descripción |
|---|---|
| `start_session` | Crear sesión para un proyecto Godot |
| `end_session` | Cerrar sesión y guardar cambios |
| `get_session_info` | Información de una sesión |
| `list_sessions` | Listar sesiones activas |

### Escenas
| Herramienta | Descripción |
|---|---|
| `create_scene` | Crear nueva escena `.tscn` |
| `get_scene_tree` | Obtener jerarquía completa de nodos |
| `save_scene` | Guardar escena a disco |
| `list_scenes` | Listar todas las escenas del proyecto |
| `instantiate_scene` | Instanciar una escena como nodo hijo |

### Nodos
| Herramienta | Descripción |
|---|---|
| `add_node` | Añadir nodo a una escena |
| `remove_node` | Eliminar nodo |
| `rename_node` | Renombrar nodo |
| `move_node` | Reparentar nodo |
| `duplicate_node` | Duplicar nodo y sus hijos |
| `find_nodes` | Buscar nodos por nombre o tipo (con fuzzy matching) |
| `get_node_properties` | Obtener todas las propiedades de un nodo |

### 🔥 Inspector Unificado

```python
set_node_properties(session_id, scene_path, node_path, properties={...})
```

Transforma cualquier propiedad del inspector en una sola operación:

| Tipo | Ejemplo |
|---|---|
| **Texturas** | `"texture": "res://sprites/player.png"` → crea ExtResource |
| **Shapes** | `"shape": {"shape_type": "CapsuleShape2D", "radius": 16.0}` → crea SubResource |
| **Scripts** | `"script": "res://scripts/player.gd"` → crea ExtResource |
| **Colores** | `"modulate": {"type": "Color", "r": 1, "g": 0.5, "b": 0.5, "a": 1}` |
| **Vectores** | `"position": {"type": "Vector2", "x": 100, "y": 200}` |
| **Enums** | `"motion_mode": "MOTION_MODE_GROUNDED"` |
| **Simples** | `"text": "Hello", "visible": true` |

### Recursos
| Herramienta | Descripción |
|---|---|
| `create_resource` | Crear recurso `.tres` |
| `read_resource` | Leer propiedades de un `.tres` |
| `update_resource` | Actualizar propiedades de recurso |
| `add_ext_resource` | Añadir referencia externa a escena |
| `add_sub_resource` | Crear recurso embebido en escena |
| `list_resources` | Listar recursos del proyecto |
| `get_uid` | Obtener UID de recurso (Godot 4.4+) |
| `update_project_uids` | Actualizar todos los UIDs del proyecto |

### Scripts y Señales
| Herramienta | Descripción |
|---|---|
| `set_script` | Adjuntar script `.gd` a un nodo |
| `connect_signal` | Conectar señal entre nodos |

### Proyecto
| Herramienta | Descripción |
|---|---|
| `get_project_info` | Metadata del proyecto |
| `get_project_structure` | Estructura completa (escenas, scripts, assets) |
| `find_scripts` | Buscar scripts `.gd` |
| `find_resources` | Buscar recursos `.tres` |
| `list_projects` | Encontrar proyectos Godot en un directorio |

### Validación
| Herramienta | Descripción |
|---|---|
| `validate_tscn` | Validar archivo `.tscn` |
| `validate_gdscript` | Validar script `.gd` |
| `validate_project` | Validar proyecto completo |

---

## 📚 Documentación

| Documento | Contenido |
|---|---|
| [TOOLS.md](docs/TOOLS.md) | Referencia completa de cada herramienta |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diseño interno, sesiones y cache |
| [COMMON_ERRORS.md](docs/COMMON_ERRORS.md) | Errores frecuentes y soluciones |
| [TESTS.md](docs/TESTS.md) | Métricas de testing y cobertura |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |

---

## 🧪 Testing

```bash
pytest tests/              # Todos los tests
pytest --cov=godot_mcp     # Con coverage
pytest tests/e2e/          # Solo E2E
pytest tests/test_server.py -v  # Tests específicos
```

**Estado:** 484 tests pasando · 68 tests nuevos en v3.1.0

---

## 🏗️ Arquitectura

```
src/godot_mcp/
├── server.py              # Entry point FastMCP
├── session_manager.py     # Gestión de sesiones
├── core/                  # Núcleo operatorio
│   ├── tscn_parser.py     # Parser de escenas Godot
│   ├── tres_parser.py     # Parser de recursos
│   ├── tscn_validator.py  # Validador de escenas
│   ├── gdscript_validator.py  # Validador de scripts
│   ├── cache.py           # Cache LRU
│   ├── models.py          # Modelos Pydantic
│   └── project_index.py   # Índice de proyectos
├── tools/                 # Herramientas MCP
│   ├── scene_tools.py     # Operaciones de escenas
│   ├── node_tools.py      # Operaciones de nodos
│   ├── resource_tools.py  # Gestión de recursos
│   ├── session_tools.py   # Gestión de sesiones
│   ├── project_tools.py   # Operaciones de proyecto
│   ├── validation_tools.py  # Validación
│   ├── signal_and_script_tools.py  # Señales y scripts
│   ├── property_tools.py   # Inspector unificado
│   └── debug_tools.py     # Debug
└── templates/             # Templates
    ├── node_templates.py  # Templates de nodos
    └── script_templates.py  # Templates de scripts
```

---

## 📄 Licencia

**MIT** — ver [LICENSE](LICENSE) para detalles.

---

<div align="center">

**Por los trabajadores y los iberófonos del mundo** 🌍

🇪🇸🇲🇽🇦🇷🇨🇴🇵🇪🇨🇱🇻🇪🇧🇴🇪🇨🇬🇹🇭🇳🇳🇮🇵🇾🇸🇻🇺🇾🇩🇴🇵🇷🇬🇶🇵🇭🇦🇩🇧🇿🇵🇹🇧🇷🇦🇴🇲🇿🇨🇻🇬🇼🇸🇹🇹🇱🇲🇴

</div>
