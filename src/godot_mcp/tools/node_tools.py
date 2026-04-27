"""
Node Tools - Herramientas para gestión de nodos Godot.

Proporciona herramientas FastMCP para operaciones CRUD de nodos en archivos .tscn.
Utiliza el parser TSCN nativo y fuzzywuzzy para búsquedas tolerantes.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

# Intentar importar fuzzywuzzy para búsquedas tolerantes
try:
    from fuzzywuzzy import fuzz
    from fuzzywuzzy.process import extractOne, extract

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

    # Implementación simple similarity si no hay fuzzywuzzy
    def fuzz_ratio(s1: str, s2: str) -> int:
        """Simple similarity ratio."""
        s1, s2 = s1.lower(), s2.lower()
        if s1 == s2:
            return 100
        # Contar caracteres comunes
        common = sum(1 for a, b in zip(s1, s2) if a == b)
        return int((common * 2 / (len(s1) + len(s2))) * 100) if s1 and s2 else 0


# Importar parser TSCN nativo
from godot_mcp.core.tscn_parser import (
    Scene,
    SceneNode,
    ExtResource,
    SubResource,
    parse_tscn,
    parse_tscn_string,
)
import uuid

logger = logging.getLogger(__name__)


# Tipos primitivos de GDScript que NUNCA deben convertirse en SubResource
# Estos se serializan inline (e.g., Vector2(0, 0), Color(1, 0, 0))
_GDSCRIPT_PRIMITIVE_TYPES = {
    "Vector2", "Vector2i", "Vector3", "Vector3i", "Vector4", "Vector4i",
    "Color", "Rect2", "Rect2i", "Transform2D", "Transform3D",
    "Basis", "Quaternion", "AABB", "Plane", "PackedStringArray",
    "PackedInt32Array", "PackedInt64Array", "PackedFloat32Array",
    "PackedFloat64Array", "PackedByteArray", "PackedColorArray",
    "PackedVector2Array", "PackedVector3Array", "StringName", "NodePath",
}


# ============ HELPERS ============


def _ensure_tscn_path(scene_path: str) -> str:
    """Ensure path ends with .tscn extension."""
    if not scene_path.endswith(".tscn"):
        return scene_path + ".tscn"
    return scene_path


def _normalize_node_path(node_path: str) -> str:
    """Normalize node path for comparison."""
    return node_path.strip("/")


def _compute_node_full_path(node: SceneNode, scene: Scene = None) -> str:
    """Compute the full path of a node (e.g., 'Root/Player/Sprite').
    
    If scene is provided, reconstructs the full hierarchical path by
    traversing parent references recursively.
    """
    if node.parent == "." or not node.parent:
        return node.name
    
    # If scene is provided, try to build full path recursively
    if scene:
        # Build a name -> node lookup
        name_to_node = {n.name: n for n in scene.nodes}
        
        def _build_path(node_name: str, visited: set = None) -> str:
            if visited is None:
                visited = set()
            if node_name in visited:
                return node_name  # Circular reference protection
            visited.add(node_name)
            
            if node_name not in name_to_node:
                return node_name
            
            n = name_to_node[node_name]
            if n.parent == "." or not n.parent:
                return n.name
            
            parent_path = _build_path(n.parent, visited)
            return f"{parent_path}/{n.name}"
        
        return _build_path(node.name)
    
    # Fallback: simple parent/name (for backwards compatibility)
    return f"{node.parent}/{node.name}"


def _find_node_by_path(scene: Scene, node_path: str) -> Optional[tuple[int, SceneNode]]:
    """
    Find a node in scene by its path.

    Supports:
    - Full paths: "Root/Player/Sprite" (exact match)
    - Simple names: "Sprite" (first match)
    - Fuzzy matching when enabled

    Returns tuple of (index, node) if found, None otherwise.
    """
    normalized = _normalize_node_path(node_path)

    # Strategy 1: Exact full path match (highest priority)
    if "/" in normalized:
        for idx, node in enumerate(scene.nodes):
            full_path = _compute_node_full_path(node)
            if full_path == normalized:
                return idx, node

    # Strategy 2: Exact name match (first occurrence)
    for idx, node in enumerate(scene.nodes):
        if node.name == normalized:
            return idx, node

    # Strategy 3: Match by last segment of path (e.g., "Player/Sprite" -> "Sprite")
    if "/" in normalized:
        simple_name = normalized.split("/")[-1]
        for idx, node in enumerate(scene.nodes):
            if node.name == simple_name:
                return idx, node

    # Strategy 4: Fuzzy matching
    if FUZZY_AVAILABLE:
        best_match = None
        best_ratio = 0
        for idx, node in enumerate(scene.nodes):
            ratio = fuzz.ratio(normalized.lower(), node.name.lower())
            if ratio > best_ratio and ratio > 70:
                best_ratio = ratio
                best_match = (idx, node)
        return best_match

    return None


def _find_sibling_by_name(
    scene: Scene, parent_path: str, node_name: str
) -> Optional[SceneNode]:
    """
    Find if a sibling with the same name exists under the same parent.

    Godot only requires unique names among siblings (same parent), not globally.

    Returns the existing sibling node if found, None otherwise.
    """
    normalized_parent = _resolve_parent_path(scene, parent_path) if parent_path else "."

    for node in scene.nodes:
        if node.name == node_name and node.parent == normalized_parent:
            return node
    return None


def _resolve_parent_path(scene: Scene, parent_path: str) -> str:
    """Resolve parent path to valid parent string."""
    parent_path = parent_path.strip()

    if not parent_path or parent_path == ".":
        return "."

    # Buscar si existe el nodo padre
    parent_result = _find_node_by_path(scene, parent_path)
    if parent_result:
        _, parent_node = parent_result
        return parent_node.name

    # Si no existe, asumir que es una ruta válida en el TSCN
    return parent_path


def _mark_scene_dirty(scene_path: str) -> None:
    """Mark a scene as dirty in the active session for commit tracking.

    This ensures that changes made by tools are tracked and can be
    committed via commit_session().
    """
    try:
        from godot_mcp.tools.session_tools import get_session_manager

        manager = get_session_manager()
        # Find any session that has this scene loaded or mark it dirty
        # We iterate through all sessions since we don't know which one is active
        for session_id in list(manager._sessions.keys()):
            session = manager.get_session(session_id)
            if session is not None:
                # Mark as dirty if the scene was modified
                manager.mark_scene_dirty(session_id, scene_path)
                logger.debug(
                    f"Marked scene dirty in session {session_id}: {scene_path}"
                )
    except Exception as e:
        # Don't fail the operation if dirty tracking fails
        logger.warning(f"Failed to mark scene dirty: {e}")


def _update_scene_file(scene_path: str, scene: Scene, max_retries: int = 3) -> None:
    """Write scene back to file with retry logic for file locking.

    Args:
        scene_path: Path to the .tscn file.
        scene: Scene object to serialize.
        max_retries: Number of retries on PermissionError (default: 3).

    Raises:
        PermissionError: If file is locked after all retries.
        OSError: If other I/O error occurs.
    """
    import shutil
    import time

    scene_path = _ensure_tscn_path(scene_path)
    content = scene.to_tscn()

    last_error = None
    for attempt in range(max_retries):
        try:
            # Create backup before modifying
            backup_path = scene_path + ".bak"
            if os.path.exists(scene_path):
                shutil.copy2(scene_path, backup_path)
                logger.info(f"Backup created: {backup_path}")

            # Write scene
            with open(scene_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Mark as dirty for commit tracking
            _mark_scene_dirty(scene_path)

            logger.info(f"Scene saved: {scene_path}")
            return  # Success

        except PermissionError as e:
            last_error = e
            logger.warning(
                f"Permission denied writing {scene_path} (attempt {attempt + 1}/{max_retries}). "
                f"Godot may have the file locked. Retrying..."
            )
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Progressive backoff: 0.5s, 1s, 1.5s

        except OSError as e:
            logger.error(f"OS error writing scene {scene_path}: {e}")
            raise

    # All retries exhausted
    raise PermissionError(
        f"Failed to write {scene_path} after {max_retries} attempts. "
        f"Godot editor may have the file locked. Close Godot or retry. "
        f"Last error: {last_error}"
    ) from last_error


def _build_node_tree(scene: Scene) -> list[dict]:
    """
    Build a tree structure of nodes.

    Returns list of dicts with name, type, parent, path.
    """
    result = []

    for node in scene.nodes:
        # Calcular path real del nodo
        if node.parent == ".":
            path = node.name
        else:
            path = f"{node.parent}/{node.name}"

        result.append(
            {
                "name": node.name,
                "type": node.type,
                "parent": node.parent,
                "path": path,
                "properties": node.properties,
            }
        )

    return result


def _generate_resource_id() -> str:
    """Generate a short unique ID for resources."""
    return str(uuid.uuid4())[:8]


def _clean_resource_id(resource_id: str) -> str:
    """
    Clean a resource ID by removing surrounding quotes.

    This prevents double-quoting issues when the ID comes from
    user input that may already include quotes.
    """
    if not isinstance(resource_id, str):
        return str(resource_id) if resource_id else ""

    # Remove surrounding single or double quotes
    resource_id = resource_id.strip()
    while resource_id and resource_id[0] in "\"'":
        resource_id = resource_id[1:]
    while resource_id and resource_id[-1] in "\"'":
        resource_id = resource_id[:-1]

    return resource_id


# Mapeo de propiedades a tipos de recursos
RESOURCE_TYPE_MAP = {
    # Texturas
    "texture": "Texture2D",
    "texture2d": "Texture2D",
    "sprite_frames": "SpriteFrames",
    "icon": "Texture2D",
    # Scripts
    "script": "Script",
    "script_path": "Script",
    # Shapes (se manejan como SubResource, no ExtResource)
    "shape": None,  # Special case - handled separately
    # Audio
    "stream": "AudioStream",
    "stream2d": "AudioStream",
    # Fonts
    "font": "Font",
    "font_file": "FontFile",
    # Animations
    "animation": "Animation",
    "animation_library": "AnimationLibrary",
    # Physics
    "physics_material": "PhysicsMaterial",
    # Other
    "mesh": "Mesh",
    "material": "Material",
    "shader": "Shader",
    "theme": "Theme",
    "environment": "Environment",
    "world_2d": "World2D",
}


def _process_resource_properties(scene: Scene, properties: dict) -> dict:
    """
    Process properties to convert resource paths to ExtResource/SubResource references.

    Args:
        scene: The Scene object to add resources to
        properties: Dict of properties to process

    Returns:
        New dict with resource paths replaced by ExtResource/SubResource references
    """
    if not properties:
        return properties

    processed = {}
    ext_resource_counter = 1
    sub_resource_counter = 1

    # Encontrar el siguiente ID disponible para ext_resources
    for ext in scene.ext_resources:
        try:
            ext_id = int(ext.id)
            if ext_id >= ext_resource_counter:
                ext_resource_counter = ext_id + 1
        except (ValueError, TypeError):
            pass

    for key, value in properties.items():
        # Caso 1: El valor es un string que empieza con "res://"
        if isinstance(value, str) and value.startswith("res://"):
            # Determinar el tipo de recurso
            resource_type = RESOURCE_TYPE_MAP.get(key.lower(), "Resource")

            # Buscar si ya existe un ext_resource con el mismo path
            existing_ext = None
            for ext in scene.ext_resources:
                if ext.path == value:
                    existing_ext = ext
                    break

            if existing_ext:
                # Reusar ext_resource existente
                clean_id = _clean_resource_id(existing_ext.id)
                resource_ref = f'ExtResource("{clean_id}")'
            else:
                # Crear nuevo ext_resource
                ext_id = str(ext_resource_counter)
                ext_resource_counter += 1
                new_ext = ExtResource(
                    type=resource_type,
                    path=value,
                    id=ext_id,
                )
                scene.ext_resources.append(new_ext)
                clean_id = _clean_resource_id(ext_id)
                resource_ref = f'ExtResource("{clean_id}")'

            processed[key] = resource_ref

        # Caso 2: El valor es un diccionario con "type" (SubResource/ExtResource)
        elif isinstance(value, dict) and "type" in value:
            resource_type = value["type"]

            # Si es un tipo primitivo de GDScript, pasarlo directamente
            # (nunca convertir Vector2, Color, etc. en SubResource)
            if resource_type in _GDSCRIPT_PRIMITIVE_TYPES:
                processed[key] = value
                continue

            # Si tiene campo "ref", es una referencia a recurso existente
            if "ref" in value:
                ref_id = _clean_resource_id(value["ref"])
                if resource_type == "ExtResource":
                    processed[key] = f'ExtResource("{ref_id}")'
                elif resource_type == "SubResource":
                    processed[key] = f'SubResource("{ref_id}")'
                elif resource_type == "NodePath":
                    processed[key] = f'NodePath("{ref_id}")'
                else:
                    processed[key] = value
                continue

            # Si no tiene "ref", es una definición de nuevo sub_resource
            sub_type = resource_type

            # Extraer propiedades del diccionario (excluyendo "type")
            sub_properties = {k: v for k, v in value.items() if k != "type"}

            # Buscar si ya existe un sub_resource con el mismo tipo y propiedades
            existing_sub = None
            for sub in scene.sub_resources:
                if sub.type == sub_type and sub.properties == sub_properties:
                    existing_sub = sub
                    break

            if existing_sub:
                # Reusar sub_resource existente
                clean_id = _clean_resource_id(existing_sub.id)
                resource_ref = f'SubResource("{clean_id}")'
            else:
                # Crear nuevo sub_resource
                sub_id = f"{sub_type}_{_generate_resource_id()}"
                new_sub = SubResource(
                    type=sub_type,
                    id=sub_id,
                    properties=sub_properties,
                )
                scene.sub_resources.append(new_sub)
                clean_id = _clean_resource_id(sub_id)
                resource_ref = f'SubResource("{clean_id}")'

            processed[key] = resource_ref

        # Caso 3: Valor normal (no es recurso)
        else:
            processed[key] = value

    return processed


# ============ Decoradores ====================

from godot_mcp.tools.decorators import require_session


# ============ TOOL FUNCTIONS ============


@require_session
def add_ext_resource(
    session_id: str,
    scene_path: str,
    resource_type: str,
    resource_path: str,
    resource_id: str = None,
    uid: str = "",
) -> dict:
    """
    Add an external resource to a scene's header.

    This creates an [ext_resource] entry in the TSCN file header,
    which can then be referenced by nodes using ExtResource("id").

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        resource_type: Godot resource type (e.g., "Texture2D", "Script", "PackedScene").
        resource_path: Path to the resource file (e.g., "res://sprites/player.png").
        resource_id: Optional custom ID. If None, auto-generates one.
        uid: Optional UID for the resource.

    Returns:
        Dict with success status and the resource ID to use in references.

    Example:
        # Add a texture resource
        result = add_ext_resource(
            scene_path="scenes/Player.tscn",
            resource_type="Texture2D",
            resource_path="res://sprites/player.png"
        )
        # Use result["resource_id"] in node properties:
        # update_node(..., properties={"texture": {"type": "ExtResource", "ref": result["resource_id"]}})
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Check if resource with same path already exists
    for ext in scene.ext_resources:
        if ext.path == resource_path:
            return {
                "success": True,
                "message": "Resource already exists",
                "resource_id": ext.id,
                "resource_type": ext.type,
                "resource_path": ext.path,
                "scene_path": scene_path,
            }

    # Generate ID if not provided
    if resource_id is None:
        # Find next available numeric ID
        max_id = 0
        for ext in scene.ext_resources:
            try:
                num_id = int(ext.id)
                if num_id > max_id:
                    max_id = num_id
            except (ValueError, TypeError):
                pass
        resource_id = str(max_id + 1)

    # Clean the ID
    resource_id = _clean_resource_id(resource_id)

    # Check for duplicate ID
    for ext in scene.ext_resources:
        if ext.id == resource_id:
            return {
                "success": False,
                "error": f"Resource ID '{resource_id}' already exists",
            }

    # Create and add the ExtResource
    new_ext = ExtResource(
        type=resource_type,
        path=resource_path,
        id=resource_id,
        uid=uid,
    )
    scene.ext_resources.append(new_ext)

    # Update load_steps in header
    scene.header.load_steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)

    # Save
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "resource_path": resource_path,
        "scene_path": scene_path,
        "usage_hint": f'Use ExtResource("{resource_id}") in node properties',
    }


@require_session
def add_node(
    session_id: str,
    scene_path: str,
    parent_path: str,
    node_type: str,
    node_name: str,
    properties: dict = None,
    unique_name_in_owner: bool = False,
    owner: str = "",
) -> dict:
    """
    Add a node to scene.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        parent_path: Parent node path (use "." for root).
        node_type: Godot node type (e.g., "Sprite2D", "Node2D").
        node_name: Name for the new node.
        properties: Optional dict of properties to set.
        unique_name_in_owner: If True, the node can be referenced with %name in GDScript.
        owner: Optional owner node path (Godot ownership system).

    Returns:
        Dict with success status and node info.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        # Crear nueva escena si no existe
        logger.info(f"Creating new scene: {scene_path}")
        scene = Scene()
        scene.header.load_steps = 2
        scene.header.format = 3
    else:
        scene = parse_tscn(scene_path)

    # Resolver path del padre
    resolved_parent = _resolve_parent_path(scene, parent_path)

    # Verificar que no exista un hermano con el mismo nombre bajo el mismo padre
    existing_sibling = _find_sibling_by_name(scene, resolved_parent, node_name)
    if existing_sibling:
        return {
            "success": False,
            "error": f"Node already exists under parent '{resolved_parent}': {node_name}",
            "hint": "Sibling names must be unique under the same parent",
        }

    # Crear nuevo nodo
    new_node = SceneNode(
        name=node_name,
        type=node_type,
        parent=resolved_parent,
        unique_name_in_owner=unique_name_in_owner,
        owner=owner,
    )

    # Procesar propiedades de recursos antes de asignar
    if properties:
        processed_props = _process_resource_properties(scene, properties)
        new_node.properties = processed_props

    # Agregar nodo a la escena
    scene.nodes.append(new_node)

    # Validate scene before saving (Poka-Yoke)
    from godot_mcp.core.tscn_validator import TSCNValidator

    validator = TSCNValidator()
    validation_result = validator.validate(scene)

    if not validation_result.is_valid:
        # Rollback: remove the node we just added
        scene.nodes.pop()
        return {
            "success": False,
            "error": f"Scene validation failed: {'; '.join(validation_result.errors)}",
            "validation_errors": validation_result.errors,
            "validation_warnings": validation_result.warnings,
        }

    # Log warnings but allow
    if validation_result.warnings:
        logger.warning(f"Node add warnings: {validation_result.warnings}")

    # Guardar
    _update_scene_file(scene_path, scene)

    node_path = (
        f"{resolved_parent}/{node_name}" if resolved_parent != "." else node_name
    )

    return {
        "success": True,
        "node": {
            "name": node_name,
            "type": node_type,
            "parent": resolved_parent,
            "path": node_path,
        },
        "scene_path": scene_path,
    }


@require_session
def remove_node(session_id: str, scene_path: str, node_path: str) -> dict:
    """
    Remove a node from scene.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node to remove.

    Returns:
        Dict with success status.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Buscar nodo
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result
    node_name = node.name

    # Remover nodo (y sus hijos si los hay)
    removed_nodes = [node_name]

    # Identify children BEFORE removing the node (only direct children defined after it)
    # Godot uses definition order: children always come after parent in TSCN
    children_to_remove = [
        i for i, n in enumerate(scene.nodes) if i > idx and n.parent == node_name
    ]

    # Remove children first (in reverse order to preserve indices)
    for i in reversed(children_to_remove):
        removed_nodes.append(scene.nodes[i].name)
        scene.nodes.pop(i)

    # Remove the node itself (adjust index if children were removed before it)
    # Since children were after the node, the node's index is unchanged
    scene.nodes.pop(idx)

    # Guardar
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "removed_nodes": removed_nodes,
        "scene_path": scene_path,
    }


@require_session
def update_node(
    session_id: str,
    scene_path: str,
    node_path: str,
    properties: dict,
) -> dict:
    """
    Update node properties.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node to update.
        properties: Dict of properties to set/update.

    Returns:
        Dict with success status and updated properties.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Buscar nodo
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result

    # Actualizar propiedades (procesar recursos primero)
    old_props = node.properties.copy()
    processed_props = _process_resource_properties(scene, properties)
    node.properties.update(processed_props)

    # Guardar
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "node_name": node.name,
        "old_properties": old_props,
        "new_properties": node.properties,
        "scene_path": scene_path,
    }


@require_session
def get_node_properties(session_id: str, scene_path: str, node_path: str) -> dict:
    """
    Get all properties of a node.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node.

    Returns:
        Dict with node info and properties.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Buscar nodo
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result

    # Calcular path real
    if node.parent == ".":
        full_path = node.name
    else:
        full_path = f"{node.parent}/{node.name}"

    return {
        "success": True,
        "node": {
            "name": node.name,
            "type": node.type,
            "parent": node.parent,
            "path": full_path,
            "unique_name_in_owner": node.unique_name_in_owner,
            "properties": node.properties,
        },
    }


@require_session
def rename_node(
    session_id: str, scene_path: str, node_path: str, new_name: str
) -> dict:
    """
    Rename a node.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Current path or name of the node.
        new_name: New name for the node.

    Returns:
        Dict with success status and old/new names.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Buscar nodo
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result
    old_name = node.name
    old_parent = node.parent

    # Verificar que el nuevo nombre no exista como hermano bajo el mismo padre
    existing_sibling = _find_sibling_by_name(scene, old_parent, new_name)
    if existing_sibling and existing_sibling != node:
        return {
            "success": False,
            "error": f"Node already exists under parent '{old_parent}': {new_name}",
            "hint": "Sibling names must be unique under the same parent",
        }

    # Renombrar
    node.name = new_name

    # Actualizar referencias de nodos hijos (solo hijos directos definidos después del nodo)
    # Godot usa orden de definición: los hijos siempre vienen después del padre en el TSCN
    for i, n in enumerate(scene.nodes):
        if i > idx and n.parent == old_name:
            n.parent = new_name

    # Guardar
    _update_scene_file(scene_path, scene)

    new_path = f"{old_parent}/{new_name}" if old_parent != "." else new_name

    return {
        "success": True,
        "old_name": old_name,
        "new_name": new_name,
        "new_path": new_path,
        "scene_path": scene_path,
    }


@require_session
def move_node(
    session_id: str, scene_path: str, node_path: str, new_parent_path: str
) -> dict:
    """
    Reparent a node.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Current path or name of the node.
        new_parent_path: New parent path (use "." for root).

    Returns:
        Dict with success status.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Buscar nodo
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result
    old_parent = node.parent

    # Resolver nuevo padre
    new_parent = _resolve_parent_path(scene, new_parent_path)

    # Evitar mover un nodo a sí mismo o a uno de sus descendientes
    if node.name == new_parent:
        return {
            "success": False,
            "error": "Cannot move node to itself",
        }

    # Validate that the new parent actually exists in the scene
    node_names = {n.name for n in scene.nodes}
    if new_parent != "." and new_parent not in node_names:
        return {
            "success": False,
            "error": f"Parent node does not exist: '{new_parent}'",
            "hint": "Use an existing node name or '.' for root",
        }

    # Mover
    node.parent = new_parent

    # Guardar
    _update_scene_file(scene_path, scene)

    if new_parent == ".":
        new_path = node.name
    else:
        new_path = f"{new_parent}/{node.name}"

    return {
        "success": True,
        "node_name": node.name,
        "old_parent": old_parent,
        "new_parent": new_parent,
        "new_path": new_path,
        "scene_path": scene_path,
    }


@require_session
def duplicate_node(
    session_id: str,
    scene_path: str,
    node_path: str,
    new_name: str = None,
) -> dict:
    """
    Duplicate a node and its children.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node to duplicate.
        new_name: Optional name for the duplicate (defaults to original + "_copy").

    Returns:
        Dict with success status and duplicated node info.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    # Buscar nodo original
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, original_node = result

    # Nombre para el duplicado
    if not new_name:
        new_name = original_node.name + "_copy"

    # Verificar que no exista un hermano con el mismo nombre bajo el mismo padre
    original_parent = original_node.parent
    existing_sibling = _find_sibling_by_name(scene, original_parent, new_name)
    if existing_sibling:
        return {
            "success": False,
            "error": f"Node already exists under parent '{original_parent}': {new_name}",
            "hint": "Sibling names must be unique under the same parent",
        }

    # Crear duplicado (copia profunda de propiedades)
    duplicate = SceneNode(
        name=new_name,
        type=original_node.type,
        parent=original_node.parent,
        unique_name_in_owner=original_node.unique_name_in_owner,
    )
    duplicate.properties = original_node.properties.copy()

    # Agregar a la escena
    scene.nodes.append(duplicate)

    # También duplicar nodos hijos (recursivamente para toda la jerarquía)
    original_name = original_node.name
    duplicated_nodes = [new_name]

    # Step 1: Collect all descendants in BFS order (parents before children)
    def _collect_descendants(node_name: str) -> list[SceneNode]:
        """Collect all descendants of a node in BFS order."""
        descendants = []
        queue = [node_name]
        while queue:
            current = queue.pop(0)
            children = [n for n in scene.nodes if n.parent == current]
            for child in children:
                descendants.append(child)
                queue.append(child.name)
        return descendants

    all_descendants = _collect_descendants(original_name)

    # Step 2: Build name remap with collision avoidance
    # Maps old_name -> new_name (renaming if needed to avoid collisions)
    name_remap: dict[str, str] = {}
    name_remap[original_name] = new_name

    # Track all existing names in the scene for collision detection
    existing_names = {n.name for n in scene.nodes}

    def _get_unique_name(base_name: str, parent_for_context: str) -> str:
        """Get a unique name that doesn't conflict with existing siblings."""
        # Check if base_name conflicts with any existing node under the same parent
        siblings_under_parent = [
            n.name for n in scene.nodes if n.parent == parent_for_context
        ]
        if base_name not in siblings_under_parent and base_name not in existing_names:
            return base_name

        # Add suffix to make it unique
        counter = 2
        while True:
            candidate = f"{base_name}_{counter}"
            if (
                candidate not in siblings_under_parent
                and candidate not in existing_names
            ):
                return candidate
            counter += 1

    for desc in all_descendants:
        # Determine the new parent for this descendant
        if desc.parent == original_name:
            new_parent = new_name
        else:
            new_parent = name_remap.get(desc.parent, desc.parent)

        # Get unique name for this descendant
        unique_name = _get_unique_name(desc.name, new_parent)
        name_remap[desc.name] = unique_name

    # Step 3: Create duplicates with remapped parents and unique names
    for desc in all_descendants:
        # Determine new parent
        if desc.parent == original_name:
            new_parent = new_name
        else:
            new_parent = name_remap.get(desc.parent, desc.parent)

        new_name_for_desc = name_remap[desc.name]

        child_copy = SceneNode(
            name=new_name_for_desc,
            type=desc.type,
            parent=new_parent,
            unique_name_in_owner=desc.unique_name_in_owner,
        )
        child_copy.properties = desc.properties.copy()
        scene.nodes.append(child_copy)
        duplicated_nodes.append(new_name_for_desc)

    # Guardar
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "original_node": original_node.name,
        "duplicated_nodes": duplicated_nodes,
        "scene_path": scene_path,
    }


@require_session
def find_nodes(
    session_id: str,
    scene_path: str,
    name_pattern: str = None,
    type_filter: str = None,
) -> dict:
    """
    Find nodes by name pattern or type.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name_pattern: Optional name pattern to search (fuzzy match).
        type_filter: Optional node type to filter (e.g., "Sprite2D").

    Returns:
        Dict with matching nodes and their paths.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": "Scene file not found",
        }

    scene = parse_tscn(scene_path)

    results = []

    for node in scene.nodes:
        # Filtrar por tipo
        if type_filter:
            if node.type.lower() != type_filter.lower():
                continue

        # Filtrar/buscar por nombre
        if name_pattern:
            if FUZZY_AVAILABLE:
                ratio = fuzz.ratio(name_pattern.lower(), node.name.lower())
                if ratio < 60:  # Threshold de similarity
                    continue
                results.append(
                    {
                        "name": node.name,
                        "type": node.type,
                        "parent": node.parent,
                        "path": f"{node.parent}/{node.name}"
                        if node.parent != "."
                        else node.name,
                        "match_score": ratio,
                    }
                )
            else:
                # Sin fuzzywuzzy, búsqueda simple
                if name_pattern.lower() not in node.name.lower():
                    continue
                results.append(
                    {
                        "name": node.name,
                        "type": node.type,
                        "parent": node.parent,
                        "path": f"{node.parent}/{node.name}"
                        if node.parent != "."
                        else node.name,
                    }
                )
        else:
            # Sin patrón, solo tipo
            results.append(
                {
                    "name": node.name,
                    "type": node.type,
                    "parent": node.parent,
                    "path": f"{node.parent}/{node.name}"
                    if node.parent != "."
                    else node.name,
                }
            )

    return {
        "success": True,
        "count": len(results),
        "nodes": results,
    }


# ============ NODE GROUPS ============


@require_session
def add_node_groups(
    session_id: str,
    scene_path: str,
    node_path: str,
    groups: list[str],
) -> dict:
    """
    Add groups to a node.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node.
        groups: List of group names to add.

    Returns:
        Dict with success status and updated groups.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result

    # Add groups (avoid duplicates)
    current_groups = set(node.groups)
    for group in groups:
        current_groups.add(group)
    node.groups = sorted(list(current_groups))

    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "node": node_path,
        "groups": node.groups,
        "added": groups,
        "scene_path": scene_path,
    }


@require_session
def remove_node_groups(
    session_id: str,
    scene_path: str,
    node_path: str,
    groups: list[str],
) -> dict:
    """
    Remove groups from a node.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node.
        groups: List of group names to remove.

    Returns:
        Dict with success status and updated groups.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result

    # Remove groups
    removed = []
    for group in groups:
        if group in node.groups:
            node.groups.remove(group)
            removed.append(group)

    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "node": node_path,
        "groups": node.groups,
        "removed": removed,
        "scene_path": scene_path,
    }


# ============ REGISTRATION ============


def register_node_tools(mcp) -> None:
    """
    Registrar todas las herramientas relacionadas con nodos.

    Args:
        mcp: Instancia de FastMCP donde registrar las herramientas.
    """
    logger.info("Registrando node_tools (CRUD)...")

    # Registrar todas las herramientas
    mcp.add_tool(add_ext_resource)
    mcp.add_tool(add_node)
    mcp.add_tool(remove_node)
    mcp.add_tool(update_node)
    mcp.add_tool(get_node_properties)
    mcp.add_tool(rename_node)
    mcp.add_tool(move_node)
    mcp.add_tool(duplicate_node)
    mcp.add_tool(find_nodes)
    mcp.add_tool(add_node_groups)
    mcp.add_tool(remove_node_groups)

    logger.info(
        "[OK] 11 node_tools registradas (fuzzywuzzy=%s)",
        "enabled" if FUZZY_AVAILABLE else "disabled",
    )
