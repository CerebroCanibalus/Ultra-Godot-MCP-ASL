"""
Resource Builder Tools - Herramientas genéricas para crear SubResources complejos.

Proporciona herramientas FastMCP para:
- Crear SubResources con propiedades complejas (tracks, states, etc.)
- Construir jerarquías de SubResources con referencias cruzadas
- Helpers de alto nivel para recursos comunes (Animation, StateMachine, etc.)

Diseño:
- Capa 1: build_resource (genérica, cualquier recurso)
- Capa 2: build_nested_resource (jerarquías con referencias cruzadas)
- Capa 3: Helpers específicos (create_animation, create_state_machine, etc.)
"""

from __future__ import annotations

import logging
import os
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


# ============ UTILIDADES DE FLATTENING ============


# Known GDScript typed value types (these should NOT be flattened)
_TYPED_VALUE_TYPES = {
    "Vector2", "Vector2i", "Vector3", "Vector3i", "Vector4", "Vector4i",
    "Color", "Rect2", "Rect2i", "Transform2D", "Transform3D", "Quaternion",
    "Plane", "AABB", "Basis", "Projection",
    "ExtResource", "SubResource", "NodePath",
    "Array", "Dictionary",
    "PackedByteArray", "PackedInt32Array", "PackedInt64Array",
    "PackedFloat32Array", "PackedFloat64Array",
    "PackedStringArray", "PackedVector2Array", "PackedVector3Array",
    "PackedColorArray",
}


def _is_typed_value(value: Any) -> bool:
    """Check if a dict is a typed GDScript value (Vector2, Color, SubResource ref, etc.)"""
    if not isinstance(value, dict):
        return False
    return value.get("type") in _TYPED_VALUE_TYPES


def _flatten_properties(
    props: dict[str, Any],
    prefix: str = "",
    array_properties: set[str] | None = None,
) -> dict[str, Any]:
    """
    Flatten nested dict properties into TSCN flat key format.

    Converts:
        {"tracks": [{"type": "value", "path": "Node:prop"}]}
    Into:
        {"tracks/0/type": "value", "tracks/0/path": "Node:prop"}

    Rules:
    - Dicts with "type" key matching a GDScript type → keep as-is
    - Other dicts are structural → flatten with slash notation
    - Lists are flattened with index notation UNLESS the property name
      is in `array_properties` (kept as flat array)
    - Primitives are kept as-is

    Args:
        props: Properties to flatten.
        prefix: Key prefix for recursive calls.
        array_properties: Set of property names that should remain as
                         flat arrays (not expanded to index notation).
                         Examples: "transitions", "bones", "points".
    """
    if array_properties is None:
        array_properties = set()

    result = {}

    for key, value in props.items():
        full_key = f"{prefix}/{key}" if prefix else key

        if value is None:
            result[full_key] = None

        elif isinstance(value, dict):
            if _is_typed_value(value):
                # Typed value (Vector2, Color, SubResource ref, Array, etc.)
                result[full_key] = value
            else:
                # Structural dict → flatten recursively
                nested = _flatten_properties(
                    value, prefix=full_key, array_properties=array_properties
                )
                result.update(nested)

        elif isinstance(value, list):
            if key in array_properties:
                # Keep as flat array (e.g., transitions, bones, points)
                formatted_items = []
                for item in value:
                    if isinstance(item, dict) and _is_typed_value(item):
                        formatted_items.append(item)
                    elif isinstance(item, str):
                        formatted_items.append(item)
                    else:
                        formatted_items.append(item)
                result[full_key] = {"type": "Array", "items": formatted_items}
            elif not value:
                # Empty list → store as empty array
                result[full_key] = {"type": "Array", "items": []}
            else:
                for i, item in enumerate(value):
                    item_key = f"{full_key}/{i}"
                    if isinstance(item, dict):
                        if _is_typed_value(item):
                            result[item_key] = item
                        else:
                            nested = _flatten_properties(
                                item, prefix=item_key, array_properties=array_properties
                            )
                            result.update(nested)
                    else:
                        result[item_key] = item

        else:
            # Primitive (int, float, str, bool)
            result[full_key] = value

    return result


def _build_sub_resource(
    scene: Scene,
    resource_type: str,
    properties: dict[str, Any],
    resource_id: str | None = None,
    array_properties: set[str] | None = None,
) -> str:
    """
    Internal: Create a SubResource in a scene object.

    Returns the resource_id.
    """
    if resource_id is None:
        resource_id = f"{resource_type}_{_generate_resource_id()}"

    resource_id = _clean_resource_id(resource_id)

    # Check for duplicate ID
    for sub in scene.sub_resources:
        if sub.id == resource_id:
            raise ValueError(f"SubResource ID '{resource_id}' already exists")

    # Flatten properties
    flat_props = _flatten_properties(
        properties, array_properties=array_properties
    )

    # Create SubResource
    new_sub = SubResource(
        type=resource_type,
        id=resource_id,
        properties=flat_props,
    )
    scene.sub_resources.append(new_sub)

    return resource_id


# ============ CAPA 1: BUILD RESOURCE (Genérica) ============


@require_session
def build_resource(
    session_id: str,
    scene_path: str,
    resource_type: str,
    properties: dict[str, Any],
    resource_id: str | None = None,
    array_properties: set[str] | None = None,
) -> dict:
    """
    Create a SubResource with complex nested properties.

    Automatically flattens nested dicts/lists into TSCN flat key format.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        resource_type: Godot resource type (e.g., "Animation",
                       "AnimationNodeStateMachine", "ParticleProcessMaterial").
        properties: Nested dict of properties. Automatically flattened.
        resource_id: Optional custom ID. Auto-generates if None.
        array_properties: Set of property names that should remain as
                         flat arrays instead of being expanded to index notation.
                         Common: {"transitions", "bones", "points"}.

    Returns:
        Dict with success status and resource info.

    Examples:
        # Create an Animation with tracks
        build_resource(
            scene_path="scenes/Player.tscn",
            resource_type="Animation",
            resource_id="anim_idle",
            properties={
                "length": 1.0,
                "loop_mode": 1,
                "tracks": [
                    {
                        "type": "value",
                        "path": "Sprite2D:position",
                        "keys": {
                            "times": [0.0, 0.5, 1.0],
                            "transitions": [1.0, 1.0, 1.0],
                            "values": [
                                {"type": "Vector2", "x": 0, "y": 0},
                                {"type": "Vector2", "x": 10, "y": 0},
                                {"type": "Vector2", "x": 0, "y": 0}
                            ]
                        }
                    }
                ]
            }
        )

        # Create an AnimationNodeAnimation
        build_resource(
            scene_path="scenes/Player.tscn",
            resource_type="AnimationNodeAnimation",
            resource_id="node_idle",
            properties={"animation": "&\"Idle\""}
        )
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    try:
        scene = parse_tscn(scene_path)

        resource_id = _build_sub_resource(
            scene=scene,
            resource_type=resource_type,
            properties=properties,
            resource_id=resource_id,
            array_properties=array_properties,
        )

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

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {type(e).__name__}: {e}"}


# ============ CAPA 2: BUILD NESTED RESOURCE (Jerarquías) ============


@require_session
def build_nested_resource(
    session_id: str,
    scene_path: str,
    root_type: str,
    root_id: str | None = None,
    children: list[dict[str, Any]] | None = None,
    root_properties: dict[str, Any] | None = None,
    array_properties: set[str] | None = None,
) -> dict:
    """
    Create a hierarchy of SubResources with cross-references.

    Creates child resources first, then the root resource that references them.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        root_type: Type of the root resource (e.g., "AnimationNodeStateMachine").
        root_id: Optional ID for the root resource.
        children: List of child resources to create first. Each dict has:
            - type: Resource type (required)
            - id: Resource ID (required)
            - properties: Dict of properties (optional)
        root_properties: Properties for the root resource.
                        Can reference children via SubResource refs.
        array_properties: Set of property names that should remain as
                         flat arrays in the root resource.

    Returns:
        Dict with success status and all created resource IDs.

    Examples:
        # Create a State Machine with states
        build_nested_resource(
            scene_path="scenes/Player.tscn",
            root_type="AnimationNodeStateMachine",
            root_id="state_machine",
            children=[
                {
                    "type": "AnimationNodeAnimation",
                    "id": "node_idle",
                    "properties": {"animation": "&\"Idle\""}
                },
                {
                    "type": "AnimationNodeAnimation",
                    "id": "node_walk",
                    "properties": {"animation": "&\"Walk\""}
                }
            ],
            root_properties={
                "states": {
                    "Idle": {
                        "node": {"type": "SubResource", "ref": "node_idle"},
                        "position": {"type": "Vector2", "x": 293, "y": 87}
                    },
                    "Walk": {
                        "node": {"type": "SubResource", "ref": "node_walk"},
                        "position": {"type": "Vector2", "x": 462, "y": 28}
                    }
                },
                "transitions": ["Start", "Idle", "Idle", "Walk", "Walk", "Finished"]
            }
        )
    """
    scene_path = _ensure_tscn_path(scene_path)

    if not os.path.exists(scene_path):
        return {"success": False, "error": "Scene file not found"}

    try:
        scene = parse_tscn(scene_path)

        created_ids = []

        # Step 1: Create children first
        if children:
            for child in children:
                child_type = child.get("type")
                child_id = child.get("id")
                child_props = child.get("properties", {})

                if not child_type or not child_id:
                    return {
                        "success": False,
                        "error": f"Child resource missing 'type' or 'id': {child}",
                    }

                _build_sub_resource(
                    scene=scene,
                    resource_type=child_type,
                    properties=child_props,
                    resource_id=child_id,
                )
                created_ids.append(child_id)

        # Step 2: Create root resource
        root_id = _build_sub_resource(
            scene=scene,
            resource_type=root_type,
            properties=root_properties or {},
            resource_id=root_id,
            array_properties=array_properties,
        )
        created_ids.append(root_id)

        # Update load_steps
        scene.header.load_steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)

        # Save
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "message": f"Created nested resource hierarchy with root '{root_id}'",
            "root_id": root_id,
            "root_type": root_type,
            "children": created_ids[:-1],  # All except root
            "all_ids": created_ids,
            "scene_path": scene_path,
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {type(e).__name__}: {e}"}


# ============ CAPA 3: HELPERS DE ALTO NIVEL ============


@require_session
def create_animation(
    session_id: str,
    scene_path: str,
    name: str,
    length: float = 1.0,
    loop_mode: int = 0,
    tracks: list[dict[str, Any]] | None = None,
) -> dict:
    """
    Create an Animation resource with a simplified API.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: Animation name (used for resource_id: "anim_{name}").
        length: Animation length in seconds.
        loop_mode: 0=none, 1=linear, 2=clamp.
        tracks: List of track definitions. Each track has:
            - type: "value", "position_3d", "rotation_3d", "scale_3d",
                    "blend_shape", "method", "bezier", "audio", "animation"
            - path: NodePath to the animated property (e.g., "Sprite2D:position")
            - keys: Dict with "times", "transitions", "values" arrays

    Returns:
        Dict with success status and animation info.

    Example:
        create_animation(
            scene_path="scenes/Player.tscn",
            name="idle",
            length=1.0,
            loop_mode=1,
            tracks=[
                {
                    "type": "value",
                    "path": "Sprite2D:position",
                    "keys": {
                        "times": [0.0, 0.5, 1.0],
                        "transitions": [1.0, 1.0, 1.0],
                        "values": [
                            {"type": "Vector2", "x": 0, "y": 0},
                            {"type": "Vector2", "x": 10, "y": 0},
                            {"type": "Vector2", "x": 0, "y": 0}
                        ]
                    }
                }
            ]
        )
    """
    resource_id = f"anim_{name}"

    # Build track properties in TSCN format
    track_props = {}
    if tracks:
        for i, track in enumerate(tracks):
            track_type = track.get("type", "value")
            track_path = track.get("path", "")
            track_keys = track.get("keys", {})

            track_props[f"tracks/{i}/type"] = track_type
            track_props[f"tracks/{i}/path"] = track_path

            # Format keys as a dict with times/transitions/values
            if track_keys:
                times = track_keys.get("times", [])
                transitions = track_keys.get("transitions", [1.0] * len(times))
                values = track_keys.get("values", [])

                track_props[f"tracks/{i}/keys"] = {
                    "times": {"type": "Array", "items": times},
                    "transitions": {"type": "Array", "items": transitions},
                    "values": {"type": "Array", "items": values},
                }

    properties = {
        "length": length,
        "loop_mode": loop_mode,
        "step": 0.0333333,
    }
    properties.update(track_props)

    return build_resource(
        session_id=session_id,
        scene_path=scene_path,
        resource_type="Animation",
        resource_id=resource_id,
        properties=properties,
    )


@require_session
def create_state_machine(
    session_id: str,
    scene_path: str,
    name: str,
    states: list[dict[str, Any]],
    transitions: list[dict[str, Any]] | None = None,
    state_machine_type: int = 0,
) -> dict:
    """
    Create an AnimationNodeStateMachine with a simplified API.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: State machine name (used for resource_id).
        states: List of state definitions. Each state has:
            - name: State name (required)
            - node_type: AnimationNode type (default: "AnimationNodeAnimation")
            - node_properties: Properties for the node (e.g., {"animation": "&\"Idle\""})
            - position: Vector2 position in editor (optional)
        transitions: List of transition definitions. Each has:
            - from: Source state name
            - to: Target state name
            - switch_mode: 0=immediate, 1=sync, 2=at_end (default: 0)
            - xfade_time: Cross-fade time in seconds (default: 0.0)
            - advance_mode: 0=disabled, 1=enabled, 2=auto (default: 1)
            - advance_condition: StringName for condition (optional)
            - advance_expression: Expression string (optional)
            - reset: Reset animation on transition (default: true)
            - priority: Priority for travel() (default: 1)
        state_machine_type: 0=root, 1=nested, 2=grouped

    Returns:
        Dict with success status and state machine info.

    Example:
        create_state_machine(
            scene_path="scenes/Player.tscn",
            name="player_states",
            states=[
                {
                    "name": "Idle",
                    "node_properties": {"animation": "&\"Idle\""},
                    "position": {"type": "Vector2", "x": 293, "y": 87}
                },
                {
                    "name": "Walk",
                    "node_properties": {"animation": "&\"Walk\""},
                    "position": {"type": "Vector2", "x": 462, "y": 28}
                }
            ],
            transitions=[
                {"from": "Idle", "to": "Walk", "switch_mode": 0},
                {"from": "Walk", "to": "Idle", "switch_mode": 0}
            ]
        )
    """
    sm_id = f"sm_{name}"

    # Build children (AnimationNodeAnimation for each state)
    children = []
    state_names = []

    for state in states:
        state_name = state["name"]
        state_names.append(state_name)

        node_type = state.get("node_type", "AnimationNodeAnimation")
        node_id = f"node_{name}_{state_name.lower()}"
        node_props = state.get("node_properties", {})

        children.append({
            "type": node_type,
            "id": node_id,
            "properties": node_props,
        })

    # Build root properties
    root_props = {}

    # States
    states_dict = {}
    for state in states:
        state_name = state["name"]
        node_id = f"node_{name}_{state_name.lower()}"
        position = state.get("position", {"type": "Vector2", "x": 0, "y": 0})

        states_dict[state_name] = {
            "node": {"type": "SubResource", "ref": node_id},
            "position": position,
        }

    root_props["states"] = states_dict

    # Transitions: Real Godot format is a flat triplet array:
    # [from, to, SubResource(transition), from, to, SubResource(transition), ...]
    # If no custom transition properties, SubResource is omitted (just [from, to])
    if transitions:
        trans_array = []
        for t in transitions:
            has_custom = (
                t.get("switch_mode", 0) != 0
                or t.get("xfade_time", 0.0) != 0.0
                or t.get("advance_mode", 1) != 1
                or t.get("advance_condition")
                or t.get("advance_expression")
                or not t.get("reset", True)
                or t.get("priority", 1) != 1
            )

            trans_array.append(t["from"])
            trans_array.append(t["to"])

            if has_custom:
                # Create AnimationNodeStateMachineTransition SubResource
                trans_id = f"trans_{name}_{t['from'].lower()}_{t['to'].lower()}"
                trans_props = {}
                if t.get("switch_mode", 0) != 0:
                    trans_props["switch_mode"] = t["switch_mode"]
                if t.get("xfade_time", 0.0) != 0.0:
                    trans_props["xfade_time"] = t["xfade_time"]
                if t.get("advance_mode", 1) != 1:
                    trans_props["advance_mode"] = t["advance_mode"]
                if t.get("advance_condition"):
                    trans_props["advance_condition"] = t["advance_condition"]
                if t.get("advance_expression"):
                    trans_props["advance_expression"] = t["advance_expression"]
                if not t.get("reset", True):
                    trans_props["reset"] = False
                if t.get("priority", 1) != 1:
                    trans_props["priority"] = t["priority"]

                children.append({
                    "type": "AnimationNodeStateMachineTransition",
                    "id": trans_id,
                    "properties": trans_props,
                })

                trans_array.append({"type": "SubResource", "ref": trans_id})

        root_props["transitions"] = trans_array

    # State machine type
    if state_machine_type != 0:
        root_props["state_machine_type"] = state_machine_type

    return build_nested_resource(
        session_id=session_id,
        scene_path=scene_path,
        root_type="AnimationNodeStateMachine",
        root_id=sm_id,
        children=children,
        root_properties=root_props,
        array_properties={"transitions"},
    )


# ============ CAPA 4: ANIMATION TREE HELPERS ============


@require_session
def create_blend_space_1d(
    session_id: str,
    scene_path: str,
    name: str,
    animations: list[dict[str, Any]],
    min_space: float = 0.0,
    max_space: float = 1.0,
    blend_position: float = 0.0,
) -> dict:
    """
    Create an AnimationNodeBlendSpace1D with a simplified API.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: Blend space name (used for resource_id: "blend1d_{name}").
        animations: List of blend point definitions. Each has:
            - name: Point name (required)
            - position: Float position on the blend axis (required)
            - animation: StringName reference to animation (e.g., '&"Idle"')
            - node: SubResource ref to AnimationNodeAnimation (alternative to animation)
            - position_2d: Vector2 position in editor (optional, default: {x: 0, y: 0})
        min_space: Minimum value of the blend axis.
        max_space: Maximum value of the blend axis.
        blend_position: Current blend position.

    Returns:
        Dict with success status and blend space info.

    Example:
        create_blend_space_1d(
            scene_path="scenes/Player.tscn",
            name="movement",
            min_space=0.0,
            max_space=100.0,
            animations=[
                {"name": "Idle", "position": 0.0, "animation": '&"Idle"'},
                {"name": "Walk", "position": 50.0, "animation": '&"Walk"'},
                {"name": "Run", "position": 100.0, "animation": '&"Run"'},
            ]
        )
    """
    bs_id = f"blend1d_{name}"

    # Build children (AnimationNodeAnimation for each blend point)
    children = []

    for anim in animations:
        anim_name = anim["name"]
        node_id = f"node_{name}_{anim_name.lower()}"

        # If user provided an animation StringName, create AnimationNodeAnimation
        if "animation" in anim:
            children.append({
                "type": "AnimationNodeAnimation",
                "id": node_id,
                "properties": {"animation": anim["animation"]},
            })

    # Build root properties
    root_props = {
        "min_space": min_space,
        "max_space": max_space,
        "blend_position": blend_position,
    }

    # Add blend points
    for i, anim in enumerate(animations):
        anim_name = anim["name"]
        node_id = f"node_{name}_{anim_name.lower()}"
        position = anim["position"]

        # Editor position (for visual graph)
        editor_pos = anim.get("position_2d", {"type": "Vector2", "x": i * 150, "y": 0})

        root_props[f"blend_point_{i}/node"] = {"type": "SubResource", "ref": node_id}
        root_props[f"blend_point_{i}/pos"] = {"type": "Vector2", "x": position, "y": 0}
        root_props[f"blend_point_{i}/position"] = editor_pos

    return build_nested_resource(
        session_id=session_id,
        scene_path=scene_path,
        root_type="AnimationNodeBlendSpace1D",
        root_id=bs_id,
        children=children,
        root_properties=root_props,
    )


@require_session
def create_blend_space_2d(
    session_id: str,
    scene_path: str,
    name: str,
    animations: list[dict[str, Any]],
    min_space: dict[str, float] | None = None,
    max_space: dict[str, float] | None = None,
    blend_position: dict[str, float] | None = None,
) -> dict:
    """
    Create an AnimationNodeBlendSpace2D with a simplified API.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: Blend space name (used for resource_id: "blend2d_{name}").
        animations: List of blend point definitions. Each has:
            - name: Point name (required)
            - position: Vector2 position (required) - {"x": float, "y": float}
            - animation: StringName reference to animation (e.g., '&"Idle"')
            - node: SubResource ref to AnimationNodeAnimation (alternative to animation)
        min_space: Minimum corner of blend space (default: {"x": -1, "y": -1}).
        max_space: Maximum corner of blend space (default: {"x": 1, "y": 1}).
        blend_position: Current blend position (default: {"x": 0, "y": 0}).

    Returns:
        Dict with success status and blend space info.

    Example:
        create_blend_space_2d(
            scene_path="scenes/Player.tscn",
            name="direction",
            animations=[
                {"name": "Idle", "position": {"x": 0, "y": 0}, "animation": '&"Idle"'},
                {"name": "Up", "position": {"x": 0, "y": -1}, "animation": '&"Up"'},
                {"name": "Down", "position": {"x": 0, "y": 1}, "animation": '&"Down"'},
                {"name": "Left", "position": {"x": -1, "y": 0}, "animation": '&"Left"'},
                {"name": "Right", "position": {"x": 1, "y": 0}, "animation": '&"Right"'},
            ]
        )
    """
    bs_id = f"blend2d_{name}"

    if min_space is None:
        min_space = {"x": -1.0, "y": -1.0}
    if max_space is None:
        max_space = {"x": 1.0, "y": 1.0}
    if blend_position is None:
        blend_position = {"x": 0.0, "y": 0.0}

    # Build children (AnimationNodeAnimation for each blend point)
    children = []

    for anim in animations:
        anim_name = anim["name"]
        node_id = f"node_{name}_{anim_name.lower()}"

        if "animation" in anim:
            children.append({
                "type": "AnimationNodeAnimation",
                "id": node_id,
                "properties": {"animation": anim["animation"]},
            })

    # Build root properties
    root_props = {
        "min_space": {"type": "Vector2", "x": min_space["x"], "y": min_space["y"]},
        "max_space": {"type": "Vector2", "x": max_space["x"], "y": max_space["y"]},
        "blend_position": {
            "type": "Vector2",
            "x": blend_position["x"],
            "y": blend_position["y"],
        },
    }

    # Add blend points
    for i, anim in enumerate(animations):
        anim_name = anim["name"]
        node_id = f"node_{name}_{anim_name.lower()}"
        pos = anim["position"]

        root_props[f"blend_point_{i}/node"] = {"type": "SubResource", "ref": node_id}
        root_props[f"blend_point_{i}/pos"] = {
            "type": "Vector2",
            "x": pos["x"],
            "y": pos["y"],
        }

    return build_nested_resource(
        session_id=session_id,
        scene_path=scene_path,
        root_type="AnimationNodeBlendSpace2D",
        root_id=bs_id,
        children=children,
        root_properties=root_props,
    )


@require_session
def create_blend_tree(
    session_id: str,
    scene_path: str,
    name: str,
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]] | None = None,
) -> dict:
    """
    Create an AnimationNodeBlendTree with a simplified API.

    The BlendTree is the root node of an AnimationTree's animation graph.
    It contains a network of AnimationNodes connected together.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: Blend tree name (used for resource_id: "blendtree_{name}").
        nodes: List of node definitions. Each has:
            - name: Node name (required, "output" is the default output node)
            - type: AnimationNode type (default: "AnimationNodeAnimation")
            - properties: Properties for the node (optional)
            - position: Vector2 position in editor (optional)
        connections: List of connection definitions. Each has:
            - from: Source node name (required)
            - to: Target node name (required)
            - input_index: Input port index on target (default: 0)

    Returns:
        Dict with success status and blend tree info.

    Example:
        create_blend_tree(
            scene_path="scenes/Player.tscn",
            name="player_tree",
            nodes=[
                {
                    "name": "output",
                    "type": "AnimationNodeOutput",
                    "position": {"type": "Vector2", "x": 0, "y": 0}
                },
                {
                    "name": "blend",
                    "type": "AnimationNodeBlendSpace1D",
                    "properties": {"min_space": 0.0, "max_space": 1.0},
                    "position": {"type": "Vector2", "x": -200, "y": 0}
                },
            ],
            connections=[
                {"from": "blend", "to": "output"}
            ]
        )
    """
    bt_id = f"blendtree_{name}"

    # Build children (all nodes except "output" which is implicit)
    children = []
    nodes_dict = {}

    for node_def in nodes:
        node_name = node_def["name"]
        node_type = node_def.get("type", "AnimationNodeAnimation")
        node_props = node_def.get("properties", {})
        node_id = f"node_{name}_{node_name.lower()}"
        position = node_def.get("position", {"type": "Vector2", "x": 0, "y": 0})

        # Merge position into properties
        node_props["position"] = position

        if node_name != "output":
            children.append({
                "type": node_type,
                "id": node_id,
                "properties": node_props,
            })

        nodes_dict[node_name] = node_id

    # Build root properties
    root_props = {}

    # Add nodes to root (output is always first)
    output_id = nodes_dict.get("output", f"node_{name}_output")
    root_props["nodes/output"] = {"type": "SubResource", "ref": output_id}
    root_props["nodes/output/position"] = {"type": "Vector2", "x": 0, "y": 0}

    for node_def in nodes:
        node_name = node_def["name"]
        node_id = f"node_{name}_{node_name.lower()}"
        position = node_def.get("position", {"type": "Vector2", "x": 0, "y": 0})

        if node_name != "output":
            root_props[f"nodes/{node_name}"] = {"type": "SubResource", "ref": node_id}
            root_props[f"nodes/{node_name}/position"] = position

    # Add connections
    if connections:
        for i, conn in enumerate(connections):
            from_name = conn["from"]
            to_name = conn["to"]
            input_idx = conn.get("input_index", 0)

            from_id = nodes_dict.get(from_name, f"node_{name}_{from_name.lower()}")
            to_id = nodes_dict.get(to_name, f"node_{name}_{to_name.lower()}")

            root_props[f"connections/{i}/from_node"] = from_name
            root_props[f"connections/{i}/to_node"] = to_name
            root_props[f"connections/{i}/to_input"] = input_idx

    return build_nested_resource(
        session_id=session_id,
        scene_path=scene_path,
        root_type="AnimationNodeBlendTree",
        root_id=bt_id,
        children=children,
        root_properties=root_props,
    )


# ============ CAPA 5: SPRITEFRAMES Y TILESET ============


@require_session
def create_sprite_frames(
    session_id: str,
    scene_path: str,
    name: str,
    animations: list[dict[str, Any]],
) -> dict:
    """
    Create a SpriteFrames resource with a simplified API.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: SpriteFrames name (used for resource_id: "sprites_{name}").
        animations: List of animation definitions. Each has:
            - name: Animation name (required, default: "default")
            - frames: List of frame definitions (required). Each frame has:
                - texture: Path to texture (e.g., "res://sprites/frame1.png")
                - atlas: Optional atlas source ID (for sprite sheets)
                - region: Optional Rect2 region (for sprite sheets)
            - loop: Whether the animation loops (default: True)
            - speed: Frames per second (default: 5.0)

    Returns:
        Dict with success status and SpriteFrames info.

    Example:
        create_sprite_frames(
            scene_path="scenes/Player.tscn",
            name="player",
            animations=[
                {
                    "name": "idle",
                    "frames": [
                        {"texture": "res://sprites/player_idle_1.png"},
                        {"texture": "res://sprites/player_idle_2.png"},
                        {"texture": "res://sprites/player_idle_3.png"},
                    ],
                    "loop": True,
                    "speed": 8.0
                },
                {
                    "name": "run",
                    "frames": [
                        {"texture": "res://sprites/player_run_1.png"},
                        {"texture": "res://sprites/player_run_2.png"},
                    ],
                    "loop": True,
                    "speed": 12.0
                }
            ]
        )
    """
    sf_id = f"sprites_{name}"

    # Build animations array
    anim_list = []

    for anim in animations:
        anim_name = anim.get("name", "default")
        loop = anim.get("loop", True)
        speed = anim.get("speed", 5.0)
        frames = anim.get("frames", [])

        # Build frame references
        frame_refs = []
        for frame in frames:
            texture_path = frame.get("texture", "")
            if texture_path:
                # Use ExtResource reference
                frame_refs.append({"type": "ExtResource", "path": texture_path})

        anim_entry = {
            "name": anim_name,
            "loop": loop,
            "speed": speed,
            "frames": {"type": "Array", "items": frame_refs},
        }
        anim_list.append(anim_entry)

    return build_resource(
        session_id=session_id,
        scene_path=scene_path,
        resource_type="SpriteFrames",
        resource_id=sf_id,
        properties={"animations": {"type": "Array", "items": anim_list}},
        array_properties={"animations"},
    )


@require_session
def create_tile_set(
    session_id: str,
    scene_path: str,
    name: str,
    tile_size: dict[str, int],
    sources: list[dict[str, Any]] | None = None,
    physics_layer_0: dict[str, Any] | None = None,
) -> dict:
    """
    Create a TileSet resource with a simplified API.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        name: TileSet name (used for resource_id: "tileset_{name}").
        tile_size: Size of tiles in pixels. {"x": int, "y": int}.
        sources: List of tile source definitions. Each has:
            - id: Source ID (required)
            - type: "atlas" or "single_tile" (default: "atlas")
            - texture: Path to texture (required)
            - tiles_per_row: Number of tiles per row (for atlas, default: 1)
            - tiles_per_column: Number of tiles per column (for atlas, default: 1)
            - tile_size: Override tile size for this source (optional)
            - regions: List of tile regions (optional). Each has:
                - id: Tile ID within the source
                - region: Rect2 region {"x", "y", "width", "height"}
                - collision: Optional collision polygons
        physics_layer_0: Physics layer 0 configuration (optional). Has:
            - name: Layer name (default: "")
            - physics_material: Physics material properties
            - collision_polygons: Default collision shape

    Returns:
        Dict with success status and TileSet info.

    Example:
        create_tile_set(
            scene_path="scenes/Level.tscn",
            name="ground",
            tile_size={"x": 16, "y": 16},
            sources=[
                {
                    "id": 0,
                    "type": "atlas",
                    "texture": "res://tiles/ground_tiles.png",
                    "tiles_per_row": 4,
                    "tiles_per_column": 4,
                }
            ]
        )
    """
    ts_id = f"tileset_{name}"

    # Build root properties
    root_props = {
        "tile_size": {"type": "Vector2i", "x": tile_size["x"], "y": tile_size["y"]},
    }

    # Physics layer 0
    if physics_layer_0:
        if "name" in physics_layer_0:
            root_props["physics_layer_0/name"] = physics_layer_0["name"]

    # Sources
    if sources:
        for source in sources:
            source_id = source.get("id", 0)
            source_type = source.get("type", "atlas")
            texture_path = source.get("texture", "")

            if source_type == "atlas":
                tiles_x = source.get("tiles_per_row", 1)
                tiles_y = source.get("tiles_per_column", 1)

                root_props[f"sources/{source_id}/type"] = 0  # Atlas
                root_props[f"sources/{source_id}/texture"] = texture_path
                root_props[f"sources/{source_id}/tiles_count"] = {
                    "type": "Vector2i",
                    "x": tiles_x,
                    "y": tiles_y,
                }

                # Override tile size for source
                if "tile_size" in source:
                    src_size = source["tile_size"]
                    root_props[f"sources/{source_id}/tile_size"] = {
                        "type": "Vector2i",
                        "x": src_size["x"],
                        "y": src_size["y"],
                    }

                # Tile regions
                if "regions" in source:
                    for region in source["regions"]:
                        tile_id = region.get("id", 0)
                        if "region" in region:
                            r = region["region"]
                            root_props[
                                f"sources/{source_id}/tiles/{tile_id}/region"
                            ] = {
                                "type": "Rect2i",
                                "x": r["x"],
                                "y": r["y"],
                                "width": r["width"],
                                "height": r["height"],
                            }

                        # Collision polygons
                        if "collision" in region:
                            for ci, poly in enumerate(region["collision"]):
                                points = poly.get("points", [])
                                points_array = {
                                    "type": "Array",
                                    "items": [
                                        {"type": "Vector2", "x": p["x"], "y": p["y"]}
                                        for p in points
                                    ],
                                }
                                root_props[
                                    f"sources/{source_id}/tiles/{tile_id}/"
                                    f"collision_layer_0/polygons/{ci}"
                                ] = points_array

            elif source_type == "single_tile":
                root_props[f"sources/{source_id}/type"] = 1  # Single tile
                root_props[f"sources/{source_id}/texture"] = texture_path

    return build_resource(
        session_id=session_id,
        scene_path=scene_path,
        resource_type="TileSet",
        resource_id=ts_id,
        properties=root_props,
    )


# ============ REGISTRATION ============


def register_resource_builder_tools(mcp) -> None:
    """
    Register all resource builder tools.

    Args:
        mcp: FastMCP instance to register tools on.
    """
    logger.info("Registrando resource builder tools...")

    mcp.add_tool(build_resource)
    mcp.add_tool(build_nested_resource)
    mcp.add_tool(create_animation)
    mcp.add_tool(create_state_machine)
    mcp.add_tool(create_blend_space_1d)
    mcp.add_tool(create_blend_space_2d)
    mcp.add_tool(create_blend_tree)
    mcp.add_tool(create_sprite_frames)
    mcp.add_tool(create_tile_set)

    logger.info("[OK] 9 resource builder tools registradas")
