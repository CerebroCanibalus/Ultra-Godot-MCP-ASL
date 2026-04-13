# Errores Comunes del Godot MCP

Documentación de errores frecuentes y sus soluciones.

---

## ✅ Prevención Automática con TSCNValidator

El MCP ahora incluye validación automática (Poka-Yoke) que previene los errores más comunes **antes** de escribir el archivo.

### Cómo funciona:

Todas las operaciones de escritura (`create_scene`, `save_scene`) ahora validan automáticamente:

1. **Root node no tiene parent** - Bloqueado antes de escribir
2. **ExtResource IDs únicos** - Verificado automáticamente
3. **SubResource IDs únicos** - Verificado automáticamente
4. **Referencias válidas** - Recursos deben existir
5. **Tipos de nodo válidos** - Contra lista de 290+ tipos Godot

### Si ves un error de validación:

```
Scene validation failed: Root node cannot have parent attribute
```

Esto significa que el validador interceptó el problema antes de que Godot lo rechace.

### Desactivar validación (solo desarrollo):

```python
# En código del MCP - NO recomendado para producción
validator = TSCNValidator()
result = validator.validate(scene, strict=False)  # Warnings only
```

---

## 🚨 Errores de Escenas (.tscn)

### Error: "Invalid scene: root node X cannot specify a parent node"

**STATUS: ✅ PREVENIDO AUTOMÁTICAMENTE** por TSCNValidator

**Mensaje completo:**
```
ERROR: Invalid scene: root node Player cannot specify a parent node.
```

**Prevención:**
El validador ahora detecta esto automáticamente y retorna:
```
Scene validation failed: Root node cannot have parent attribute
```

**Causa:**
El nodo raíz de una escena tiene el atributo `parent="."` o `parent=".."`, lo cual es inválido. Los nodos raíz no deben especificar un nodo padre.

**Ejemplo incorrecto:**
```
[node name="Player" type="CharacterBody2D" parent="."]
```

**Ejemplo correcto:**
```
[node name="Player" type="CharacterBody2D"]
```

**Solución:**
Eliminar el atributo `parent` del nodo raíz en el archivo `.tscn`.

---

### Error: "Failed to load scene dependency"

**Mensaje completo:**
```
ERROR: Failed to load scene dependency: "res://scenes/test/Player.tscn". 
Make sure the required scene is valid.
```

**Causa:**
Una escena que es instanciada como PackedScene contiene errores de sintaxis o referencias inválidas.

**Solución:**
1. Verificar que el archivo `.tscn` tenga formato correcto
2. Comprobar que todos los nodos raíz no tengan `parent` definido
3. Validar que las rutas de recursos (ext_resource) sean correctas

---

## 🚨 Errores de Scripts GDScript

### Error: "Identifier X not declared in the current scope"

**Mensaje completo:**
```
ERROR: res://scenes/test/Player.gd:73 - Parse Error: Identifier "sprite" not declared in the current scope.
```

**Causa:**
Se está usando una variable que no ha sido declarada o no está en el scope actual.

**Solución:**
Declarar la variable usando `@onready` o `var`:
```gdscript
@onready var sprite: Sprite2D = $Sprite2D
```

---

### Error: "Member X is not a function" / "Name X called as a function but is a bool"

**Mensajes completos:**
```
ERROR: res://scenes/test_errores/Player.gd:117 - Parse Error: Member "was_on_floor" is not a function.
ERROR: res://scenes/test_errores/Player.gd:117 - Parse Error: Name "was_on_floor" called as a function but is a "bool".
```

**Causa:**
Se está llamando como función (`was_on_floor()`) una variable que es de tipo `bool`. En GDScript los booleanos no son funciones.

**Solución:**
Usar el nombre de la variable como tal (sin paréntesis):
```gdscript
# Incorrecto:
if is_on_floor() and not was_on_floor():

# Correcto:
if is_on_floor() and not was_on_floor:
```

**Nota:** Este error también puede aparecer como:
```
ERROR: Function "was_on_floor()" not found in base self.
```

---

## 🚨 Errores de Sesión MCP

### Error: "No active session"

**Causa:**
Se intentó usar una herramienta MCP sin tener una sesión activa iniciada.

**Solución:**
Llamar primero a `godot_start_session`:
```python
session_result = await godot_start_session(project_path="/ruta/al/proyecto")
session_id = json.loads(session_result)["session_id"]
```

---

### Error: "Invalid node_path"

**Causa:**
Se proporcionó un path de nodo que no existe en la escena.

**Solución:**
Usar el path correcto:
- `.` para el nodo raíz
- `NombreNodo` para hijos directos del raíz
- `Padre/Hijo` para nodos anidados

---

## 🚨 Errores de Recursos

### Error: "Preload file does not exist"

**Mensaje completo:**
```
ERROR: Preload file "res://scenes/Projectile.tscn" does not exist.
```

**Causa:**
El script intenta hacer preload de un archivo que no existe en la ruta especificada.

**Solución:**
1. Verificar que el archivo exista en la ruta indicada
2. Corregir la ruta si es necesario
3. Crear el archivo si es requerido

---

## 🚨 Errores de Formato TSCN

### Error: "Expected key=value pair"

**Causa:**
El archivo `.tscn` tiene sintaxis inválida, generalmente:
- Falta el símbolo `=` en una propiedad
- Valores sin comillas cuando son strings
- Formato incorrecto de subresources

**Ejemplo incorrecto:**
```
position = 100,200  # Falta Vector2()
zoom = 1.5,1.5      # Falta Vector2()
```

**Ejemplo correcto:**
```
position = Vector2(100, 200)
zoom = Vector2(1.5, 1.5)
```

---

## 📝 Mejores Prácticas para Evitar Errores

1. **Siempre verificar el nodo raíz** no tenga `parent="."`
2. **Usar `@onready`** para referencias a nodos hijos
3. **Iniciar sesión** antes de cualquier operación MCP
4. **Validar rutas** de recursos antes de usar preload/load
5. **Probar escenas** individualmente antes de instanciarlas
6. **Usar rutas absolutas** cuando sea posible para evitar confusiones

---

## 🔧 Debug Tips

Cuando ocurra un error:

1. Leer el mensaje de error completo
2. Identificar el archivo y línea del error
3. Verificar la sintaxis del archivo problemático
4. Comparar con ejemplos funcionales
5. Usar el editor de Godot para validar el archivo

---

## 🔧 Uso Avanzado del TSCNValidator

### Validar manualmente:

```python
from godot_mcp.core.tscn_validator import TSCNValidator, validate_scene
from godot_mcp.core.tscn_parser import parse_tscn_string

# Parsear escena
scene = parse_tscn_string(tscn_content)

# Validar
validator = TSCNValidator()
result = validator.validate(scene)

if not result.is_valid:
    print(f"Errores: {result.errors}")
    print(f"Warnings: {result.warnings}")
else:
    print("Validación exitosa!")
```

### Reglas de validación:

| Regla | Nivel | Descripción |
|-------|-------|-------------|
| root_no_parent | ERROR | Root no puede tener parent |
| unique_extresource_ids | ERROR | IDs ExtResource únicos |
| unique_subresource_ids | ERROR | IDs SubResource únicos |
| valid_node_types | ERROR | Tipos de nodo válidos |
| valid_resource_refs | ERROR | Referencias existentes |
| has_root_node | ERROR | Escena tiene root |
| non_empty_node_names | WARNING | Nombres no vacíos |
| valid_parent_paths | WARNING | Rutas parent válidas |
| ext_resource_files_exist | ERROR | Archivos existen en disco |

---

## 🔍 Errores Encontrados en Tests LAIKA-GD

Durante el análisis de los tests del proyecto LAIKA-GD, se identificaron los siguientes patrones de errores:

### 1. **Archivos de Script Referenciados No Existen**

**Ejemplo de test_scene.tscn:**
```
[gd_scene load_steps=2 format=3 uid="uid://npc_room"]

[ext_resource type="Script" path="res://src/scenes/test/npc_room.tscn.gd" id="1"]

[node name="NPCRoom" type="Node2D"]
script = ExtResource("1")
```

**Problema:** El archivo `npc_room.tscn.gd` **NO EXISTE** en el sistema de archivos.

**Causa:** 
- El script se referenció en el TSCN pero nunca se creó el archivo `.gd`
- El validador **NO detecta esto** porque no verifica existencia de archivos

**Estado:** 🔴 **CRÍTICO** - El validador necesita `project_path` para verificar

---

### 2. **Escenas con Formato Incompleto**

**Ejemplo de test_scene.tscn (sin load_steps):**
```
[gd_scene format=3]
```

**Problema:** Falta `load_steps` en el header.

**Estado:** 🟡 **ADVERTENCIA** - Godot puede cargarlo pero no es estándar

---

### 3. **Escenas con `unique_id` pero Sin Referencias**

**Ejemplo de test_hierarchy_scene.tscn:**
```
[node name="Ball" type="RigidBody3D" parent="." unique_id=1093637155]
```

**Problema:** Los `unique_id` se generaron pero los nodos no tienen propiedades ni referencias.

**Estado:** 🟢 **INFO** - Válido pero inusual

---

### 4. **TileMap sin Archivos de Textura**

**Ejemplo de npc_room_mcp.tscn:**
```
[node name="Sprite" type="Sprite2D" parent="NPC" unique_id=414967242]
texture = ExtResource("2_2hpgf")
```

**Problema:** El archivo `min_character.png` debe existir en `res://assets/graphics/minplayer/`.

**Estado:** 🔴 **CRÍTICO** - El validador debe verificar archivos de textura

---

## 📊 Resumen de Errores en Tests

| Archivo | Error | Severidad | Validador Detecta |
|---------|-------|-----------|-------------------|
| npc_room.tscn | Script no existe | 🔴 CRÍTICO | ❌ No (sin project_path) |
| test_scene.tscn | Sin load_steps | 🟡 ADVERTENCIA | ❌ No |
| test_hierarchy_scene.tscn | Sin propiedades | 🟢 INFO | ❌ No |
| npc_room_mcp.tscn | Textura no verificada | 🔴 CRÍTICO | ❌ No (sin project_path) |

---

## 🛠️ Mejoras Necesarias

### Prioridad 1 (Crítico)
1. ✅ **Validación de archivos en disco** - En progreso
2. **Validar que todos los ExtResource existan** (scripts, texturas, escenas)

### Prioridad 2 (Importante)
3. **Detectar formatos incompletos** (falta load_steps)
4. **Validar que texturas existan** antes de usarlas

### Prioridad 3 (Mejora)
5. **Añadir tests específicos para LAIKA-GD**
6. **Documentar patrones de errores comunes**

---

*Documento mantenido por el equipo de Devil's Kitchen*
*Última actualización: 2026-04-13*
