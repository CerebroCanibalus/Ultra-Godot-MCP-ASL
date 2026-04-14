# 🛠️ Referencia de Herramientas MCP

Todas las herramientas disponibles en el Godot MCP Server.

---

## Sesión

### `start_session`
Crea una sesión para un proyecto Godot.

```python
start_session(project_path: str) -> dict
```

**Ejemplo:**
```python
result = start_session(project_path="/ruta/al/proyecto")
session_id = result["session_id"]
```

### `end_session`
Cierra una sesión, opcionalmente guardando cambios.

```python
end_session(session_id: str, save: bool = True) -> dict
```

### `get_session_info`
Obtiene información detallada de una sesión.

```python
get_session_info(session_id: str) -> dict
```

### `list_sessions`
Lista todas las sesiones activas.

```python
list_sessions() -> dict
```

---

## Escenas

### `create_scene`
Crea una nueva escena `.tscn`.

```python
create_scene(session_id: str, scene_path: str,
             root_type: str = "Node2D", root_name: str = "Root") -> dict
```

### `get_scene_tree`
Obtiene la jerarquía completa de nodos de una escena.

```python
get_scene_tree(session_id: str, scene_path: str) -> dict
```

### `save_scene`
Guarda una escena a disco.

```python
save_scene(session_id: str, scene_path: str, scene_data: dict) -> dict
```

### `list_scenes`
Lista todas las escenas del proyecto.

```python
list_scenes(session_id: str, recursive: bool = True) -> dict
```

### `instantiate_scene`
Instancia una escena como nodo dentro de otra escena.

```python
instantiate_scene(session_id: str, scene_path: str,
                  parent_scene_path: str, node_name: str,
                  parent_node_path: str = ".") -> dict
```

---

## Nodos

### `add_node`
Añade un nodo a una escena.

```python
add_node(session_id: str, scene_path: str,
         parent_path: str, node_type: str, node_name: str,
         properties: dict = None) -> dict
```

### `remove_node`
Elimina un nodo de una escena.

```python
remove_node(session_id: str, scene_path: str, node_path: str) -> dict
```

### `update_node`
Actualiza propiedades de un nodo (versión básica).

```python
update_node(session_id: str, scene_path: str,
            node_path: str, properties: dict) -> dict
```

> **Nota:** Para propiedades complejas (texturas, shapes, etc.) usa `set_node_properties`.

### `get_node_properties`
Obtiene todas las propiedades de un nodo.

```python
get_node_properties(session_id: str, scene_path: str, node_path: str) -> dict
```

### `rename_node`
Renombra un nodo.

```python
rename_node(session_id: str, scene_path: str,
            node_path: str, new_name: str) -> dict
```

### `move_node`
Cambia el padre de un nodo (reparent).

```python
move_node(session_id: str, scene_path: str,
          node_path: str, new_parent_path: str) -> dict
```

### `duplicate_node`
Duplica un nodo y sus hijos.

```python
duplicate_node(session_id: str, scene_path: str,
               node_path: str, new_name: str = None) -> dict
```

### `find_nodes`
Busca nodos por nombre o tipo.

```python
find_nodes(session_id: str, scene_path: str,
           name_pattern: str = None, type_filter: str = None) -> dict
```

---

## 🔥 Inspector Unificado

### `set_node_properties`

Configura **CUALQUIER** propiedad del inspector de **CUALQUIER** nodo. Esta es la herramienta principal para manipular propiedades.

```python
set_node_properties(session_id: str, scene_path: str,
                    node_path: str, properties: dict[str, Any]) -> dict
```

#### Tipos de valores soportados

| Tipo | Formato | Ejemplo |
|------|---------|---------|
| **String** | Valor directo | `"Hello World"` |
| **Número** | Valor directo | `42`, `3.14` |
| **Booleano** | Valor directo | `true`, `false` |
| **Vector2** | Dict con tipo | `{"type": "Vector2", "x": 100, "y": 200}` |
| **Vector3** | Dict con tipo | `{"type": "Vector3", "x": 1, "y": 2, "z": 3}` |
| **Color** | Dict con tipo | `{"type": "Color", "r": 1, "g": 0.5, "b": 0.5, "a": 1}` |
| **Rect2** | Dict con tipo | `{"type": "Rect2", "x": 0, "y": 0, "w": 100, "h": 50}` |
| **Archivo** | Path `res://` | `"res://sprites/player.png"` |
| **Shape** | Dict con propiedades | `{"radius": 16.0}` |
| **Shape explícito** | Dict con shape_type | `{"shape_type": "CircleShape2D", "radius": 16.0}` |
| **Ref SubResource** | Dict con ref | `{"type": "SubResource", "ref": "my_shape"}` |
| **Ref ExtResource** | Dict con ref | `{"type": "ExtResource", "ref": "1"}` |
| **NodePath** | Dict con ref | `{"type": "NodePath", "ref": "../Player"}` |

#### Ejemplos por tipo de nodo

**Sprite2D - Textura y posición:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Sprite",
    properties={
        "texture": "res://sprites/player.png",
        "position": {"type": "Vector2", "x": 100, "y": 200},
        "scale": {"type": "Vector2", "x": 2.0, "y": 2.0},
        "flip_h": True,
        "modulate": {"type": "Color", "r": 1, "g": 0.8, "b": 0.8, "a": 1},
    })
```

**CollisionShape2D - Shape:**
```python
# Rectangle
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Collision",
    properties={
        "shape": {"size": {"type": "Vector2", "x": 32, "y": 32}}
    })

# Circle
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Collision",
    properties={
        "shape": {"shape_type": "CircleShape2D", "radius": 16.0}
    })

# Capsule
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Collision",
    properties={
        "shape": {"shape_type": "CapsuleShape2D", "radius": 12, "height": 40}
    })
```

**Label - Texto:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Label",
    properties={
        "text": "Game Over",
        "horizontal_alignment": "HORIZONTAL_ALIGNMENT_CENTER",
        "autowrap_mode": "AUTOWRAP_WORD_SMART",
    })
```

**Timer:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Timer",
    properties={
        "wait_time": 2.5,
        "one_shot": True,
        "autostart": True,
    })
```

**Camera2D:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Camera",
    properties={
        "current": True,
        "zoom": {"type": "Vector2", "x": 2, "y": 2},
        "position_smoothing_enabled": True,
        "position_smoothing_speed": 5.0,
    })
```

**AudioStreamPlayer:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Music",
    properties={
        "stream": "res://audio/music.ogg",
        "autoplay": True,
        "volume_db": -10.0,
    })
```

**PointLight2D:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Light",
    properties={
        "color": {"type": "Color", "r": 1, "g": 0.8, "b": 0.5, "a": 1},
        "energy": 2.0,
        "range": 200.0,
        "shadow_enabled": True,
    })
```

**RigidBody2D:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Ball",
    properties={
        "mass": 1.0,
        "gravity_scale": 1.0,
        "bounce": 0.5,
        "friction": 0.3,
        "lock_rotation": False,
    })
```

**MeshInstance3D:**
```python
set_node_properties(session_id, scene_path="game.tscn",
    node_path="Mesh",
    properties={
        "mesh": "res://models/player.glb",
        "material_override": "res://materials/player.tres",
    })
```

---

## Recursos

### `create_resource`
Crea un recurso `.tres`.

```python
create_resource(session_id: str, resource_path: str,
                resource_type: str, properties: dict = None) -> dict
```

### `read_resource`
Lee propiedades de un recurso `.tres`.

```python
read_resource(session_id: str, resource_path: str) -> dict
```

### `update_resource`
Actualiza propiedades de un recurso.

```python
update_resource(session_id: str, resource_path: str, properties: dict) -> dict
```

### `add_ext_resource`
Añade una referencia externa a una escena.

```python
add_ext_resource(session_id: str, scene_path: str,
                 resource_type: str, resource_path: str,
                 resource_id: str = None, uid: str = "") -> dict
```

### `add_sub_resource`
Crea un recurso embebido en una escena.

```python
add_sub_resource(session_id: str, scene_path: str,
                 resource_type: str, properties: dict = None,
                 resource_id: str = None) -> dict
```

### `get_uid`
Obtiene el UID de un recurso.

```python
get_uid(session_id: str, resource_path: str) -> dict
```

### `update_project_uids`
Actualiza todos los UIDs del proyecto.

```python
update_project_uids(session_id: str) -> dict
```

### `list_resources`
Lista recursos del proyecto.

```python
list_resources(session_id: str, resource_type: str = None,
               recursive: bool = True) -> dict
```

---

## Scripts y Señales

### `set_script`
Adjunta un script `.gd` a un nodo.

```python
set_script(session_id: str, scene_path: str,
           node_path: str, script_path: str) -> dict
```

### `connect_signal`
Conecta una señal entre nodos.

```python
connect_signal(session_id: str, scene_path: str,
               from_node: str, signal: str,
               to_node: str, method: str,
               flags: int = 0, binds: list = None) -> dict
```

---

## Proyecto

### `get_project_info`
Obtiene información del proyecto.

```python
get_project_info(session_id: str) -> dict
```

### `get_project_structure`
Obtiene la estructura completa del proyecto.

```python
get_project_structure(session_id: str) -> dict
```

### `find_scripts`
Busca scripts `.gd` en el proyecto.

```python
find_scripts(session_id: str) -> dict
```

### `find_resources`
Busca recursos `.tres` en el proyecto.

```python
find_resources(session_id: str, type_filter: str = None) -> dict
```

### `list_projects`
Busca proyectos Godot en un directorio.

```python
list_projects(session_id: str, directory: str, recursive: bool = True) -> dict
```

---

## Validación

### `validate_tscn`
Valida un archivo `.tscn`.

```python
validate_tscn(scene_path: str, project_path: str = None, strict: bool = False) -> dict
```

### `validate_gdscript`
Valida un script `.gd`.

```python
validate_gdscript(script_path: str = None, script_content: str = None,
                  strict: bool = False) -> dict
```

### `validate_project`
Valida todos los archivos del proyecto.

```python
validate_project(project_path: str, strict: bool = False) -> dict
```

---

## Nodos con propiedades mapeadas

El esquema de propiedades (`NODE_PROPERTY_SCHEMAS`) cubre **150+ tipos de nodo**, incluyendo:

### Física 2D/3D
`CollisionShape2D`, `CollisionShape3D`, `CollisionPolygon2D`, `CollisionPolygon3D`,
`Area2D`, `Area3D`, `RigidBody2D`, `RigidBody3D`, `StaticBody2D`, `StaticBody3D`,
`CharacterBody2D`, `CharacterBody3D`, `AnimatableBody2D`, `AnimatableBody3D`

### Rendering 2D
`Sprite2D`, `Sprite3D`, `AnimatedSprite2D`, `AnimatedSprite3D`, `TextureRect`,
`TextureButton`, `NinePatchRect`, `Polygon2D`, `Line2D`, `GPUParticles2D`,
`GPUParticles3D`, `CPUParticles2D`, `CPUParticles3D`

### Rendering 3D
`MeshInstance3D`, `CSGMesh3D`, `CSGBox3D`, `CSGSphere3D`, `CSGCylinder3D`,
`CSGCapsule3D`, `CSGTorus3D`

### Luces
`Light2D`, `PointLight2D`, `DirectionalLight2D`,
`DirectionalLight3D`, `OmniLight3D`, `SpotLight3D`

### Cámaras
`Camera2D`, `Camera3D`

### UI
`Label`, `RichTextLabel`, `Button`, `LineEdit`, `TextEdit`, `CodeEdit`,
`CheckBox`, `CheckButton`, `OptionButton`, `ColorRect`, `ColorPicker`,
`ColorPickerButton`, `ProgressBar`, `TextureProgressBar`, `HSlider`, `VSlider`,
`SpinBox`, `Panel`, `PanelContainer`, `VBoxContainer`, `HBoxContainer`,
`GridContainer`, `MarginContainer`, `CenterContainer`, `ScrollContainer`,
`TabContainer`, `TabBar`, `Tree`, `ItemList`, `ReferenceRect`

### Audio
`AudioStreamPlayer`, `AudioStreamPlayer2D`, `AudioStreamPlayer3D`

### Animación
`AnimationPlayer`, `AnimationTree`

### Mundo
`WorldEnvironment`, `Environment`, `CanvasLayer`, `YSort`,
`ParallaxBackground`, `ParallaxLayer`

### Navegación
`NavigationRegion2D`, `NavigationRegion3D`,
`NavigationAgent2D`, `NavigationAgent3D`

### TileMap
`TileMap`, `TileMapLayer`

### Materiales
`ShaderMaterial`, `StandardMaterial3D`, `ORMMaterial3D`

### Sky
`ProceduralSkyMaterial`, `PanoramaSkyMaterial`, `PhysicalSkyMaterial`

### Shapes (SubResources)
`RectangleShape2D`, `CircleShape2D`, `CapsuleShape2D`, `WorldBoundaryShape2D`,
`SegmentShape2D`, `ConvexPolygonShape2D`, `ConcavePolygonShape2D`,
`RectangleShape3D`, `SphereShape3D`, `CapsuleShape3D`, `CylinderShape3D`,
`WorldBoundaryShape3D`, `BoxShape3D`, `ConvexPolygonShape3D`, `ConcavePolygonShape3D`

### Meshes (SubResources)
`BoxMesh`, `SphereMesh`, `CylinderMesh`, `CapsuleMesh`, `PlaneMesh`,
`QuadMesh`, `PrismMesh`, `TorusMesh`, `RibbonTrailMesh`, `TubeTrailMesh`

### Otros
`Timer`, `RayCast2D`, `RayCast3D`, `ShapeCast2D`, `ShapeCast3D`,
`Path2D`, `Path3D`, `PathFollow2D`, `PathFollow3D`,
`SpringArm2D`, `SpringArm3D`, `Skeleton2D`, `Skeleton3D`, `Bone2D`,
`LightOccluder2D`, `OccluderPolygon2D`,
`VisibleOnScreenNotifier2D`, `VisibleOnScreenNotifier3D`,
`VisibilityEnabler2D`, `VisibilityEnabler3D`,
`RemoteTransform2D`, `RemoteTransform3D`,
`PinJoint2D`, `DampedSpringJoint2D`, `GrooveJoint2D`,
`HingeJoint3D`, `SliderJoint3D`, `ConeTwistJoint3D`, `Generic6DOFJoint3D`,
`VehicleBody2D`, `VehicleWheel2D`, `VehicleBody3D`, `VehicleWheel3D`,
`MultiplayerSpawner`, `SubViewport`, `SubViewportContainer`,
`ParticleProcessMaterial`
