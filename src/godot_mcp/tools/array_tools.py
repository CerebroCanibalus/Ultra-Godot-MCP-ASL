"""
Array Operations - Herramientas para manipular arrays en escenas Godot.

Provee operaciones quirúrgicas sobre arrays sin reescribir todo el archivo:
- append: Añadir elemento al final
- remove: Quitar elemento por índice o valor
- replace: Reemplazar elemento por índice
- insert: Insertar elemento en posición específica
- clear: Vaciar array

Preserva el tipo del array (Array[Type]) y metadatos de la escena.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from godot_mcp.core.tscn_parser import Scene, parse_tscn
from godot_mcp.tools.node_tools import (
    _ensure_tscn_path,
    _update_scene_file,
    _find_node_by_path,
)
from godot_mcp.tools.decorators import require_session

logger = logging.getLogger(__name__)


@require_session
def scene_array_operation(
    session_id: str,
    scene_path: str,
    node_path: str,
    property_name: str,
    operation: str,  # "append", "remove", "replace", "insert", "clear"
    value: Any = None,
    index: int = -1,
) -> dict:
    """
    Perform surgical array operations without rewriting the entire scene file.

    Preserves array type (Array[Type]) and all scene metadata.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        node_path: Path or name of the node containing the array.
        property_name: Name of the array property (e.g., "scenes", "enemies").
        operation: One of "append", "remove", "replace", "insert", "clear".
        value: Value to add/replace (for append, replace, insert).
        index: Position for remove/replace/insert operations.

    Returns:
        Dict with success status and operation details.

    Examples:
        # Append an ExtResource to an array
        scene_array_operation(
            scene_path="spawner.tscn",
            node_path="Spawner",
            property_name="scenes",
            operation="append",
            value={"type": "ExtResource", "ref": "3_newscene"}
        )

        # Remove element at index 2
        scene_array_operation(
            scene_path="spawner.tscn",
            node_path="Spawner",
            property_name="scenes",
            operation="remove",
            index=2
        )

        # Replace element at index 0
        scene_array_operation(
            scene_path="spawner.tscn",
            node_path="Spawner",
            property_name="scenes",
            operation="replace",
            index=0,
            value={"type": "ExtResource", "ref": "4_other"}
        )
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": f"Scene file not found: {scene_path}",
        }

    # Validate operation
    valid_operations = {"append", "remove", "replace", "insert", "clear"}
    if operation not in valid_operations:
        return {
            "success": False,
            "error": f"Invalid operation '{operation}'. Must be one of: {valid_operations}",
        }

    scene = parse_tscn(scene_path)

    # Find node
    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result

    # Check property exists
    if property_name not in node.properties:
        return {
            "success": False,
            "error": f"Property '{property_name}' not found in node '{node.name}'",
            "available_properties": list(node.properties.keys()),
        }

    # Get current array value
    current_value = node.properties[property_name]

    # Handle case where property is not an array
    if isinstance(current_value, dict) and current_value.get("type") == "Array":
        array_data = current_value
        items = array_data.get("items", [])
        array_type = array_data.get("array_type")
    elif isinstance(current_value, list):
        # Plain list (shouldn't happen in Godot 4.x but handle anyway)
        array_data = {"type": "Array", "items": current_value}
        items = current_value
        array_type = None
    else:
        return {
            "success": False,
            "error": f"Property '{property_name}' is not an array. Current type: {type(current_value).__name__}",
        }

    # Perform operation
    original_items = items.copy()
    modified = False

    if operation == "append":
        if value is None:
            return {
                "success": False,
                "error": "Value is required for 'append' operation",
            }
        items.append(value)
        modified = True

    elif operation == "remove":
        if index >= 0:
            # Remove by index
            if index >= len(items):
                return {
                    "success": False,
                    "error": f"Index {index} out of bounds (array has {len(items)} items)",
                }
            removed = items.pop(index)
            modified = True
        elif value is not None:
            # Remove by value
            try:
                items.remove(value)
                modified = True
            except ValueError:
                return {
                    "success": False,
                    "error": f"Value not found in array: {value}",
                }
        else:
            return {
                "success": False,
                "error": "Either 'index' or 'value' is required for 'remove' operation",
            }

    elif operation == "replace":
        if index < 0:
            return {
                "success": False,
                "error": "Index is required for 'replace' operation",
            }
        if value is None:
            return {
                "success": False,
                "error": "Value is required for 'replace' operation",
            }
        if index >= len(items):
            return {
                "success": False,
                "error": f"Index {index} out of bounds (array has {len(items)} items)",
            }
        items[index] = value
        modified = True

    elif operation == "insert":
        if index < 0:
            return {
                "success": False,
                "error": "Index is required for 'insert' operation",
            }
        if value is None:
            return {
                "success": False,
                "error": "Value is required for 'insert' operation",
            }
        if index > len(items):
            index = len(items)  # Clamp to end
        items.insert(index, value)
        modified = True

    elif operation == "clear":
        items.clear()
        modified = True

    if not modified:
        return {
            "success": True,
            "message": "No changes made",
            "property": property_name,
            "operation": operation,
        }

    # Update the property with modified array
    new_array_data = {"type": "Array", "items": items}
    if array_type:
        new_array_data["array_type"] = array_type
    node.properties[property_name] = new_array_data

    # Save scene
    _update_scene_file(scene_path, scene)

    return {
        "success": True,
        "property": property_name,
        "operation": operation,
        "old_count": len(original_items),
        "new_count": len(items),
        "node_name": node.name,
        "scene_path": scene_path,
    }


@require_session
def preview_array_operation(
    session_id: str,
    scene_path: str,
    node_path: str,
    property_name: str,
    operation: str,
    value: Any = None,
    index: int = -1,
) -> dict:
    """
    Preview what an array operation would do without applying it.

    Returns a diff showing the changes that would be made.
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {
            "success": False,
            "error": f"Scene file not found: {scene_path}",
        }

    scene = parse_tscn(scene_path)

    result = _find_node_by_path(scene, node_path)
    if not result:
        return {
            "success": False,
            "error": f"Node not found: {node_path}",
        }

    idx, node = result

    if property_name not in node.properties:
        return {
            "success": False,
            "error": f"Property '{property_name}' not found",
        }

    current_value = node.properties[property_name]
    if isinstance(current_value, dict) and current_value.get("type") == "Array":
        items = current_value.get("items", [])
        array_type = current_value.get("array_type")
    elif isinstance(current_value, list):
        items = current_value
        array_type = None
    else:
        return {
            "success": False,
            "error": f"Property is not an array",
        }

    # Simulate operation
    preview_items = items.copy()
    preview_message = ""

    if operation == "append" and value is not None:
        preview_items.append(value)
        preview_message = f"Would append 1 item (total: {len(items)} → {len(preview_items)})"
    elif operation == "remove":
        if index >= 0 and index < len(items):
            preview_items.pop(index)
            preview_message = f"Would remove item at index {index} (total: {len(items)} → {len(preview_items)})"
        elif value is not None:
            try:
                preview_items.remove(value)
                preview_message = f"Would remove matching item (total: {len(items)} → {len(preview_items)})"
            except ValueError:
                preview_message = "Item not found - no changes"
    elif operation == "replace" and index >= 0 and value is not None:
        if index < len(items):
            preview_items[index] = value
            preview_message = f"Would replace item at index {index}"
    elif operation == "insert" and index >= 0 and value is not None:
        preview_items.insert(min(index, len(preview_items)), value)
        preview_message = f"Would insert at index {index} (total: {len(items)} → {len(preview_items)})"
    elif operation == "clear":
        preview_items.clear()
        preview_message = f"Would clear array ({len(items)} → 0 items)"

    return {
        "success": True,
        "preview": True,
        "property": property_name,
        "operation": operation,
        "current_count": len(items),
        "preview_count": len(preview_items),
        "message": preview_message,
        "current_items": items,
        "preview_items": preview_items,
        "array_type": array_type,
    }


def register_array_tools(mcp) -> None:
    """Register array operation tools with FastMCP server."""
    logger.info("Registrando array_tools...")
    mcp.add_tool(scene_array_operation)
    mcp.add_tool(preview_array_operation)
    logger.info("[OK] 2 array_tools registradas")