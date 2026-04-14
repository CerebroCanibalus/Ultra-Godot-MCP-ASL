# 🏗️ Arquitectura del Godot MCP

## Resumen

El Godot MCP Server usa una arquitectura basada en **sesiones** que proporciona workspace en memoria, lazy loading y dirty tracking para operaciones eficientes sobre archivos `.tscn`.

---

## Componentes Principales

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT (AI/LLM)                       │
└──────────────────────────┬──────────────────────────────┘
                           │ JSON-RPC (MCP)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  GODOT MCP SERVER                        │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  Session     │  │  TSCN        │  │  Validator    │ │
│  │  Manager     │  │  Parser      │  │  (Poka-Yoke)  │ │
│  └──────────────┘  └──────────────┘  └───────────────┘ │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  Node Tools  │  │  Property    │  │  Resource     │ │
│  │              │  │  Tools       │  │  Tools        │ │
│  └──────────────┘  └──────────────┘  └───────────────┘ │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │  Signal &    │  │  Project     │                    │
│  │  Script      │  │  Tools       │                    │
│  └──────────────┘  └──────────────┘                    │
└──────────────────────────┬──────────────────────────────┘
                           │ Lectura/Escritura directa
                           ▼
┌─────────────────────────────────────────────────────────┐
│              SISTEMA DE ARCHIVOS (.tscn, .tres, .gd)     │
└─────────────────────────────────────────────────────────┘
```

---

## 1. SessionManager

Gestiona sesiones con workspace en memoria.

### Campos de Session

```python
@dataclass
class Session:
    id: str                          # ID único
    project_path: str                # Ruta al proyecto
    created_at: float                # Timestamp
    loaded_scenes: Dict[str, Scene]  # Escenas parseadas en memoria
    dirty_scenes: set                # Escenas con cambios sin guardar
    operations: list                 # Historial de operaciones
```

### Métodos principales

| Método | Descripción |
|--------|-------------|
| `start_session(project_path)` | Crea nueva sesión |
| `end_session(session_id, save)` | Cierra sesión |
| `load_scene_into_session(session_id, scene_path)` | Carga escena en memoria |
| `get_loaded_scene(session_id, scene_path)` | Obtiene escena cacheada |
| `mark_scene_dirty(session_id, scene_path)` | Marca escena como modificada |
| `commit_scene(session_id, scene_path)` | Guarda escena a disco |

### Decorador `@require_session`

Todas las tools que modifican archivos usan este decorador:

```python
@require_session
def add_node(session_id: str, scene_path: str, ...) -> dict:
    # session_id ya validado
    ...
```

---

## 2. TSCN Parser

Parser nativo de archivos `.tscn` sin necesidad de Godot Editor.

### Clases principales

| Clase | Descripción |
|-------|-------------|
| `Scene` | Escena completa (header, recursos, nodos, conexiones) |
| `SceneNode` | Nodo individual con propiedades |
| `ExtResource` | Referencia a archivo externo |
| `SubResource` | Recurso embebido en la escena |
| `Connection` | Conexión de señal entre nodos |

### Serialización

`Scene.to_tscn()` convierte la estructura de vuelta a formato TSCN:
- El nodo raíz **no** lleva atributo `parent`
- Los recursos se serializan como `ExtResource("id")` o `SubResource("id")`
- Los tipos tipados (Vector2, Color, etc.) se formatean correctamente

---

## 3. Validator (Poka-Yoke)

Validación automática que previene errores **antes** de escribir archivos.

### Reglas de validación

| Regla | Nivel | Descripción |
|-------|-------|-------------|
| `root_no_parent` | ERROR | El nodo raíz no puede tener `parent` |
| `unique_extresource_ids` | ERROR | IDs de ExtResource deben ser únicos |
| `unique_subresource_ids` | ERROR | IDs de SubResource deben ser únicos |
| `valid_resource_refs` | ERROR | Las referencias a recursos deben existir |
| `has_root_node` | ERROR | La escena debe tener al menos un nodo |
| `non_empty_node_names` | WARNING | Los nodos deben tener nombre |
| `valid_parent_paths` | WARNING | Las rutas de padre deben ser válidas |
| `ext_resource_files_exist` | ERROR | Los archivos de ExtResource deben existir |

---

## 4. Property Tools (Inspector Unificado)

`set_node_properties` es la herramienta central para manipular propiedades.

### Flujo de procesamiento

```
properties dict
       │
       ▼
┌─────────────────────────┐
│ _validate_properties()  │ ← Valida contra NODE_PROPERTY_SCHEMAS
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ _process_property_value │ ← Convierte valores a formato TSCN
│                         │
│ • "res://..." → ExtResource
│ • {"size": ...} → SubResource
│ • {"type": "SubResource", "ref": "id"} → SubResource("id")
│ • {"type": "Vector2", ...} → Vector2(x, y)
│ • "Hello" → string directo
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ node.properties.update()│ ← Aplica propiedades al nodo
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ _update_scene_file()    │ ← Serializa y escribe a disco
└─────────────────────────┘
```

### NODE_PROPERTY_SCHEMAS

Diccionario que mapea tipos de nodo → propiedades válidas:

```python
NODE_PROPERTY_SCHEMAS = {
    "Sprite2D": {
        "texture": {"type": "ext_resource", "resource_type": "Texture2D"},
        "position": {"type": "Vector2"},
        "flip_h": {"type": "bool"},
        ...
    },
    "CollisionShape2D": {
        "shape": {"type": "sub_resource", "resource_type": "Shape2D"},
        "disabled": {"type": "bool"},
        ...
    },
    ...
}
```

Cubre **150+ tipos de nodo** incluyendo física, rendering, UI, audio, animación, etc.

---

## 5. Estructura de Archivos

```
godot-mcp-python/
├── src/godot_mcp/
│   ├── server.py                    # Entry point del servidor
│   ├── session_manager.py           # SessionManager
│   ├── core/
│   │   ├── tscn_parser.py           # Parser y serializador TSCN
│   │   └── tscn_validator.py        # Validador Poka-Yoke
│   └── tools/
│       ├── session_tools.py         # start_session, end_session
│       ├── scene_tools.py           # create_scene, get_scene_tree
│       ├── node_tools.py            # add_node, update_node, find_nodes
│       ├── property_tools.py        # set_node_properties (inspector)
│       ├── resource_tools.py        # create_resource, add_ext_resource
│       ├── signal_and_script_tools.py # connect_signal, set_script
│       ├── project_tools.py         # get_project_info, find_scripts
│       └── validation_tools.py      # validate_tscn, validate_gdscript
├── tests/
│   ├── test_parser.py
│   ├── test_property_tools.py
│   ├── test_signal_and_script_tools.py
│   ├── test_tscn_validator.py
│   └── ...
└── docs/
    ├── TOOLS.md                     # Referencia de herramientas
    ├── ARCHITECTURE.md              # Este documento
    └── COMMON_ERRORS.md             # Errores comunes
```

---

## 6. Flujo de Trabajo Típico

```
1. start_session(project_path)
   └─→ session_id

2. create_scene(session_id, "Player.tscn", root_type="CharacterBody2D")
   └─→ Escena creada con nodo raíz

3. add_node(session_id, "Player.tscn", parent_path=".",
            node_type="Sprite2D", node_name="Sprite")
   └─→ Nodo añadido

4. set_node_properties(session_id, "Player.tscn",
    node_path="Sprite",
    properties={
        "texture": "res://sprites/player.png",
        "position": {"type": "Vector2", "x": 0, "y": -20},
    })
   └─→ ExtResource creado, propiedades aplicadas

5. add_node(session_id, "Player.tscn", parent_path=".",
            node_type="CollisionShape2D", node_name="Collision")

6. set_node_properties(session_id, "Player.tscn",
    node_path="Collision",
    properties={"shape": {"radius": 16.0}})
   └─→ SubResource CircleShape2D creado

7. set_script(session_id, "Player.tscn",
             node_path="Player", script_path="res://scripts/player.gd")
   └─→ Script adjuntado

8. connect_signal(session_id, "Player.tscn",
                  from_node="Player/Area2D", signal="body_entered",
                  to_node="Player", method="_on_body_entered")
   └─→ Conexión de señal creada

9. end_session(session_id, save=True)
   └─→ Sesión cerrada, cambios guardados
```

---

*Documento de arquitectura v2.0*
*Fecha: 2026-04-13*
