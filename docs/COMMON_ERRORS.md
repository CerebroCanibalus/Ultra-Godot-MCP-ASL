# 🔧 Errores Comunes y Soluciones

## Prevención Automática

El MCP incluye validación automática (Poka-Yoke) que previene errores **antes** de escribir archivos. Todas las operaciones de escritura validan la escena automáticamente.

---

## 🚨 Errores de Escenas (.tscn)

### Root node cannot specify a parent

**Mensaje:** `Invalid scene: root node X cannot specify a parent node`

**Causa:** El nodo raíz tiene `parent="."`.

**Solución:** El MCP ahora omite automáticamente el atributo `parent` en el nodo raíz durante la serialización.

---

### Failed to load scene dependency

**Mensaje:** `Failed to load scene dependency: "res://scenes/Player.tscn"`

**Causa:** La escena instanciada contiene errores.

**Solución:**
1. Verificar formato `.tscn` correcto
2. Comprobar que el nodo raíz no tenga `parent`
3. Validar rutas de recursos

---

## 🚨 Errores de Scripts GDScript

### Identifier not declared

**Mensaje:** `Identifier "sprite" not declared in the current scope`

**Solución:**
```gdscript
@onready var sprite: Sprite2D = $Sprite2D
```

### Called as function but is a bool

**Mensaje:** `Name "was_on_floor" called as a function but is a "bool"`

**Solución:**
```gdscript
# Incorrecto:
if was_on_floor():

# Correcto:
if was_on_floor:
```

---

## 🚨 Errores de Sesión MCP

### No active session

**Causa:** Se usó una tool sin sesión activa.

**Solución:**
```python
result = start_session(project_path="/ruta/proyecto")
session_id = result["session_id"]
```

### Invalid node_path

**Causa:** Path de nodo no existe.

**Solución:**
- `.` para nodo raíz
- `NombreNodo` para hijos directos
- `Padre/Hijo` para nodos anidados

---

## 🚨 Errores de Recursos

### Preload file does not exist

**Mensaje:** `Preload file "res://scenes/Projectile.tscn" does not exist`

**Solución:** Verificar que el archivo exista en la ruta especificada.

---

## 🚨 Errores de Formato TSCN

### Expected key=value pair

**Causa:** Sintaxis inválida en `.tscn`.

**Incorrecto:**
```
position = 100,200
```

**Correcto:**
```
position = Vector2(100, 200)
```

---

### Nodo instanciado aparece con X roja (tipo inválido)

**Síntoma:** El nodo aparece en el editor con una ❌ y el mensaje:
> "Este nodo se guardó como tipo de clase 'PackedScene', que ya no estaba disponible"

**Causa:** `instantiate_scene` generaba `type="PackedScene"` en el header del nodo. `PackedScene` es un **recurso**, no un tipo de nodo.

**Solución:** El MCP ahora usa el formato nativo de Godot con `instance=ExtResource("id")` en el header del nodo:

```
# Formato correcto (Godot nativo)
[node name="Enemy1" parent="." instance=ExtResource("1")]

# Formato incorrecto (viejo)
[node name="Enemy1" type="PackedScene" parent="."]
scene_file_path = ExtResource("1")
```

---

### ExtResource duplicados en escena

**Síntema:** Múltiples `[ext_resource]` apuntan al mismo archivo con IDs diferentes.

**Causa:** `instantiate_scene` calculaba paths inconsistentes (ej: `res://a/b/c.tscn` vs `res://c.tscn`) y no detectaba que eran el mismo recurso.

**Solución:** El MCP incluye un **deduplicador automático** que se ejecuta antes de guardar. Usa 3 estrategias:

1. **Filesystem resolution**: Resuelve `res://` a path real en disco
2. **Fuzzy match**: Detecta recursos con el mismo filename + tipo
3. **Path normalization**: Colapsa `..`, `.`, `//` en paths

El deduplicador también **remapea** todas las referencias de nodos al ID canónico.

---

### Color pierde canal alpha

**Síntoma:** `Color(r, g, b, a)` se serializa como `Color(r, g, b)`.

**Solución:** El parser ahora extrae correctamente los 4 componentes del Color. El round-trip parse→serialize preserva el alpha.

---

## 📝 Mejores Prácticas

1. **Siempre iniciar sesión** antes de cualquier operación
2. **Usar `set_node_properties`** para propiedades complejas (texturas, shapes)
3. **Validar rutas** de recursos antes de usarlas
4. **Probar escenas** individualmente antes de instanciarlas
5. **Usar `find_nodes`** para verificar paths de nodos

---

## 🔧 Uso del Validador

### Validar manualmente:

```python
from godot_mcp.core.tscn_validator import TSCNValidator
from godot_mcp.core.tscn_parser import parse_tscn_string

scene = parse_tscn_string(tscn_content)
validator = TSCNValidator()
result = validator.validate(scene)

if not result.is_valid:
    print(f"Errores: {result.errors}")
    print(f"Warnings: {result.warnings}")
```

---

*Última actualización: 2026-04-14*
