"""
Signal & Script Tools - Herramientas para signals, scripts y SubResources.

Proporciona herramientas FastMCP para:
- Conectar signals entre nodos (connect_signal)
- Adjuntar scripts .gd a nodos (set_script)
- Crear SubResources dedicados (add_sub_resource)
"""

import logging
import os
import re
from typing import Any, Optional

from godot_mcp.core.tscn_parser import (
    Scene,
    SceneNode,
    ExtResource,
    SubResource,
    Connection,
    parse_tscn,
)
from godot_mcp.tools.node_tools import (
    _ensure_tscn_path,
    _update_scene_file,
    _find_node_by_path,
    _generate_resource_id,
    _clean_resource_id,
    _process_resource_properties,
)
from godot_mcp.tools.decorators import require_session

logger = logging.getLogger(__name__)


# ============ CONNECT SIGNAL ============


@require_session
def connect_signal(
    session_id: str,
    scene_path: str,
    from_node: str,
    signal: str,
    to_node: str,
    method: str,
    flags: int = 0,
    binds: list[Any] | None = None,
) -> dict:
    """
    Connect a signal from one node to a method on another node.

    Creates a [connection] entry in the TSCN file.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        from_node: Node path that emits the signal (e.g., "Player/Area2D").
        signal: Name of the signal to connect (e.g., "body_entered").
        to_node: Node path that receives the signal (e.g., "Player").
        method: Name of the method to call (e.g., "_on_area_body_entered").
        flags: Connection flags (0 = default, 1 = oneshot, 2 = persistent).
        binds: Optional list of values to bind to the connection.

    Returns:
        Dict with success status and connection details.

    Example:
        connect_signal(
            scene_path="scenes/Player.tscn",
            from_node="Player/Area2D",
            signal="body_entered",
            to_node="Player",
            method="_on_area_body_entered"
        )
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    # Validate that from_node exists
    from_result = _find_node_by_path(scene, from_node)
    if not from_result:
        return {
            "success": False,
            "error": f"Source node not found: '{from_node}'",
            "hint": "Use find_nodes to list available nodes",
        }

    # Validate that to_node exists
    to_result = _find_node_by_path(scene, to_node)
    if not to_result:
        return {
            "success": False,
            "error": f"Target node not found: '{to_node}'",
            "hint": "Use find_nodes to list available nodes",
        }

    # Validate method exists on target node (best-effort)
    warnings = []
    _, to_node_obj = to_result
    script_ref = to_node_obj.properties.get("script")
    if script_ref:
        # Try to resolve script path
        script_path = None
        if isinstance(script_ref, str):
            match = re.search(r'ExtResource\("([^"]+)"\)', script_ref)
            if match:
                ext_id = match.group(1)
                for ext in scene.ext_resources:
                    if ext.id == ext_id and ext.type == "Script":
                        script_path = ext.path
                        break
        elif isinstance(script_ref, dict) and script_ref.get("type") == "ExtResource":
            ext_id = script_ref.get("ref", "")
            for ext in scene.ext_resources:
                if ext.id == ext_id and ext.type == "Script":
                    script_path = ext.path
                    break

        if script_path and script_path.startswith("res://"):
            # Try to find project root from scene path
            project_root = None
            scene_dir = os.path.dirname(scene_path)
            # Walk up to find project.godot
            current = scene_dir
            for _ in range(10):
                if os.path.isfile(os.path.join(current, "project.godot")):
                    project_root = current
                    break
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent

            if project_root:
                rel_path = script_path.replace("res://", "").replace("/", os.sep)
                abs_script_path = os.path.join(project_root, rel_path)
                if os.path.isfile(abs_script_path):
                    try:
                        with open(abs_script_path, "r", encoding="utf-8") as f:
                            script_content = f.read()
                        # Check for method definition
                        pattern = rf'\bfunc\s+{re.escape(method)}\s*\('
                        if not re.search(pattern, script_content):
                            warnings.append(
                                f"Method '{method}' not found in script '{script_path}'. "
                                "It may be inherited or a built-in method."
                            )
                    except Exception:
                        pass  # Ignore read errors

    # Check for duplicate connection
    for conn in scene.connections:
        if (
            conn.from_node == from_node
            and conn.signal == signal
            and conn.to_node == to_node
            and conn.method == method
        ):
            return {
                "success": True,
                "message": "Connection already exists",
                "connection": conn.to_dict(),
                "warnings": warnings,
            }

    # Create connection
    new_conn = Connection(
        from_node=from_node,
        signal=signal,
        to_node=to_node,
        method=method,
        flags=flags,
        binds=binds or [],
    )
    scene.connections.append(new_conn)

    # Save
    _update_scene_file(scene_path, scene)

    result = {
        "success": True,
        "message": f"Connected '{signal}' from '{from_node}' to '{to_node}.{method}'",
        "connection": new_conn.to_dict(),
        "scene_path": scene_path,
    }
    if warnings:
        result["warnings"] = warnings
    return result


# ============ DISCONNECT SIGNAL ============


@require_session
def disconnect_signal(
    session_id: str,
    scene_path: str,
    from_node: str,
    signal: str,
    to_node: str,
    method: str,
) -> dict:
    """
    Disconnect a signal from one node to a method on another node.

    Removes a [connection] entry from the TSCN file.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        from_node: Node path that emits the signal (e.g., "Player/Area2D").
        signal: Name of the signal to disconnect (e.g., "body_entered").
        to_node: Node path that receives the signal (e.g., "Player").
        method: Name of the method to disconnect (e.g., "_on_area_body_entered").

    Returns:
        Dict with success status.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    # Find and remove the connection
    removed = None
    for i, conn in enumerate(scene.connections):
        if (
            conn.from_node == from_node
            and conn.signal == signal
            and conn.to_node == to_node
            and conn.method == method
        ):
            removed = scene.connections.pop(i)
            break

    if not removed:
        return {
            "success": False,
            "error": f"Connection not found: {signal} from {from_node} to {to_node}.{method}",
        }

    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "message": f"Disconnected '{signal}' from '{from_node}' to '{to_node}.{method}'",
        "connection": removed.to_dict(),
        "scene_path": scene_path,
    }


# ============ LIST SIGNALS ============


@require_session
def list_signals(
    session_id: str,
    scene_path: str,
) -> dict:
    """
    List all signal connections in a scene.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.

    Returns:
        Dict with success status and list of connections.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    connections = [conn.to_dict() for conn in scene.connections]

    return {
        "success": True,
        "count": len(connections),
        "connections": connections,
        "scene_path": scene_path,
    }


# ============ SET SCRIPT ============


@require_session
def set_script(
    session_id: str,
    scene_path: str,
    node_path: str,
    script_path: str,
) -> dict:
    """
    Attach a GDScript file to a node in one step.

    Combines add_ext_resource + update_node automatically.
    If the script is already registered as an ExtResource, reuses it.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node to attach the script to.
        script_path: Path to the .gd file (e.g., "res://scripts/player.gd").

    Returns:
        Dict with success status and script reference info.

    Example:
        set_script(
            scene_path="scenes/Player.tscn",
            node_path="Player",
            script_path="res://scripts/player.gd"
        )
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    if not script_path.endswith(".gd"):
        return {
            "success": False,
            "error": "Script path must end with .gd",
            "script_path": script_path,
        }

    scene = parse_tscn(scene_path)

    # Find the node
    node_result = _find_node_by_path(scene, node_path)
    if not node_result:
        return {
            "success": False,
            "error": f"Node not found: '{node_path}'",
            "hint": "Use find_nodes to list available nodes",
        }

    idx, node = node_result

    # Check if script is already an ExtResource
    existing_ext = None
    for ext in scene.ext_resources:
        if ext.path == script_path and ext.type == "Script":
            existing_ext = ext
            break

    if existing_ext:
        resource_id = existing_ext.id
    else:
        # Generate new ExtResource
        max_id = 0
        for ext in scene.ext_resources:
            try:
                num_id = int(ext.id)
                if num_id > max_id:
                    max_id = num_id
            except (ValueError, TypeError):
                pass
        resource_id = str(max_id + 1)

        new_ext = ExtResource(
            type="Script",
            path=script_path,
            id=resource_id,
        )
        scene.ext_resources.append(new_ext)

    # Set script property on node
    node.properties["script"] = f'ExtResource("{_clean_resource_id(resource_id)}")'

    # Update load_steps
    scene.header.load_steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)

    # Save
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "message": f"Attached script to node '{node.name}'",
        "node": node.name,
        "script_path": script_path,
        "resource_id": resource_id,
        "scene_path": scene_path,
    }


# ============ ADD SUB RESOURCE ============


@require_session
def add_sub_resource(
    session_id: str,
    scene_path: str,
    resource_type: str,
    properties: dict[str, Any] | None = None,
    resource_id: str | None = None,
) -> dict:
    """
    Create a SubResource in the scene.

    Useful for creating shapes, materials, tilesets, etc. that are
    embedded in the scene file.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        resource_type: Godot resource type (e.g., "RectangleShape2D",
                       "CircleShape2D", "TileSet", "StandardMaterial3D").
        properties: Dict of properties to set on the resource.
                    Supports nested types like Vector2, Color via dict format:
                    {"size": {"type": "Vector2", "x": 32, "y": 32}}
        resource_id: Optional custom ID. If None, auto-generates one.

    Returns:
        Dict with success status and the resource ID to use in references.

    Example:
        # Create a rectangle shape
        add_sub_resource(
            scene_path="scenes/Player.tscn",
            resource_type="RectangleShape2D",
            properties={"size": {"type": "Vector2", "x": 32, "y": 32}}
        )

        # Create a circle shape
        add_sub_resource(
            scene_path="scenes/Player.tscn",
            resource_type="CircleShape2D",
            properties={"radius": 16.0}
        )
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    scene = parse_tscn(scene_path)

    # Generate ID if not provided
    if resource_id is None:
        resource_id = f"{resource_type}_{_generate_resource_id()}"

    resource_id = _clean_resource_id(resource_id)

    # Check for duplicate ID
    for sub in scene.sub_resources:
        if sub.id == resource_id:
            return {
                "success": False,
                "error": f"SubResource ID '{resource_id}' already exists",
            }

    # Process properties - store as-is (the parser handles dict types during serialization)
    processed_props = {}
    if properties:
        for key, value in properties.items():
            if isinstance(value, dict) and "type" in value:
                # Typed values like Vector2, Color - store as dict for proper serialization
                processed_props[key] = value
            else:
                processed_props[key] = value

    # Create SubResource
    new_sub = SubResource(
        type=resource_type,
        id=resource_id,
        properties=processed_props,
    )
    scene.sub_resources.append(new_sub)

    # Update load_steps
    scene.header.load_steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)

    # Save
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "message": f"Created SubResource '{resource_type}' with id '{resource_id}'",
        "resource_id": resource_id,
        "resource_type": resource_type,
        "reference": f'SubResource("{resource_id}")',
        "scene_path": scene_path,
    }


# ============ REGISTRATION ============


def register_signal_and_script_tools(mcp) -> None:
    """
    Register all signal, script, and subresource tools.

    Args:
        mcp: FastMCP instance to register tools on.
    """
    logger.info("Registrando signal & script tools...")

    mcp.add_tool(connect_signal)
    mcp.add_tool(disconnect_signal)
    mcp.add_tool(list_signals)
    mcp.add_tool(set_script)
    mcp.add_tool(add_sub_resource)

    logger.info("[OK] 5 signal & script tools registradas")
