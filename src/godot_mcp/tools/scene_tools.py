"""
Herramientas FastMCP para operaciones CRUD de escenas Godot.

Provee herramientas para:
- Crear nuevas escenas
- Leer jerarquía de nodos
- Guardar escenas modificadas
- Listar escenas del proyecto
- Instanciar escenas

Usa el parser TSCN nativo y cache LRU para optimizar operaciones.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Import cache and parser
from godot_mcp.core.cache import LRUCache, get_cache as _get_cache_func
from godot_mcp.core.tscn_parser import (
    GdSceneHeader,
    Scene,
    SceneNode,
    SubResource,
    parse_tscn,
    parse_tscn_string,
)
from godot_mcp.core.tscn_validator import TSCNValidator
from godot_mcp.tools.node_tools import _mark_scene_dirty


# ==================== Cache Compartido ====================


def _get_scene_cache() -> LRUCache:
    """Obtiene el cache de escenas."""
    return _get_cache_func(max_size=100)


# ==================== Decoradores ====================

from godot_mcp.tools.decorators import require_session


# ==================== Herramientas MCP ====================


@require_session
def create_scene(
    session_id: str,
    project_path: str,
    scene_path: str,
    root_type: str = "Node2D",
    root_name: str = "Root",
    inherits: str = "",
) -> dict:
    """
    Create a new scene in the project.

    Args:
        session_id: Session ID from start_session.
        project_path: Absolute path to the Godot project directory.
        scene_path: Relative path for the scene (e.g., "scenes/Player.tscn").
        root_type: Godot node type for root (default: "Node2D").
        root_name: Name for root node (default: "Root").
        inherits: Optional path to base scene for inherited scenes (e.g., "res://scenes/Base.tscn").

    Returns:
        Dict with success status and scene info.
    """
    try:
        # Validate project path
        if not os.path.isdir(project_path):
            return {
                "success": False,
                "error": f"Project path does not exist: {project_path}",
            }

        # Check for project.godot
        project_file = os.path.join(project_path, "project.godot")
        if not os.path.isfile(project_file):
            return {
                "success": False,
                "error": f"Not a valid Godot project (no project.godot): {project_path}",
            }

        # Build full scene path
        if not scene_path.endswith(".tscn"):
            scene_path = scene_path + ".tscn"

        full_scene_path = os.path.join(project_path, scene_path)

        # Check if file already exists
        if os.path.isfile(full_scene_path):
            return {
                "success": False,
                "error": f"Scene already exists: {scene_path}",
            }

        # Create directory if needed
        scene_dir = os.path.dirname(full_scene_path)
        if scene_dir and not os.path.isdir(scene_dir):
            os.makedirs(scene_dir, exist_ok=True)

        # Create basic scene
        if inherits:
            # Inherited scene: no root node, inherits from base scene
            scene = Scene(
                header=GdSceneHeader(load_steps=2, format=3, inherits=inherits),
                nodes=[],
            )
        else:
            scene = Scene(
                header=GdSceneHeader(load_steps=2, format=3),
                nodes=[
                    SceneNode(
                        name=root_name,
                        type=root_type,
                        parent=".",
                    )
                ],
            )

        # Validate before writing
        validator = TSCNValidator(project_path=project_path)
        validation_result = validator.validate(scene)

        if not validation_result.is_valid:
            return {
                "success": False,
                "error": f"Scene validation failed: {'; '.join(validation_result.errors)}",
                "validation_errors": validation_result.errors,
                "validation_warnings": validation_result.warnings,
            }

        # Write to disk
        with open(full_scene_path, "w", encoding="utf-8") as f:
            f.write(scene.to_tscn())

        # Mark as dirty for commit tracking
        _mark_scene_dirty(full_scene_path)

        # Add to cache (empty until loaded properly)
        cache = _get_scene_cache()
        cache.set(full_scene_path, scene)

        result = {
            "success": True,
            "scene_path": scene_path,
            "root_type": root_type if not inherits else None,
            "root_name": root_name if not inherits else None,
        }
        if inherits:
            result["inherits"] = inherits
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def get_scene_tree(session_id: str, scene_path: str) -> dict:
    """
    Get full node hierarchy as JSON.

    Args:
        session_id: Session ID from start_session.
        scene_path: Absolute path to the .tscn file.

    Returns:
        Dict with scene data or error message.
    """
    try:
        # Validate file exists
        if not os.path.isfile(scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        # Try cache first
        cache = _get_scene_cache()
        cached = cache.get(scene_path)

        if cached is not None:
            return {
                "success": True,
                "scene_path": scene_path,
                "from_cache": True,
                "data": cached.to_dict(),
            }

        # Parse the scene
        scene = parse_tscn(scene_path)

        # Cache the result
        cache.set(scene_path, scene)

        return {
            "success": True,
            "scene_path": scene_path,
            "from_cache": False,
            "data": scene.to_dict(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def save_scene(
    session_id: str, scene_path: str, scene_data: dict, project_path: str | None = None
) -> dict:
    """
    Save scene to disk.

    Args:
        session_id: Session ID from start_session.
        scene_path: Absolute path to the .tscn file.
        scene_data: Dict with scene structure (from get_scene_tree).
        project_path: Absolute path to the Godot project. If provided,
            validates that ExtResource files exist on disk.

    Returns:
        Dict with success status or error message.
    """
    try:
        # Rebuild Scene object from dict
        scene = Scene()

        # Parse header
        if "header" in scene_data:
            header_data = scene_data["header"]
            scene.header = GdSceneHeader(
                load_steps=header_data.get("load_steps", 2),
                format=header_data.get("format", 3),
                uid=header_data.get("uid", ""),
                scene_unique_name=header_data.get("scene_unique_name", ""),
                inherits=header_data.get("inherits", ""),
            )

        # Parse external resources
        if "ext_resources" in scene_data:
            from godot_mcp.core.tscn_parser import ExtResource

            for res in scene_data["ext_resources"]:
                scene.ext_resources.append(
                    ExtResource(
                        type=res.get("type", ""),
                        path=res.get("path", ""),
                        id=res.get("id", ""),
                        uid=res.get("uid", ""),
                    )
                )

        # Parse sub resources
        if "sub_resources" in scene_data:
            for sub in scene_data["sub_resources"]:
                scene.sub_resources.append(
                    SubResource(
                        type=sub.get("type", ""),
                        id=sub.get("id", ""),
                        uid=sub.get("uid", ""),
                        properties=sub.get("properties", {}),
                    )
                )

        # Parse nodes
        if "nodes" in scene_data:
            for node_data in scene_data["nodes"]:
                scene.nodes.append(
                    SceneNode(
                        name=node_data.get("name", ""),
                        type=node_data.get("type", ""),
                        parent=node_data.get("parent", "."),
                        unique_name_in_owner=node_data.get(
                            "unique_name_in_owner", False
                        ),
                        instance=node_data.get("instance", ""),
                        properties=node_data.get("properties", {}),
                    )
                )

        # Parse connections
        if "connections" in scene_data:
            from godot_mcp.core.tscn_parser import Connection

            for conn in scene_data["connections"]:
                scene.connections.append(
                    Connection(
                        from_node=conn.get("from_node", ""),
                        signal=conn.get("signal", ""),
                        to_node=conn.get("to_node", ""),
                        method=conn.get("method", ""),
                        flags=conn.get("flags", 0),
                        binds=conn.get("binds", []),
                    )
                )

        # Validate before writing
        validator = TSCNValidator(project_path=project_path)
        validation_result = validator.validate(scene)

        if not validation_result.is_valid:
            return {
                "success": False,
                "error": f"Scene validation failed: {'; '.join(validation_result.errors)}",
                "validation_errors": validation_result.errors,
                "validation_warnings": validation_result.warnings,
            }

        # Log warnings if any
        if validation_result.warnings:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Scene validation warnings: {validation_result.warnings}")

        # Write to file
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write(scene.to_tscn())

        # Mark as dirty for commit tracking
        _mark_scene_dirty(scene_path)

        # Invalidate cache
        cache = _get_scene_cache()
        cache.invalidate(scene_path)

        return {
            "success": True,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def list_scenes(session_id: str, project_path: str, recursive: bool = True) -> dict:
    """
    List all .tscn files in project.

    Args:
        session_id: Session ID from start_session.
        project_path: Absolute path to the Godot project directory.
        recursive: If True, search subdirectories (default: True).

    Returns:
        Dict with list of scene file paths relative to project.
    """
    try:
        # Validate project path
        if not os.path.isdir(project_path):
            return {
                "success": False,
                "error": f"Project path does not exist: {project_path}",
            }

        scenes: list[dict] = []
        base_path = Path(project_path)

        # Search patterns
        if recursive:
            pattern = "**/*.tscn"
        else:
            pattern = "*.tscn"

        # Find all .tscn files
        for tscn_file in base_path.glob(pattern):
            if tscn_file.is_file():
                rel_path = tscn_file.relative_to(base_path)
                scenes.append(
                    {
                        "path": str(rel_path).replace(os.sep, "/"),
                        "name": tscn_file.stem,
                    }
                )

        # Sort by path
        scenes.sort(key=lambda x: x["path"])

        return {
            "success": True,
            "project_path": project_path,
            "count": len(scenes),
            "scenes": scenes,
        }

    except Exception as e:
        return [
            {
                "success": False,
                "error": str(e),
            }
        ]


@require_session
def modify_scene(
    session_id: str,
    project_path: str,
    scene_path: str,
    new_root_type: Optional[str] = None,
    new_root_name: Optional[str] = None,
) -> dict:
    """
    Modifica una escena existente.

    Args:
        session_id: Session ID from start_session.
        project_path: Absolute path to the Godot project directory.
        scene_path: Path to the scene file (relative to project).
        new_root_type: Optional new root node type (e.g., "Node2D", "CharacterBody2D").
        new_root_name: Optional new root node name.

    Returns:
        Dict with success status and updated scene info.
    """
    try:
        # Validate project path
        if not os.path.isdir(project_path):
            return {
                "success": False,
                "error": f"Project path does not exist: {project_path}",
            }

        # Build full scene path
        if not scene_path.endswith(".tscn"):
            scene_path = scene_path + ".tscn"

        full_scene_path = os.path.join(project_path, scene_path)

        # Check if file exists
        if not os.path.isfile(full_scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        # Parse the scene
        scene = parse_tscn(full_scene_path)

        if not scene.nodes:
            return {
                "success": False,
                "error": "Scene has no nodes",
            }

        # Modify root node (first node in the list with parent ".")
        root_node = None
        for node in scene.nodes:
            if node.parent == "." or node.parent == "":
                root_node = node
                break

        if not root_node:
            return {
                "success": False,
                "error": "Could not find root node",
            }

        changes = []

        # Apply new root type
        if new_root_type:
            old_type = root_node.type
            root_node.type = new_root_type
            changes.append(f"root_type: {old_type} -> {new_root_type}")

        # Apply new root name
        if new_root_name:
            old_name = root_node.name
            root_node.name = new_root_name
            changes.append(f"root_name: {old_name} -> {new_root_name}")

        if not changes:
            return {
                "success": False,
                "error": "No changes specified (use new_root_type or new_root_name)",
            }

        # Save the modified scene
        with open(full_scene_path, "w", encoding="utf-8") as f:
            f.write(scene.to_tscn())

        # Mark as dirty for commit tracking
        _mark_scene_dirty(full_scene_path)

        # Invalidate cache
        cache = _get_scene_cache()
        cache.invalidate(full_scene_path)

        return {
            "success": True,
            "scene_path": scene_path,
            "changes": changes,
            "new_root_type": root_node.type,
            "new_root_name": root_node.name,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def instantiate_scene(
    session_id: str,
    scene_path: str,
    parent_scene_path: str,
    node_name: str,
    parent_node_path: str = ".",
    project_path: str | None = None,
    editable_children: bool = False,
    unique_name_in_owner: bool = False,
    owner: str = "",
) -> dict:
    """
    Instantiate a scene as a node in another scene.

    Args:
        session_id: Session ID from start_session.
        scene_path: Absolute path to the scene to instantiate.
        parent_scene_path: Absolute path to the parent .tscn file.
        node_name: Name for the instantiated node.
        parent_node_path: Path to parent node in the parent scene (default: ".").
        project_path: Absolute path to the Godot project root. If provided,
            generates clean res:// paths relative to the project.
            Required when scenes are in different directories.
        editable_children: If True, marks this instance's children as editable
            in the parent scene (Godot 4.x [editable path="..."] format).
        unique_name_in_owner: If True, the node can be referenced with %name in GDScript.
        owner: Optional owner node path (Godot ownership system).

    Returns:
        Dict with success status or error message.
    """
    try:
        # Validate files exist
        if not os.path.isfile(scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        if not os.path.isfile(parent_scene_path):
            return {
                "success": False,
                "error": f"Parent scene not found: {parent_scene_path}",
            }

        # Parse parent scene
        cache = _get_scene_cache()
        parent = cache.get(parent_scene_path)

        if parent is None:
            parent = parse_tscn(parent_scene_path)
            cache.set(parent_scene_path, parent)

        # === Calculate res:// path ===
        # Strategy: Always calculate relative to project_path if available,
        # otherwise fall back to parent directory (legacy behavior).
        if project_path and os.path.isdir(project_path):
            # Calculate relative path from project root → always clean res://
            scene_rel = os.path.relpath(scene_path, project_path)
        else:
            # Fallback: relative to parent scene's directory
            parent_dir = os.path.dirname(parent_scene_path)
            scene_rel = os.path.relpath(scene_path, parent_dir)

            # Legacy fallback: if path goes up (..), try to find project root
            if scene_rel.startswith(".."):
                logger.warning(
                    f"instantiate_scene: scene is outside parent directory. "
                    f"Path '{scene_rel}' may be invalid. "
                    f"Provide project_path for correct res:// paths."
                )

        # Normalize path separators to forward slashes (Godot standard)
        scene_rel = scene_rel.replace(os.sep, "/")

        # Validate the resulting path doesn't contain ..
        if scene_rel.startswith(".."):
            return {
                "success": False,
                "error": (
                    f"Cannot create valid res:// path: '{scene_rel}'. "
                    f"The scene is outside the project directory. "
                    f"Provide a valid project_path parameter."
                ),
                "hint": "Both scenes must be within the same Godot project",
            }

        # Create packed scene reference using the scene name
        scene_name = Path(scene_path).stem

        # Check if we need to add an external resource
        from godot_mcp.core.tscn_parser import ExtResource
        from godot_mcp.tools.node_tools import (
            _find_sibling_by_name,
            _resolve_parent_path,
        )

        # Resolver parent path y verificar duplicados de hermanos
        resolved_parent = _resolve_parent_path(parent, parent_node_path)

        # Verificar que no exista un hermano con el mismo nombre bajo el mismo padre
        existing_sibling = _find_sibling_by_name(parent, resolved_parent, node_name)
        if existing_sibling:
            return {
                "success": False,
                "error": f"Node already exists under parent '{resolved_parent}': {node_name}",
                "hint": "Sibling names must be unique under the same parent",
            }

        # Find existing PackedScene resource or add new one
        target_path = f"res://{scene_rel}"

        # Check if ExtResource with this path already exists
        existing_ext = None
        for res in parent.ext_resources:
            if res.path == target_path:
                existing_ext = res
                break

        if existing_ext:
            # Reuse existing resource
            ext_id = existing_ext.id
        else:
            # Generate unique numeric ID
            numeric_ids = []
            for res in parent.ext_resources:
                try:
                    numeric_ids.append(int(res.id))
                except (ValueError, TypeError):
                    pass
            new_id = max(numeric_ids) + 1 if numeric_ids else 1
            ext_id = str(new_id)

            # Create and append new ExtResource
            packed_res = ExtResource(
                type="PackedScene",
                path=target_path,
                id=ext_id,
            )
            parent.ext_resources.append(packed_res)

        # Add instantiation node
        # Add instantiation node using Godot's native format:
        # [node name="X" parent="." instance=ExtResource("id")]
        # Note: NO type attribute, instance= goes in the header
        new_node = SceneNode(
            name=node_name,
            type="",  # Empty type - Godot infers from instance
            parent=resolved_parent,
            instance=ext_id,  # ExtResource ID in header, not as property
            unique_name_in_owner=unique_name_in_owner,
            owner=owner,
        )

        parent.nodes.append(new_node)

        # If editable_children is requested, add [editable path="..."] entry
        if editable_children:
            from godot_mcp.core.tscn_parser import EditablePath
            # Build the full node path for the editable declaration
            if resolved_parent == ".":
                editable_node_path = node_name
            else:
                editable_node_path = f"{resolved_parent}/{node_name}"
            parent.editable_paths.append(EditablePath(path=editable_node_path))
            logger.info(f"Marked children as editable: {editable_node_path}")

        # WORKAROUND: Deduplicate ExtResources before saving
        # Uses filesystem resolution when project_path is available to catch
        # cases where different res:// strings point to the same file on disk
        dedup_result = parent.deduplicate_ext_resources(project_path=project_path)
        if dedup_result["removed"] > 0:
            logger.info(
                f"instantiate_scene: deduplicated ExtResources in parent scene: "
                f"removed={dedup_result['removed']}, remapped={dedup_result['remapped']}"
            )

        # Save the parent scene
        with open(parent_scene_path, "w", encoding="utf-8") as f:
            f.write(parent.to_tscn())

        # Mark as dirty for commit tracking
        _mark_scene_dirty(parent_scene_path)

        # Invalidate cache
        cache.invalidate(parent_scene_path)

        return {
            "success": True,
            "scene_path": scene_path,
            "parent_scene_path": parent_scene_path,
            "node_name": node_name,
            "parent_node_path": parent_node_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def set_editable_paths(
    session_id: str,
    scene_path: str,
    paths: list[str],
) -> dict:
    """
    Set editable child paths for instantiated scenes (Godot 4.x format).

    In Godot 4.x, editable children are declared as [editable path="..."]
    lines at the end of the TSCN file, NOT as node attributes.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        paths: List of node paths to mark as editable (e.g., ["Kitchen", "Kitchen/Door"]).
               These are typically the paths of instantiated scene nodes whose
               children you want to be able to modify.

    Returns:
        Dict with success status and list of editable paths set.

    Example:
        set_editable_paths(
            scene_path="scenes/Day2.tscn",
            paths=["Kitchen", "Kitchen/Door", "Kitchen/Entities/Table", "IngredientsRoom"]
        )
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)

        if not os.path.exists(scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        scene = parse_tscn(scene_path)

        from godot_mcp.core.tscn_parser import EditablePath

        # Clear existing editable paths
        old_count = len(scene.editable_paths)
        scene.editable_paths = []

        # Add new editable paths
        for path in paths:
            scene.editable_paths.append(EditablePath(path=path))

        # Save
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write(scene.to_tscn())

        # Mark as dirty
        _mark_scene_dirty(scene_path)

        # Invalidate cache
        cache = _get_scene_cache()
        cache.invalidate(scene_path)

        return {
            "success": True,
            "scene_path": scene_path,
            "paths_set": paths,
            "paths_count": len(paths),
            "old_count": old_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def remove_ext_resource(
    session_id: str,
    scene_path: str,
    resource_id: str,
) -> dict:
    """
    Remove an external resource from a scene.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        resource_id: ID of the ExtResource to remove (e.g., "1", "2_abc").

    Returns:
        Dict with success status.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)

        if not os.path.exists(scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        scene = parse_tscn(scene_path)

        # Find the resource
        found = False
        for i, ext in enumerate(scene.ext_resources):
            if ext.id == resource_id:
                scene.ext_resources.pop(i)
                found = True
                break

        if not found:
            return {
                "success": False,
                "error": f"ExtResource '{resource_id}' not found in scene",
            }

        # Save
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write(scene.to_tscn())

        # Mark as dirty
        _mark_scene_dirty(scene_path)

        # Invalidate cache
        cache = _get_scene_cache()
        cache.invalidate(scene_path)

        return {
            "success": True,
            "scene_path": scene_path,
            "removed_resource_id": resource_id,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def remove_sub_resource(
    session_id: str,
    scene_path: str,
    resource_id: str,
) -> dict:
    """
    Remove a sub-resource from a scene.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        resource_id: ID of the SubResource to remove (e.g., "RectangleShape2D_abc123").

    Returns:
        Dict with success status.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)

        if not os.path.exists(scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        scene = parse_tscn(scene_path)

        # Find the resource
        found = False
        for i, sub in enumerate(scene.sub_resources):
            if sub.id == resource_id:
                scene.sub_resources.pop(i)
                found = True
                break

        if not found:
            return {
                "success": False,
                "error": f"SubResource '{resource_id}' not found in scene",
            }

        # Save
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write(scene.to_tscn())

        # Mark as dirty
        _mark_scene_dirty(scene_path)

        # Invalidate cache
        cache = _get_scene_cache()
        cache.invalidate(scene_path)

        return {
            "success": True,
            "scene_path": scene_path,
            "removed_resource_id": resource_id,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ==================== Registro de Herramientas ====================


def register_scene_tools(mcp: FastMCP) -> None:
    """
    Register all scene tools with a FastMCP server.

    Args:
        mcp: FastMCP instance to register tools with
    """
    mcp.add_tool(create_scene)
    mcp.add_tool(get_scene_tree)
    mcp.add_tool(save_scene)
    mcp.add_tool(list_scenes)
    mcp.add_tool(instantiate_scene)
    mcp.add_tool(modify_scene)
    mcp.add_tool(set_editable_paths)
    mcp.add_tool(remove_ext_resource)
    mcp.add_tool(remove_sub_resource)
