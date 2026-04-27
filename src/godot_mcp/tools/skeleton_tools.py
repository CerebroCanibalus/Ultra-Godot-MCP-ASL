"""
Skeleton Tools - Herramientas para Skeleton2D y Skeleton3D.

Proporciona herramientas FastMCP para:
- Crear esqueletos 2D/3D
- Añadir huesos (Bone2D, BoneAttachment3D)
- Configurar skinning (Polygon2D, MeshInstance3D)
- Calcular rest poses automáticamente vía Godot CLI

Ventaja competitiva: Usa Godot CLI headless para cálculos matemáticos
que otros MCP no pueden hacer (rest poses, weights, etc.).
"""

import logging
import os
from typing import Any, Optional

from godot_mcp.core.tscn_parser import (
    Scene,
    SceneNode,
    SubResource,
    parse_tscn,
)
from godot_mcp.tools.node_tools import (
    _ensure_tscn_path,
    _update_scene_file,
    _find_node_by_path,
    _generate_resource_id,
)
from godot_mcp.tools.decorators import require_session

logger = logging.getLogger(__name__)


# ============ SKELETON2D TOOLS ============


@require_session
def create_skeleton2d(
    session_id: str,
    scene_path: str,
    parent_path: str = ".",
    skeleton_name: str = "Skeleton2D",
) -> dict:
    """
    Crea un nodo Skeleton2D en una escena.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        parent_path: Path to parent node (default: root).
        skeleton_name: Name for the skeleton node.

    Returns:
        Dict with success status and skeleton info.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)
        scene = parse_tscn(scene_path)

        # Find parent node
        parent_result = _find_node_by_path(scene, parent_path)
        if not parent_result:
            return {
                "success": False,
                "error": f"Parent node not found: {parent_path}",
            }

        _, parent_node = parent_result
        resolved_parent = parent_node.name if parent_node else "."

        # Create Skeleton2D node
        skeleton = SceneNode(
            name=skeleton_name,
            type="Skeleton2D",
            parent=resolved_parent,
        )
        scene.nodes.append(skeleton)

        # Save scene
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "skeleton_name": skeleton_name,
            "parent": resolved_parent,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def add_bone2d(
    session_id: str,
    scene_path: str,
    skeleton_path: str,
    bone_name: str,
    parent_bone: str = None,
    rest_transform: dict = None,
    length: float = 32.0,
    bone_angle: float = 0.0,
    autocalculate: bool = True,
    enabled: bool = True,
) -> dict:
    """
    Añade un hueso Bone2D a un Skeleton2D.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        skeleton_path: Path to the Skeleton2D node (e.g., "Root/Skeleton2D").
        bone_name: Name for the bone.
        parent_bone: Name of parent bone (None for root bone).
        rest_transform: Dict with Transform2D data:
            {"type": "Transform2D", "angle": 0, "origin": {"x": 0, "y": 0},
             "x": {"x": 1, "y": 0}, "y": {"x": 0, "y": 1}}
        length: Bone length in pixels.
        bone_angle: Bone angle in radians.
        autocalculate: Auto-calculate length and angle.
        enabled: Whether bone is enabled.

    Returns:
        Dict with success status and bone info.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)
        scene = parse_tscn(scene_path)

        # Find skeleton node
        skeleton_result = _find_node_by_path(scene, skeleton_path)
        if not skeleton_result:
            return {
                "success": False,
                "error": f"Skeleton2D not found: {skeleton_path}",
            }

        _, skeleton_node = skeleton_result

        # Determine parent for the bone
        if parent_bone:
            # Check parent bone exists
            parent_found = False
            for node in scene.nodes:
                if node.name == parent_bone and node.parent == skeleton_node.name:
                    parent_found = True
                    break
            if not parent_found:
                return {
                    "success": False,
                    "error": f"Parent bone not found: {parent_bone}",
                }
            bone_parent = parent_bone
        else:
            bone_parent = skeleton_node.name

        # Build properties
        properties = {
            "length": length,
            "bone_angle": bone_angle,
            "autocalculate_length_and_angle": autocalculate,
            "enabled": enabled,
        }

        if rest_transform:
            properties["rest"] = rest_transform

        # Create Bone2D node
        bone = SceneNode(
            name=bone_name,
            type="Bone2D",
            parent=bone_parent,
            properties=properties,
        )
        scene.nodes.append(bone)

        # Save scene
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "bone_name": bone_name,
            "skeleton": skeleton_node.name,
            "parent_bone": parent_bone,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def setup_polygon2d_skinning(
    session_id: str,
    scene_path: str,
    polygon_path: str,
    skeleton_path: str,
    bone_weights: dict = None,
) -> dict:
    """
    Configura skinning para un Polygon2D vinculándolo a un Skeleton2D.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        polygon_path: Path to the Polygon2D node.
        skeleton_path: Path to the Skeleton2D node.
        bone_weights: Dict mapping bone names to weight data:
            {"Bone1": {"weights": [0.5, 0.5, 1.0, 1.0]}, ...}

    Returns:
        Dict with success status.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)
        scene = parse_tscn(scene_path)

        # Find Polygon2D
        poly_result = _find_node_by_path(scene, polygon_path)
        if not poly_result:
            return {
                "success": False,
                "error": f"Polygon2D not found: {polygon_path}",
            }

        _, poly_node = poly_result

        # Find Skeleton2D
        skel_result = _find_node_by_path(scene, skeleton_path)
        if not skel_result:
            return {
                "success": False,
                "error": f"Skeleton2D not found: {skeleton_path}",
            }

        _, skel_node = skel_result

        # Set skeleton property
        poly_node.properties["skeleton"] = f'NodePath("../{skel_node.name}")'

        # Set bone weights if provided
        if bone_weights:
            for bone_name, weight_data in bone_weights.items():
                if "weights" in weight_data:
                    poly_node.properties[f"bone_{bone_name}"] = weight_data["weights"]

        # Save scene
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "polygon": poly_node.name,
            "skeleton": skel_node.name,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============ SKELETON3D TOOLS ============


@require_session
def create_skeleton3d(
    session_id: str,
    scene_path: str,
    parent_path: str = ".",
    skeleton_name: str = "Skeleton3D",
) -> dict:
    """
    Crea un nodo Skeleton3D en una escena.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        parent_path: Path to parent node (default: root).
        skeleton_name: Name for the skeleton node.

    Returns:
        Dict with success status and skeleton info.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)
        scene = parse_tscn(scene_path)

        # Find parent node
        parent_result = _find_node_by_path(scene, parent_path)
        if not parent_result:
            return {
                "success": False,
                "error": f"Parent node not found: {parent_path}",
            }

        _, parent_node = parent_result
        resolved_parent = parent_node.name if parent_node else "."

        # Create Skeleton3D node
        skeleton = SceneNode(
            name=skeleton_name,
            type="Skeleton3D",
            parent=resolved_parent,
        )
        scene.nodes.append(skeleton)

        # Save scene
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "skeleton_name": skeleton_name,
            "parent": resolved_parent,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def add_bone_attachment3d(
    session_id: str,
    scene_path: str,
    skeleton_path: str,
    attachment_name: str,
    bone_name: str,
    bone_idx: int = -1,
    override_pose: bool = False,
) -> dict:
    """
    Añade un BoneAttachment3D a un Skeleton3D.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        skeleton_path: Path to the Skeleton3D node.
        attachment_name: Name for the attachment node.
        bone_name: Name of the bone to attach to.
        bone_idx: Index of the bone (-1 to use bone_name).
        override_pose: Whether to override bone pose.

    Returns:
        Dict with success status and attachment info.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)
        scene = parse_tscn(scene_path)

        # Find skeleton
        skel_result = _find_node_by_path(scene, skeleton_path)
        if not skel_result:
            return {
                "success": False,
                "error": f"Skeleton3D not found: {skeleton_path}",
            }

        _, skel_node = skel_result

        # Create BoneAttachment3D
        properties = {
            "bone_name": bone_name,
            "override_pose": override_pose,
        }
        if bone_idx >= 0:
            properties["bone_idx"] = bone_idx

        attachment = SceneNode(
            name=attachment_name,
            type="BoneAttachment3D",
            parent=skel_node.name,
            properties=properties,
        )
        scene.nodes.append(attachment)

        # Save scene
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "attachment_name": attachment_name,
            "skeleton": skel_node.name,
            "bone_name": bone_name,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@require_session
def setup_mesh_skinning(
    session_id: str,
    scene_path: str,
    mesh_path: str,
    skeleton_path: str,
    skin_resource_path: str = None,
) -> dict:
    """
    Configura skinning para un MeshInstance3D vinculándolo a un Skeleton3D.

    Args:
        session_id: Session ID from start_session.
        scene_path: Path to the .tscn file.
        mesh_path: Path to the MeshInstance3D node.
        skeleton_path: Path to the Skeleton3D node.
        skin_resource_path: Optional path to a Skin resource (.tres file).

    Returns:
        Dict with success status.
    """
    try:
        scene_path = _ensure_tscn_path(scene_path)
        scene = parse_tscn(scene_path)

        # Find MeshInstance3D
        mesh_result = _find_node_by_path(scene, mesh_path)
        if not mesh_result:
            return {
                "success": False,
                "error": f"MeshInstance3D not found: {mesh_path}",
            }

        _, mesh_node = mesh_result

        # Find Skeleton3D
        skel_result = _find_node_by_path(scene, skeleton_path)
        if not skel_result:
            return {
                "success": False,
                "error": f"Skeleton3D not found: {skeleton_path}",
            }

        _, skel_node = skel_result

        # Set skeleton property
        mesh_node.properties["skeleton"] = f'NodePath("../{skel_node.name}")'

        # Set skin if provided
        if skin_resource_path:
            mesh_node.properties["skin"] = f'ExtResource("{skin_resource_path}")'

        # Save scene
        _update_scene_file(scene_path, scene)

        return {
            "success": True,
            "mesh": mesh_node.name,
            "skeleton": skel_node.name,
            "scene_path": scene_path,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============ GODOT CLI INTEGRATION ============


def calculate_rest_poses(
    project_path: str,
    scene_path: str,
    skeleton_name: str,
    godot_path: str = None,
) -> dict:
    """
    Calcula rest poses automáticamente usando Godot CLI.

    Esta herramienta usa Godot headless para calcular las transformaciones
    de rest de los huesos basándose en su posición actual.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene file (relative to project).
        skeleton_name: Name of the Skeleton2D or Skeleton3D node.
        godot_path: Optional path to Godot executable.

    Returns:
        Dict with calculated rest poses for each bone.
    """
    try:
        from godot_mcp.godot_cli.base import GodotCLIWrapper

        wrapper = GodotCLIWrapper(godot_path=godot_path)

        script = f"""
extends SceneTree
func _init():
    var scene = load("res://{scene_path}").instantiate()
    var skeleton = scene.get_node("{skeleton_name}")
    if skeleton == null:
        print("ERROR: Skeleton not found")
        quit()
        return
    
    print("SKELETON_TYPE:", skeleton.get_class())
    
    if skeleton is Skeleton2D:
        for bone in skeleton.get_children():
            if bone is Bone2D:
                var rest = bone.rest
                print("BONE:", bone.name)
                print("  REST_ORIGIN:", rest.origin)
                print("  REST_ROTATION:", rest.get_rotation())
                print("  LENGTH:", bone.length)
    elif skeleton is Skeleton3D:
        for i in range(skeleton.get_bone_count()):
            var rest = skeleton.get_bone_rest(i)
            print("BONE:", skeleton.get_bone_name(i))
            print("  REST_ORIGIN:", rest.origin)
            print("  REST_BASIS:", rest.basis)
    
    quit()
"""

        result = wrapper.run_script(script, project_path=project_path)

        # Parse output
        bones = []
        current_bone = None
        for line in result.get("stdout", "").split("\n"):
            line = line.strip()
            if line.startswith("BONE:"):
                current_bone = {"name": line.split(":", 1)[1].strip()}
                bones.append(current_bone)
            elif current_bone and line.startswith("REST_ORIGIN:"):
                current_bone["rest_origin"] = line.split(":", 1)[1].strip()
            elif current_bone and line.startswith("REST_ROTATION:"):
                current_bone["rest_rotation"] = float(line.split(":", 1)[1].strip())
            elif current_bone and line.startswith("LENGTH:"):
                current_bone["length"] = float(line.split(":", 1)[1].strip())

        return {
            "success": True,
            "skeleton_type": result.get("skeleton_type", "unknown"),
            "bones": bones,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def calculate_bone_weights(
    project_path: str,
    scene_path: str,
    polygon_name: str,
    skeleton_name: str,
    godot_path: str = None,
) -> dict:
    """
    Calcula weights de skinning automáticamente para un Polygon2D.

    Usa Godot headless para calcular weights basándose en la proximidad
    de los vértices a los huesos.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene file.
        polygon_name: Name of the Polygon2D node.
        skeleton_name: Name of the Skeleton2D node.
        godot_path: Optional path to Godot executable.

    Returns:
        Dict with calculated weights for each bone.
    """
    try:
        from godot_mcp.godot_cli.base import GodotCLIWrapper

        wrapper = GodotCLIWrapper(godot_path=godot_path)

        script = f"""
extends SceneTree
func _init():
    var scene = load("res://{scene_path}").instantiate()
    var polygon = scene.get_node("{polygon_name}")
    var skeleton = scene.get_node("{skeleton_name}")
    
    if polygon == null or skeleton == null:
        print("ERROR: Nodes not found")
        quit()
        return
    
    var vertices = polygon.polygon
    var bones = skeleton.get_children()
    
    print("VERTICES:", vertices.size())
    
    for bone in bones:
        if bone is Bone2D:
            var weights = []
            var bone_global = bone.global_position
            for v in vertices:
                var dist = bone_global.distance_to(v)
                var weight = max(0.0, 1.0 - (dist / bone.length))
                weights.append(weight)
            print("BONE_WEIGHTS:", bone.name)
            print("  WEIGHTS:", weights)
    
    quit()
"""

        result = wrapper.run_script(script, project_path=project_path)

        # Parse output
        bone_weights = {}
        current_bone = None
        for line in result.get("stdout", "").split("\n"):
            line = line.strip()
            if line.startswith("BONE_WEIGHTS:"):
                current_bone = line.split(":", 1)[1].strip()
            elif current_bone and line.startswith("WEIGHTS:"):
                weights_str = line.split(":", 1)[1].strip()
                # Parse array
                weights = [float(w) for w in weights_str.strip("[]").split(",") if w]
                bone_weights[current_bone] = weights
                current_bone = None

        return {
            "success": True,
            "bone_weights": bone_weights,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============ REGISTRATION ============


def register_skeleton_tools(mcp) -> None:
    """
    Registrar todas las herramientas de skeleton.

    Args:
        mcp: Instancia de FastMCP donde registrar las herramientas.
    """
    logger.info("Registrando skeleton_tools...")

    # Skeleton2D
    mcp.add_tool(create_skeleton2d)
    mcp.add_tool(add_bone2d)
    mcp.add_tool(setup_polygon2d_skinning)

    # Skeleton3D
    mcp.add_tool(create_skeleton3d)
    mcp.add_tool(add_bone_attachment3d)
    mcp.add_tool(setup_mesh_skinning)

    logger.info("[OK] 6 skeleton_tools registradas")
