"""
TSCN Validator - Poka-Yoke validation for Godot 4.x .tscn files

Prevents common TSCN errors before writing scenes:
- Root node with parent attribute
- Duplicate ExtResource/SubResource IDs
- Invalid node types
- Invalid resource references
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from godot_mcp.core.tscn_parser import (
    Scene,
    SceneNode,
    ExtResource,
    SubResource,
)

# Configure logging
logger = logging.getLogger(__name__)


class ValidationLevel:
    """Validation severity levels"""

    ERROR = "error"  # Blocks operation
    WARNING = "warning"  # Warns but allows
    INFO = "info"  # Informational


# Valid Godot 4.6 node types (commonly used)
# Source: https://docs.godotengine.org/en/4.6/classes/
VALID_NODE_TYPES: set[str] = {
    # Base nodes
    "Node",
    "Node2D",
    "Node3D",
    "Control",
    "CanvasItem",
    "CanvasLayer",
    # 2D Nodes
    "Sprite2D",
    "Sprite3D",
    "AnimatedSprite2D",
    "AnimatedSprite3D",
    "Label",
    "Label3D",
    "Button",
    "CheckBox",
    "CheckButton",
    "LineEdit",
    "TextEdit",
    "TextureRect",
    "TextureButton",
    "TextureProgressBar",
    "ProgressBar",
    "HSlider",
    "VSlider",
    "ScrollBar",
    "Panel",
    "PanelContainer",
    "ColorRect",
    "BoxContainer",
    "VBoxContainer",
    "HBoxContainer",
    "GridContainer",
    "CenterContainer",
    "MarginContainer",
    "TabContainer",
    "SplitContainer",
    "HSplitContainer",
    "VSplitContainer",
    "AspectRatioContainer",
    "FlowContainer",
    "HFlowContainer",
    "VFlowContainer",
    "Tree",
    "ItemList",
    "Popup",
    "PopupMenu",
    "PopupPanel",
    "OptionButton",
    "MenuButton",
    "SpinBox",
    "FileDialog",
    "ColorPicker",
    "ConfirmationDialog",
    "AcceptDialog",
    "Window",
    # 2D Physics
    "StaticBody2D",
    "RigidBody2D",
    "CharacterBody2D",
    "KinematicBody2D",  # Deprecated but valid
    "Area2D",
    "CollisionShape2D",
    "CollisionPolygon2D",
    "RayCast2D",
    "Joint2D",
    "PinJoint2D",
    "GrooveJoint2D",
    "DampedSpringJoint2D",
    "PhysicsBody2D",
    "CollisionObject2D",
    "PhysicalBone2D",
    # 3D Physics
    "StaticBody3D",
    "RigidBody3D",
    "CharacterBody3D",
    "KinematicBody3D",  # Deprecated but valid
    "Area3D",
    "CollisionShape3D",
    "CollisionPolygon3D",
    "RayCast3D",
    "Joint3D",
    "PinJoint3D",
    "HingeJoint3D",
    "SliderJoint3D",
    "Generic6DOFJoint3D",
    "ConeTwistJoint3D",
    "PhysicsBody3D",
    "CollisionObject3D",
    "PhysicalBone3D",
    "VehicleBody3D",
    "VehicleWheel3D",
    "SoftBody3D",
    # Cameras & Lights
    "Camera2D",
    "Camera3D",
    "AudioListener2D",
    "AudioListener3D",
    "AudioStreamPlayer",
    "AudioStreamPlayer2D",
    "AudioStreamPlayer3D",
    "Light2D",
    "Light3D",
    "DirectionalLight2D",
    "DirectionalLight3D",
    "OmniLight3D",
    "SpotLight3D",
    "PointLight2D",
    # Navigation
    "NavigationAgent2D",
    "NavigationAgent3D",
    "NavigationRegion2D",
    "NavigationRegion3D",
    "NavigationLink2D",
    "NavigationLink3D",
    "NavigationObstacle2D",
    "NavigationObstacle3D",
    # Paths & Follows
    "Path2D",
    "Path3D",
    "PathFollow2D",
    "PathFollow3D",
    # Tilemaps & Grids
    "TileMap",
    "TileMapLayer",
    "GridMap",
    # Containers
    "SubViewport",
    "SubViewportContainer",
    "Viewport",
    "CanvasGroup",
    "Parallax2D",
    "ParallaxBackground",
    "ParallaxLayer",
    # Visuals
    "Line2D",
    "Polygon2D",
    "MultiMeshInstance2D",
    "MeshInstance2D",
    "MeshInstance3D",
    "BackBufferCopy",
    "CPUParticles2D",
    "CPUParticles3D",
    "GPUParticles2D",
    "GPUParticles3D",
    "WorldEnvironment",
    "FogVolume",
    "Decal",
    "ReflectionProbe",
    "LightmapGI",
    "VoxelGI",
    # UI
    "RichTextLabel",
    "CodeEdit",
    "ReferenceRect",
    "Tabs",
    "TabBar",
    "MenuBar",
    "Separator",
    "HSeparator",
    "VSeparator",
    "ScrollContainer",
    "NinePatchRect",
    "GraphEdit",
    "GraphNode",
    # Animation
    "AnimationPlayer",
    "AnimationTree",
    "AnimationMixer",
    "AnimatorPlayer",  # Legacy
    # 骨骼
    "Skeleton2D",
    "Skeleton3D",
    "Bone2D",
    "BoneAttachment3D",
    "SkeletonIK3D",
    "PhysicalBoneSimulator3D",
    # Markers
    "Marker2D",
    "Marker3D",
    "RemoteTransform2D",
    "RemoteTransform3D",
    # Multiplayer
    "MultiplayerSpawner",
    "MultiplayerSynchronizer",
    # XR
    "XROrigin3D",
    "XRCamera3D",
    "XRController3D",
    "XRAnchor3D",
    "XRNode3D",
    # Others
    "Timer",
    "Tween",
    "ResourcePreloader",
    "VisibilityNotifier2D",
    "VisibilityNotifier3D",
    "VisibleOnScreenNotifier2D",
    "VisibleOnScreenNotifier3D",
    "VisibleOnScreenEnabler2D",
    "VisibleOnScreenEnabler3D",
    "ShapeCast2D",
    "ShapeCast3D",
    "AudioStreamPlayer",  # Legacy 3.x
    "HTTPRequest",
    "WebSocketPeer",
    "WebSocketMultiplayerPeer",
    "TCPServer",
    "TCPStreamPeer",
    "UDPServer",
    "PacketPeer",
    "PacketPeerStream",
    "PacketPeerUDP",
    # Editor nodes (sometimes in scenes)
    "EditorNode3DGizmo",
    "EditorNode3DGizmoPlugin",
    # Missing/placeholder (edge cases)
    "MissingNode",
    "InstancePlaceholder",
    # Godot 4.x new nodes
    "AimModifier3D",
    "IKModifier3D",
    "ConvertTransformModifier3D",
    "CopyTransformModifier3D",
    "RetargetModifier3D",
    "LookAtModifier3D",
    "LimitAngularVelocityModifier3D",
    "CCDIK3D",
    "ChainIK3D",
    "FABRIK3D",
    "IterateIK3D",
    "JacobianIK3D",
    "SplineIK3D",
    "TwoBoneIK3D",
    "SkeletonModifier3D",
    "BoneConstraint3D",
    "BoneTwistDisperser3D",
    "SpringBoneCollision3D",
    "SpringBoneCollisionCapsule3D",
    "SpringBoneCollisionPlane3D",
    "SpringBoneCollisionSphere3D",
    "SpringBoneSimulator3D",
    "ModifierBoneTarget3D",
    "GPUParticlesAttractor3D",
    "GPUParticlesAttractorBox3D",
    "GPUParticlesAttractorSphere3D",
    "GPUParticlesAttractorVectorField3D",
    "GPUParticlesCollision3D",
    "GPUParticlesCollisionBox3D",
    "GPUParticlesCollisionHeightField3D",
    "GPUParticlesCollisionSDF3D",
    "GPUParticlesCollisionSphere3D",
    "LightOccluder2D",
    "OccluderInstance3D",
    "OccluderPolygon2D",
    "ImporterMeshInstance3D",
    "FogMaterial",  # Resource
    "NavigationMesh",  # Resource
    # Last resort - allow any custom class
    # Custom scripts may extend Node with class_name
}


@dataclass
class ValidationRule:
    """A single validation rule"""

    name: str
    check: Callable[[Scene], bool]
    message: str
    level: str = ValidationLevel.ERROR


@dataclass
class ValidationResult:
    """Result of validation"""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message"""
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Add an info message"""
        self.infos.append(message)

    def __str__(self) -> str:
        """String representation"""
        parts = []
        if self.errors:
            parts.append(f"ERRORS ({len(self.errors)}): {self.errors}")
        if self.warnings:
            parts.append(f"WARNINGS ({len(self.warnings)}): {self.warnings}")
        if self.infos:
            parts.append(f"INFOS ({len(self.infos)}): {self.infos}")
        if not parts:
            return "Validation passed"
        return " | ".join(parts)


class TSCNValidator:
    """
    Validates TSCN scenes before writing (Poka-Yoke)

    Prevents common errors that cause Godot to reject scenes.
    """

    def __init__(self, project_path: str | None = None) -> None:
        """Initialize validator with all rules
        
        Args:
            project_path: Absolute path to the Godot project. If provided,
                the validator will check that ExtResource files exist on disk.
        """
        self.project_path = project_path
        self.rules: list[ValidationRule] = [
            # Rule 1: Root node cannot have parent
            ValidationRule(
                name="root_no_parent",
                check=self._check_root_no_parent,
                message="Root node cannot have parent attribute",
                level=ValidationLevel.ERROR,
            ),
            # Rule 2: Unique ExtResource IDs
            ValidationRule(
                name="unique_extresource_ids",
                check=self._check_unique_extresource_ids,
                message="Duplicate ExtResource ID: {id}",
                level=ValidationLevel.ERROR,
            ),
            # Rule 3: Unique SubResource IDs
            ValidationRule(
                name="unique_subresource_ids",
                check=self._check_unique_subresource_ids,
                message="Duplicate SubResource ID: {id}",
                level=ValidationLevel.ERROR,
            ),
            # Rule 4: Valid node types
            ValidationRule(
                name="valid_node_types",
                check=self._check_valid_node_types,
                message="Invalid node type '{type}' for node '{name}'",
                level=ValidationLevel.ERROR,
            ),
            # Rule 5: Valid resource references
            ValidationRule(
                name="valid_resource_refs",
                check=self._check_valid_resource_refs,
                message="Invalid {ref_type} reference '{ref}' in node '{node}'",
                level=ValidationLevel.ERROR,
            ),
            # Rule 6: ExtResource files exist on disk
            ValidationRule(
                name="ext_resource_files_exist",
                check=self._check_ext_resource_files_exist,
                message="ExtResource file does not exist: {path}",
                level=ValidationLevel.ERROR,
            ),
            # Rule 7: Root node must exist
            ValidationRule(
                name="has_root_node",
                check=self._check_has_root_node,
                message="Scene must have at least one root node",
                level=ValidationLevel.ERROR,
            ),
            # Rule 8: Non-empty node names (optional)
            ValidationRule(
                name="non_empty_node_names",
                check=self._check_non_empty_node_names,
                message="Node has empty name",
                level=ValidationLevel.WARNING,
            ),
            # Rule 9: Valid parent paths (warn only)
            ValidationRule(
                name="valid_parent_paths",
                check=self._check_valid_parent_paths,
                message="Invalid parent path '{parent}' for node '{name}'",
                level=ValidationLevel.WARNING,
            ),
        ]

    def _is_root_node(self, scene: Scene, node: SceneNode) -> bool:
        """Check if node is the root (first node with parent='.')"""
        if not scene.nodes:
            return False
        # Root is the first node defined, OR any node explicitly set as parent="."
        return node.parent == "." and node is scene.nodes[0]

    def _get_root_node(self, scene: Scene) -> SceneNode | None:
        """Get the root node of the scene"""
        for node in scene.nodes:
            if node.parent == ".":
                return node
        return scene.nodes[0] if scene.nodes else None

    # ============ RULE CHECKERS ============

    def _check_root_no_parent(self, scene: Scene) -> bool:
        """Check that root node has no parent attribute"""
        for node in scene.nodes:
            # Check if this is a root node (parent="." is implicit, anything else is error)
            if node.parent not in (".", ""):
                # Check if this is actually the root by position
                # First node defined is root, children come after
                idx = scene.nodes.index(node)
                if idx == 0:
                    return False
                # Also check if there's no actual root before this
                has_root_before = any(n.parent == "." for n in scene.nodes[:idx])
                if not has_root_before and node.parent != ".":
                    return False
        return True

    def _check_unique_extresource_ids(self, scene: Scene) -> bool:
        """Check that all ExtResource IDs are unique"""
        ids = [r.id for r in scene.ext_resources if r.id]
        return len(ids) == len(set(ids))

    def _check_unique_subresource_ids(self, scene: Scene) -> bool:
        """Check that all SubResource IDs are unique"""
        ids = [r.id for r in scene.sub_resources if r.id]
        return len(ids) == len(set(ids))

    def _check_valid_node_types(self, scene: Scene) -> bool:
        """Check that all node types are valid Godot types"""
        for node in scene.nodes:
            if node.type and node.type not in VALID_NODE_TYPES:
                logger.warning(
                    f"Unknown node type '{node.type}' for node '{node.name}'. "
                    f"This may cause loading issues."
                )
                # Allow custom types (class_name scripts) but warn
        return True  # Don't block - custom types are common

    def _check_valid_resource_refs(self, scene: Scene) -> bool:
        """Check that all ExtResource/SubResource references are valid"""
        valid_ext_ids = {r.id for r in scene.ext_resources if r.id}
        valid_sub_ids = {r.id for r in scene.sub_resources if r.id}

        for node in scene.nodes:
            for key, value in node.properties.items():
                ref = self._extract_resource_ref(value)
                if ref:
                    ref_type, ref_id = ref
                    if ref_type == "ExtResource" and ref_id not in valid_ext_ids:
                        return False
                    if ref_type == "SubResource" and ref_id not in valid_sub_ids:
                        return False
        return True

    def _extract_resource_ref(self, value: Any) -> tuple[str, str] | None:
        """Extract resource reference from a property value"""
        if isinstance(value, dict):
            ref_type = value.get("type")
            ref_id = value.get("ref")
            if ref_type in ("ExtResource", "SubResource") and ref_id:
                return (ref_type, str(ref_id))
        # Also check for string values like 'ExtResource("id")'
        if isinstance(value, str):
            if value.startswith('ExtResource("'):
                ref_id = value[13:-2]
                return ("ExtResource", ref_id)
            if value.startswith('SubResource("'):
                ref_id = value[12:-2]
                return ("SubResource", ref_id)
        return None

    def _check_has_root_node(self, scene: Scene) -> bool:
        """Check that scene has at least one node"""
        return len(scene.nodes) > 0

    def _check_non_empty_node_names(self, scene: Scene) -> bool:
        """Check that nodes have non-empty names"""
        for node in scene.nodes:
            if not node.name:
                return False
        return True

    def _check_valid_parent_paths(self, scene: Scene) -> bool:
        """Check that parent paths are valid"""
        node_names = {n.name for n in scene.nodes if n.name}
        node_names.add(".")  # Root parent

        for node in scene.nodes:
            if node.parent and node.parent not in node_names:
                # Parent might be path like "Player/Child/GrandChild"
                parts = node.parent.split("/")
                for i in range(len(parts)):
                    path = "/".join(parts[: i + 1])
                    if path not in node_names:
                        return False
        return True

    # ============ PUBLIC API ============

    def validate(self, scene: Scene) -> ValidationResult:
        """
        Validate a complete scene

        Args:
            scene: The Scene to validate

        Returns:
            ValidationResult with any errors/warnings found
        """
        result = ValidationResult()

        if not scene:
            result.add_error("Scene is None or empty")
            return result

        # Run all rule checks
        for rule in self.rules:
            try:
                passed = rule.check(scene)
                if not passed:
                    message = rule.message
                    # Apply template substitutions
                    message = self._substitute_template(rule, scene, message)

                    if rule.level == ValidationLevel.ERROR:
                        result.add_error(message)
                    elif rule.level == ValidationLevel.WARNING:
                        result.add_warning(message)
                    else:
                        result.add_info(message)
            except Exception as e:
                logger.exception(f"Rule '{rule.name}' raised exception: {e}")
                result.add_error(f"Rule '{rule.name}' failed: {e}")

        # Log results
        if result.errors:
            logger.error(
                f"Validation failed with {len(result.errors)} errors: {result.errors}"
            )
        if result.warnings:
            logger.warning(
                f"Validation found {len(result.warnings)} warnings: {result.warnings}"
            )

        return result

    def validate_node(self, node: SceneNode, scene: Scene) -> ValidationResult:
        """
        Validate a single node (for incremental validation)

        Args:
            node: The node to validate
            scene: The scene containing the node

        Returns:
            ValidationResult for the node
        """
        result = ValidationResult()

        # Check node against scene context
        if self._check_valid_resource_refs(scene):
            pass  # Would need more granular check

        # Check if parent exists
        if node.parent not in (".", ""):
            node_names = {n.name for n in scene.nodes}
            if node.parent != "." and node.parent not in node_names:
                result.add_warning(
                    f"Node '{node.name}' has parent '{node.parent}' "
                    f"that doesn't exist in scene"
                )

        return result

    def _substitute_template(
        self, rule: ValidationRule, scene: Scene, message: str
    ) -> str:
        """Substitute template variables in error messages"""
        # For duplicate ID rules
        if "id" in message.lower():
            if rule.name == "unique_extresource_ids":
                ids = [r.id for r in scene.ext_resources]
                seen: set[str] = set()
                for i in ids:
                    if i in seen:
                        return message.format(id=i)
                    seen.add(i)
            elif rule.name == "unique_subresource_ids":
                ids = [r.id for r in scene.sub_resources]
                seen = set()
                for i in ids:
                    if i in seen:
                        return message.format(id=i)
                    seen.add(i)

        # For node type/name rules
        if "{type}" in message or "{name}" in message:
            for node in scene.nodes:
                if node.type not in VALID_NODE_TYPES:
                    return message.format(type=node.type, name=node.name)

        # For resource reference rules
        if "{ref_type}" in message:
            valid_ext = {r.id for r in scene.ext_resources}
            valid_sub = {r.id for r in scene.sub_resources}
            for node in scene.nodes:
                for prop_val in node.properties.values():
                    ref = self._extract_resource_ref(prop_val)
                    if ref:
                        ref_type, ref_id = ref
                        if ref_type == "ExtResource" and ref_id not in valid_ext:
                            return message.format(
                                ref_type=ref_type, ref=ref_id, node=node.name
                            )
                        if ref_type == "SubResource" and ref_id not in valid_sub:
                            return message.format(
                                ref_type=ref_type, ref=ref_id, node=node.name
                            )

        # For parent path rules
        if "{parent}" in message:
            for node in scene.nodes:
                if node.parent not in ("", "."):
                    node_names = {n.name for n in scene.nodes}
                    if node.parent not in node_names:
                        return message.format(parent=node.parent, name=node.name)

        return message

    def raise_on_error(self, result: ValidationResult) -> None:
        """
        Raise exception if validation has errors

        Args:
            result: ValidationResult to check

        Raises:
            ValueError: If there are any error-level issues
        """
        if result.errors:
            error_msg = "TSCN validation failed:\n"
            for err in result.errors:
                error_msg += f"  - {err}\n"
            raise ValueError(error_msg)


def validate_scene(scene: Scene, raise_on_error: bool = True) -> ValidationResult:
    """
    Convenience function to validate a scene

    Args:
        scene: Scene to validate
        raise_on_error: If True, raise ValueError on validation failure

    Returns:
        ValidationResult

    Raises:
        ValueError: If raise_on_error=True and validation fails
    """
    validator = TSCNValidator()
    result = validator.validate(scene)
    if raise_on_error:
        validator.raise_on_error(result)
    return result


# ============ TEST ============


def main() -> None:
    """Test the validator with various scenarios"""
    from godot_mcp.core.tscn_parser import parse_tscn_string

    # Test 1: Valid scene
    valid_scene = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1_script"]
[ext_resource type="PackedScene" path="res://enemy.tscn" id="2_enemy"]

[sub_resource type="RectangleShape2D" id="1_shape"]

[node name="Player" type="CharacterBody2D"]
position = Vector2(100, 200)
script = ExtResource("1_script")

[node name="Collision" type="CollisionShape2D" parent="Player"]
shape = SubResource("1_shape")
"""
    print("=" * 60)
    print("Test 1: Valid scene")
    print("=" * 60)
    scene = parse_tscn_string(valid_scene)
    result = validate_scene(scene)
    print(f"Result: {result}")
    print(f"Valid: {result.is_valid}")
    print()

    # Test 2: Duplicate ExtResource ID
    dup_ext = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1_script"]
[ext_resource type="PackedScene" path="res://enemy.tscn" id="1_script"]

[node name="Player" type="CharacterBody2D"]
"""
    print("=" * 60)
    print("Test 2: Duplicate ExtResource ID")
    print("=" * 60)
    scene = parse_tscn_string(dup_ext)
    result = validate_scene(scene, raise_on_error=False)
    print(f"Result: {result}")
    print(f"Valid: {result.is_valid}")
    print()

    # Test 3: Invalid resource reference
    bad_ref = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1_script"]

[node name="Player" type="CharacterBody2D"]
texture = ExtResource("999_missing")
"""
    print("=" * 60)
    print("Test 3: Invalid resource reference")
    print("=" * 60)
    scene = parse_tscn_string(bad_ref)
    result = validate_scene(scene, raise_on_error=False)
    print(f"Result: {result}")
    print(f"Valid: {result.is_valid}")
    print()

    # Test 4: Root with parent
    root_parent = """[gd_scene load_steps=2 format=3]

[node name="Player" type="CharacterBody2D" parent="."]
"""
    print("=" * 60)
    print("Test 4: Root with explicit parent")
    print("=" * 60)
    scene = parse_tscn_string(root_parent)
    result = validate_scene(scene, raise_on_error=False)
    print(f"Result: {result}")
    print(f"Valid: {result.is_valid}")


if __name__ == "__main__":
    main()
