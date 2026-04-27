# AGENTS.md - Subagentes del MCP Godot Python

Este documento define los subagentes especializados para el MCP Godot Python, un servidor que permite a LLMs interagir con proyectos Godot Engine.

---

## 📋 Subagentes Disponibles

| Agente | Descripción | Propósito Principal |
|--------|-------------|---------------------|
| `@Parser` | Especialista en parsing TSCN y formatos Godot | Analizar y manipular archivos .tscn, .gd, .tres |
| `@ArrayOps` | Operaciones quirúrgicas sobre arrays | Añadir/quitar/modificar elementos sin reescribir archivos |
| `@LSPClient` | Language Server Protocol de Godot | Autocompletado, hover, diagnósticos de GDScript |
| `@DAPClient` | Debug Adapter Protocol de Godot | Debugging, breakpoints, stack traces |
| `@CacheMaster` | Gestión de cache LRU e invalidación | Optimizar operaciones repetitivas |
| `@TemplateEngine` | Templates Jinja2 para nodos/scripts | Generar código GDScript automáticamente |
| `@ToolSmith` | Creación de herramientas FastMCP | Extender funcionalidades del servidor |
| `@SessionKeeper` | Gestión de sesiones ligeras | Manejar conexiones temporales |
| `@GodotSage` | Conocimiento profundo de Godot Engine | Consulta de documentación y mejores prácticas |

---

## 🎯 @Parser - Especialista en Parsing TSCN

### Responsabilidades
- Parsear archivos `.tscn` (formato de escena Godot)
- Parsear archivos `.gd` (scripts GDScript)
- Parsear archivos `.tres` (recursos Godot)
- Analizar estructura de nodos
- Validar sintaxis y referencias
- Extraer metadatos de recursos

### Cuándo Invocarlo
- Cuando necesitas analizar una escena existente
- Al crear o modificar nodos en tiempo real
- Para obtener información de recursos
- Al validar referencias entre escenas

### Herramientas MCP Usadas
```python
# Herramientas principales del Parser
- mcp__godot__get_scene_tree    # Obtener jerarquía de nodos
- mcp__godot__list_scenes     # Listar todas las escenas
- mcp__godot__find_nodes     # Buscar nodos por tipo
- mcp__godot__get_node_properties  # Propiedades de un nodo
```

### Flujo de Trabajo
```
1. Identificar tipo de archivo (.tscn, .gd, .tres)
2. Seleccionar parser apropiado
3. Parsear contenido estructura
4. Aplicar transformaciones necesarias
5. Serializar de vuelta al formato original
```

### Ejemplo de Uso
```python
# Parser TSCN básico
from godot_mcp.core.parser import TSCNParser

parser = TSCNParser()
scene_data = parser.parse("res://scenes/Player.tscn")
print(scene_data.nodes)  # {'root': 'CharacterBody2D', 'children': [...]}

# Encontrar nodos específicos
parser = TSCNParser()
nodes = parser.find_nodes("res://scenes/Player.tscn", "Area2D")
print(f"Encontrados {len(nodes)} nodos Area2D")
```

---

## ⚡ @CacheMaster - Gestión de Cache

### Responsabilidades
- Implementar cache LRU para operaciones frecuentes
- Invalidar cache cuando cambia el proyecto
- Gestionar TTL (Time-To-Live) de entradas
- Sincronizar cache entre sesiones
- Optimizar consultas repetitivas

### Cuándo Invocarlo
- Al acceder frecuentemente a los mismos recursos
- Para acelerar listados de escenas
- Cuando el proyecto tiene muchas escenas
- Para caching de metadata

### Herramientas MCP Usadas
```python
# Gestión de cache
- mcp__godot__get_scene_tree   # Cacheado
- mcp__godot__list_scenes    # Cacheado
- mcp__godot__find_nodes    # Cacheado
- mcp__godot__get_node_properties  # Cacheado
```

### Flujo de Trabajo
```
1. Verificar si entrada existe en cache
2. Si existe y es válida → retornar dato cacheado
3. Si no existe → ejecutar operación
4. Almacenar resultado en cache
5. Programar invalidación (TTL o手动)
```

### Ejemplo de Uso
```python
from godot_mcp.core.cache import CacheManager

cache = CacheManager(max_size=100, ttl=300)

# Primera llamada - cache miss
result = cache.get("scenes:/Player.tscn", fetch_scene_tree)

# Segunda llamada - cache hit (rápido)
result = cache.get("scenes:/Player.tscn", fetch_scene_tree)

# Invalidar cache manualmente
cache.invalidate("scenes:/Player.tscn")

# Limpiar todo el cache
cache.clear()
```

---

## 📝 @TemplateEngine - Motor de Templates

### Responsabilidades
- Generar código GDScript desde templates
- Crear estructuras de nodos prediseñadas
- Personalizar templates con variables
- Proveer librerías de templates comunes
- Versionar templates por tipo de nodo

### Cuándo Invocarlo
- Al crear nuevos scripts GDScript
- Para generar escenas con estructura común
- Al implementar patterns recurrentes
- Para crear boilerplate de nodos

### Herramientas MCP Usadas
```python
# Generación de código
- mcp__godot__create_scene   # Crear escena desde template
- mcp__godot__create_script  # Crear script desde template
- mcp__godot__add_node      # Añadir nodo generado
- mcp__godot__set_script    # Adjuntar script
```

### Flujo de Trabajo
```
1. Seleccionar template apropiado
2. Proveer variables de personalización
3. Renderizar template con Jinja2
4. Escribir archivo resultante
5. Registrar en cache de templates
```

### Ejemplo de Uso
```python
from godot_mcp.templates import TemplateEngine

engine = TemplateEngine()

# Template para Player Controller
player_script = engine.render("player_controller.gd.j2", {
    "class_name": "Player",
    "extends": "CharacterBody2D",
    "speed": 200.0,
    "jump_force": 400.0
})
print(player_script)

# Template para Health Component
health_template = engine.render("health_component.gd.j2", {
    "max_health": 100,
    "regen_rate": 5.0,
    "invincibility_time": 1.0
})
```

### Templates Disponibles

| Template | Descripción | Variables |
|----------|-------------|-----------|
| `player_controller.gd.j2` | Controller de jugador | speed, jump_force, extends |
| `health_component.gd.j2` | Sistema de salud | max_health, regen_rate |
| `state_machine.gd.j2` | Máquina de estados | states, initial_state |
| `hitbox_component.gd.j2` | Área de daño | damage, knockback |
| `character_body_2d.tscn.j2` | Plantilla de personaje | animations, stats |

---

## 🔧 @ToolSmith - Creador de Herramientas

### Responsabilidades
- Crear nuevas herramientas FastMCP
- Definir interfaces de herramientas
- Registrar herramientas en el servidor
- Documentar nuevas herramientas
- Testear herramientas creadas

### Cuándo Invocarlo
- Cuando necesitas nueva funcionalidad
- Al exponer APIs externas
- Para automatizar tareas repetitivas
- Para integrar servicios externos

### Herramientas MCP Usadas
```python
# Creación de herramientas
- mcp__godot__create_scene   # Nueva herramienta
- mcp__godot__add_node      # Nueva herramienta
- mcp__godot__connect_signal  # Nueva herramienta
- mcp__godot__create_resource  # Nueva herramienta
```

### Flujo de Trabajo
```
1. Definir especificación de herramienta
2. Crear implementación FastMCP
3. Registrar en servidor
4. Documentar y testear
5. Publicar para uso
```

### Ejemplo de Uso
```python
from godot_mcp.tools import tool, ToolRegistry

# Definir nueva herramienta
@tool(name="spawn_enemy", description="Creates an enemy at position")
def spawn_enemy(enemy_type: str, position: Vector2) -> dict:
    """Spawn an enemy of given type at position."""
    # Implementación...
    return {"enemy_id": "enemy_001", "type": enemy_type}

# Registrar herramienta
registry = ToolRegistry()
registry.register(spawn_enemy)
```

---

## 🔒 @SessionKeeper - Gestión de Sesiones

### Responsabilidades
- Crear sesiones ligeras para operaciones
- Gestionar estado entre llamadas
- Limpiar recursos al cerrar sesión
- Proveer aislamiento entre operaciones
- Manejar timeouts de sesión

### Cuándo Invocarlo
- Para operaciones que requieren estado
- Al manejar transacciones complejas
- Para debugging de sesiones
- Para testing aislado

### Herramientas MCP Usadas
```python
# Gestión de sesiones
- mcp__godot__start_session  # Crear sesión
- mcp__godot__get_active_session  # Obtener sesión activa
- mcp__godot__end_session  # Cerrar sesión
- mcp__godot__list_sessions  # Listar sesiones
```

### Flujo de Trabajo
```
1. Crear nueva sesión
2. Establecer estado inicial
3. Ejecutar operaciones en sesión
4. Commit o rollback
5. Limpiar recursos
```

### Ejemplo de Uso
```python
from godot_mcp.core.session import SessionManager

manager = SessionManager()

# Crear sesión temporal
session = manager.create_session(
    name="debug_player",
    auto_close=True
)

# Ejecutar operaciones
session.set("player_hp", 100)
session.set("debug_mode", True)

# Obtener estado
hp = session.get("player_hp")

# Cerrar sesión
manager.close_session(session.id)
```

---

## 📚 @GodotSage - Experto en Godot

### Responsabilidades
- Proveer conocimiento de Godot Engine
- Documentar mejores prácticas
- Explicar patrones de diseño
- Resolver dudas técnicas
- Mantener documentación actualizada

### Cuándo Invocarlo
- Cuando necesitas información de Godot
- Al decidir arquitectura de proyecto
- Para resolver errores difíciles
- Al implementar features complejas

### Herramientas MCP Usadas
```python
# Consulta de conocimiento
- context7_query_docs    # Documentación Godot
- mcp__godot__get_godot_version  # Versión usada
- mcp__godot__get_project_info   # Info del proyecto
```

### Flujo de Trabajo
```
1. Identificar tema de consulta
2. Buscar en knowledge base
3. Si no encontrado →Context7
4. Formular respuesta con ejemplos
5. Actualizar knowledge base
```

### Ejemplo de Uso
```python
from godot_mcp.knowledge import KnowledgeBase

sage = KnowledgeBase()

# Consultar información
info = sage.query("CharacterBody2D movement")
print(info.explanation)
print(info.examples)

# Consulta específica
info = sage.query("Area2D body_entered signal")
print(info.usage)
```

---

## ⚡ @ArrayOps - Operaciones Quirúrgicas sobre Arrays

### Responsabilidades
- Modificar arrays en escenas sin reescribir todo el archivo
- Preservar tipos de arrays (`Array[PackedScene]`, `Array[int]`, etc.)
- Soportar operaciones: append, remove, replace, insert, clear
- Previsualizar cambios antes de aplicarlos
- Manejar arrays con elementos complejos (ExtResource, SubResource)

### Cuándo Invocarlo
- Cuando necesitas añadir/quitar elementos de un array
- Para modificar listas de recursos (scenes, textures, etc.)
- Cuando quieres previsualizar cambios en arrays
- Para operaciones batch sobre arrays

### Herramientas MCP Usadas
```python
# Operaciones de arrays
- mcp__godot__scene_array_operation  # Append/remove/replace/insert/clear
- mcp__godot__preview_array_operation  # Previsualizar cambios
```

### Flujo de Trabajo
```
1. Identificar array objetivo (node + property)
2. Seleccionar operación (append/remove/replace/insert/clear)
3. Especificar valor/índice
4. Previsualizar cambios (opcional)
5. Aplicar operación
```

### Ejemplo de Uso
```python
# Añadir escena a spawner
from godot_mcp.tools.array_tools import scene_array_operation

result = scene_array_operation(
    scene_path="spawner.tscn",
    node_path="Spawner",
    property_name="scenes",
    operation="append",
    value={"type": "ExtResource", "ref": "3_newscene"}
)

# Previsualizar antes de aplicar
preview = preview_array_operation(
    scene_path="spawner.tscn",
    node_path="Spawner",
    property_name="scenes",
    operation="remove",
    index=0
)
```

---

## 🔍 @LSPClient - Language Server Protocol

### Responsabilidades
- Proporcionar autocompletado de código GDScript
- Mostrar documentación hover de símbolos
- Obtener lista de símbolos en archivos
- Diagnosticar errores y warnings en tiempo real

### Cuándo Invocarlo
- Cuando necesitas autocompletado de código
- Para ver documentación de métodos/clases
- Para encontrar todos los símbolos de un archivo
- Para diagnosticar errores antes de ejecutar

### Requisitos
- **Godot Editor DEBE estar abierto** (puerto 6005)
- Proyecto Godot válido con `project.godot`

### Herramientas MCP Usadas
```python
# LSP Tools (requiere Godot Editor abierto)
- mcp__godot__lsp_get_completions    # Autocompletado en posición
- mcp__godot__lsp_get_hover          # Documentación de símbolo
- mcp__godot__lsp_get_symbols        # Lista de símbolos
- mcp__godot__lsp_get_diagnostics    # Errores y warnings
```

### Flujo de Trabajo
```
1. Verificar que Godot Editor esté abierto
2. Proporr ruta del archivo GDScript
3. Especificar línea y columna (0-based)
4. Obtener resultados del LSP
```

### Ejemplo de Uso
```python
# Obtener autocompletado
completions = lsp_get_completions(
    project_path="D:/MyGame",
    file_path="res://scripts/player.gd",
    line=10,
    column=5
)

# Ver documentación de método
hover = lsp_get_hover(
    project_path="D:/MyGame",
    file_path="res://scripts/player.gd",
    line=15,
    column=8
)
```

---

## 🐛 @DAPClient - Debug Adapter Protocol

### Responsabilidades
- Iniciar sesiones de debugging
- Gestionar breakpoints
- Controlar ejecución (continue, step over, step into)
- Obtener stack traces con variables

### Cuándo Invocarlo
- Para debuggear scripts GDScript
- Para inspeccionar variables en runtime
- Para navegar por el stack trace
- Para breakpoints condicionales

### Requisitos
- **Godot Editor DEBE estar abierto** con debugging (puerto 6006)
- Proyecto Godot válido

### Herramientas MCP Usadas
```python
# DAP Tools (requiere Godot Editor en modo debug)
- mcp__godot__dap_start_debugging     # Iniciar sesión debug
- mcp__godot__dap_set_breakpoint      # Poner breakpoint
- mcp__godot__dap_continue            # Continuar ejecución
- mcp__godot__dap_step_over           # Step over
- mcp__godot__dap_step_into           # Step into
- mcp__godot__dap_get_stack_trace     # Obtener stack trace
```

### Flujo de Trabajo
```
1. Iniciar Godot Editor con debugging
2. Llamar dap_start_debugging()
3. Setear breakpoints con dap_set_breakpoint()
4. Ejecutar escena
5. Navegar con step_over/step_into
6. Inspeccionar stack trace
```

### Ejemplo de Uso
```python
# Iniciar debugging
session = dap_start_debugging("D:/MyGame")

# Poner breakpoint
breakpoint = dap_set_breakpoint(
    project_path="D:/MyGame",
    file_path="res://scripts/player.gd",
    line=42
)

# Obtener stack trace cuando se detenga
stack = dap_get_stack_trace("D:/MyGame")
```

---

## 🔄 Flujo de Trabajo Coordinado

Los subagentes pueden trabajan juntos:

```
@GodotSage (consulta)
       ↓
@Parser (analiza) → @CacheMaster (cachea)
       ↓
@ArrayOps (modifica arrays) → @Parser (valida)
       ↓
@TemplateEngine (genera) → @ToolSmith (crea herramienta)
       ↓
@SessionKeeper (gestiona sesión)
```

### Ejemplo Coordinado
```python
# 1. Consulta: "¿Cómo crear un Estado?"
from godot_mcp.knowledge import KnowledgeBase
sage = KnowledgeBase()
guidance = sage.query("create state pattern")

# 2. Parser: Analizar ejemplo existente
from godot_mcp.core.parser import GDScriptParser
parser = GDScriptParser()
example = parser.parse("res://scripts/states/EnemyState.gd")

# 3. Template Engine: Generar nuevo estado
from godot_mcp.templates import TemplateEngine
engine = TemplateEngine()
new_state = engine.render("state_base.gd.j2", {
    "state_name": "Attack",
    "transitions": ["Idle", "Chase"]
})

# 4. Cache: Guardar para uso futuro
from godot_mcp.core.cache import CacheManager
cache = CacheManager()
cache.set("states:Attack", new_state)
```

---

## 🆕 Nuevas Herramientas MCP (v4.1.0)

Las siguientes herramientas fueron añadidas para soportar funcionalidades avanzadas de Godot 4.x:

### Escenas Heredadas (`create_scene` con `inherits`)

Crear escenas que heredan de otra escena base:

```python
create_scene(
    project_path="D:/MyGame",
    scene_path="scenes/PlayerExtended.tscn",
    inherits="res://scenes/BasePlayer.tscn"
)
```

Genera `[gd_scene load_steps=2 format=3 inherits="res://scenes/BasePlayer.tscn"]` sin nodo root.

### Instanciación con Editable Children (`instantiate_scene`)

Instanciar una escena con `editable_children=True` para permitir modificar hijos en el editor:

```python
instantiate_scene(
    scene_path="res://scenes/Enemy.tscn",
    parent_scene_path="res://scenes/Level.tscn",
    node_name="Enemy1",
    editable_children=True  # Genera [editable path="Enemy1"]
)
```

### Gestión de Grupos (`add_node_groups`, `remove_node_groups`)

```python
# Añadir grupos
add_node_groups(
    scene_path="res://scenes/Player.tscn",
    node_path="Player",
    groups=["player", "damageable"]
)

# Eliminar grupos
remove_node_groups(
    scene_path="res://scenes/Player.tscn",
    node_path="Player",
    groups=["damageable"]
)
```

### Señales (`connect_signal`, `disconnect_signal`, `list_signals`)

```python
# Conectar
connect_signal(
    scene_path="res://scenes/Player.tscn",
    from_node="Player/Area2D",
    signal="body_entered",
    to_node="Player",
    method="_on_area_body_entered"
)

# Listar
list_signals(scene_path="res://scenes/Player.tscn")

# Desconectar
disconnect_signal(
    scene_path="res://scenes/Player.tscn",
    from_node="Player/Area2D",
    signal="body_entered",
    to_node="Player",
    method="_on_area_body_entered"
)
```

### Eliminación de Recursos (`remove_ext_resource`, `remove_sub_resource`)

```python
# Eliminar ExtResource huérfano
remove_ext_resource(
    scene_path="res://scenes/Player.tscn",
    resource_id="5"
)

# Eliminar SubResource huérfano
remove_sub_resource(
    scene_path="res://scenes/Player.tscn",
    resource_id="GradientTexture2D_abc123"
)
```

### Editable Paths (`set_editable_paths`)

Marcar hijos de instancias como editables manualmente:

```python
set_editable_paths(
    scene_path="res://scenes/Level.tscn",
    paths=["Kitchen", "Kitchen/Door", "Kitchen/Entities/Table"]
)
```

### Atributos de Nodo Adicionales

`add_node` e `instantiate_scene` ahora soportan:
- `unique_name_in_owner=True` → Referenciable con `%Name` en GDScript
- `owner="NodePath"` → Sistema de ownership de Godot

```python
add_node(
    scene_path="res://scenes/Player.tscn",
    parent_path=".",
    node_type="Area2D",
    node_name="Hitbox",
    unique_name_in_owner=True
)
```

---

## 📖 Glosario

| Término | Definición |
|---------|------------|
| TSCN | Formato de archivo de escena Godot |
| .gd | Extensión de scripts GDScript |
| .tres | Formato de recursos Godot |
| LRU | Least Recently Used - estrategia de cache |
| TTL | Time-To-Live - tiempo de expiración |
| FastMCP | Framework para crear servidores MCP |
| Jinja2 | Motor de templates Python |

---

## 🔗 Referencias

- [Godot Engine Documentation](https://docs.godotengine.org/)
- [FastMCP Library](https://github.com/jlowin/fastmcp)
- [GDScript Language Reference](https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/)

---

*Última actualización: 2026-04-26*
*Versión del documento: 1.1*