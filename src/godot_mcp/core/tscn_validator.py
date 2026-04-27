"""
TSCN Validator - Poka-Yoke validation for Godot 4.x .tscn files

Prevents common TSCN errors before writing scenes:
- Root node with parent attribute
- Duplicate ExtResource/SubResource IDs
- Invalid/removed/deprecated node types
- Invalid resource references

Uses NodeAPI for validation against Godot 4.6.1 known types.
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
from godot_mcp.core.api import NodeAPI, get_node_api

# Configure logging
logger = logging.getLogger(__name__)


class ValidationLevel:
    """Validation severity levels"""

    ERROR = "error"  # Blocks operation
    WARNING = "warning"  # Warns but allows
    INFO = "info"  # Informational


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
    Uses NodeAPI for intelligent validation against Godot 4.6.1 types.
    """

    def __init__(self, project_path: str | None = None, node_api: NodeAPI | None = None) -> None:
        """Initialize validator with all rules

        Args:
            project_path: Absolute path to the Godot project. If provided,
                the validator will check that ExtResource files exist on disk.
            node_api: Optional NodeAPI instance. If None, uses singleton.
        """
        self.project_path = project_path
        self._node_api = node_api or get_node_api()
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
            # Rule 4b: Removed/deprecated node types (more specific error)
            ValidationRule(
                name="removed_node_types",
                check=self._check_removed_node_types,
                message="Removed/deprecated node type: {type} - {reason}",
                level=ValidationLevel.ERROR,
            ),
            # Rule 4c: Resource used as node type (common mistake)
            ValidationRule(
                name="resource_not_node",
                check=self._check_resource_as_node,
                message="'{type}' is a resource, not a node type. Did you mean to use a different node?",
                level=ValidationLevel.ERROR,
            ),
            # Rule 5: Valid resource references
            ValidationRule(
                name="valid_resource_refs",
                check=self._check_valid_resource_refs,
                message="Invalid {ref_type} reference '{ref}' in node '{node}'",
                level=ValidationLevel.ERROR,
            ),
            # Rule 6: Valid gd_scene header (load_steps required)
            ValidationRule(
                name="valid_gd_scene_header",
                check=self._check_valid_gd_scene_header,
                message="Invalid [gd_scene] header: {detail}",
                level=ValidationLevel.ERROR,
            ),
            # Rule 7: ExtResource files exist on disk
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
            # Rule 9: Valid parent paths (ERROR - broken chains cause Godot errors)
            ValidationRule(
                name="valid_parent_paths",
                check=self._check_valid_parent_paths,
                message="Invalid parent path '{parent}' for node '{name}' - intermediate node missing or invalid chain",
                level=ValidationLevel.ERROR,
            ),
            # Rule 10: Unique sibling node names (ERROR - Godot rejects duplicate sibling names)
            ValidationRule(
                name="unique_sibling_node_names",
                check=self._check_unique_sibling_node_names,
                message="Duplicate node name '{name}' under parent '{parent}'",
                level=ValidationLevel.ERROR,
            ),
            # Rule 11: Unique node unique_ids (Godot 4.6+)
            ValidationRule(
                name="unique_node_ids",
                check=self._check_unique_node_ids,
                message="Duplicate node unique_id: {id} in nodes '{node1}' and '{node2}'",
                level=ValidationLevel.ERROR,
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
        """Check that all ExtResource IDs are unique (including numeric vs string collisions)"""
        ids = [r.id for r in scene.ext_resources if r.id]
        # Check exact duplicates
        if len(ids) != len(set(ids)):
            return False
        # Check numeric collisions: "7" should not coexist with "7_g21cb"
        numeric_ids = set()
        for rid in ids:
            try:
                numeric_ids.add(int(rid))
            except (ValueError, TypeError):
                pass
        for rid in ids:
            try:
                int(rid)  # Skip pure numeric
                continue
            except (ValueError, TypeError):
                pass
            # Check if this string ID starts with a number that exists as pure numeric
            import re
            match = re.match(r'^(\d+)_.*$', rid)
            if match:
                prefix_num = int(match.group(1))
                if prefix_num in numeric_ids:
                    return False
        return True

    def _check_unique_subresource_ids(self, scene: Scene) -> bool:
        """Check that all SubResource IDs are unique (including numeric vs string collisions)"""
        ids = [r.id for r in scene.sub_resources if r.id]
        # Check exact duplicates
        if len(ids) != len(set(ids)):
            return False
        # Check numeric collisions: "7" should not coexist with "7_g21cb"
        numeric_ids = set()
        for rid in ids:
            try:
                numeric_ids.add(int(rid))
            except (ValueError, TypeError):
                pass
        for rid in ids:
            try:
                int(rid)  # Skip pure numeric
                continue
            except (ValueError, TypeError):
                pass
            # Check if this string ID starts with a number that exists as pure numeric
            import re
            match = re.match(r'^(\d+)_.*$', rid)
            if match:
                prefix_num = int(match.group(1))
                if prefix_num in numeric_ids:
                    return False
        return True

    def _check_unique_node_ids(self, scene: Scene) -> bool:
        """Check that all node unique_ids are unique (Godot 4.6+)"""
        unique_ids = [n.unique_id for n in scene.nodes if n.unique_id > 0]
        return len(unique_ids) == len(set(unique_ids))

    def _check_valid_node_types(self, scene: Scene) -> bool:
        """Check that all node types are valid Godot 4.6 types

        Uses NodeAPI to validate against known types, detect removed types,
        and identify resources that are incorrectly used as nodes.
        """
        for node in scene.nodes:
            if not node.type:
                continue

            # Use NodeAPI for intelligent validation
            validation = self._node_api.validate_type(node.type)

            # Check for removed types (ERROR - blocks)
            is_removed, _ = self._node_api.is_removed_node(node.type)
            if is_removed:
                return False

            # Log issues for unknown/custom types (warning only)
            if not validation["is_valid"]:
                for issue in validation["issues"]:
                    logger.warning(f"Node '{node.name}' has {issue}")

        return True  # Don't block for custom types (class_name scripts are valid)

    def _check_removed_node_types(self, scene: Scene) -> bool:
        """Check for node types that were removed in Godot 4"""
        for node in scene.nodes:
            if node.type:
                is_removed, _ = self._node_api.is_removed_node(node.type)
                if is_removed:
                    return False
        return True

    def _check_resource_as_node(self, scene: Scene) -> bool:
        """Check for resources incorrectly used as node types"""
        for node in scene.nodes:
            if node.type:
                if self._node_api.is_resource_not_node(node.type):
                    return False
        return True

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

    def _check_valid_gd_scene_header(self, scene: Scene) -> bool:
        """Check that gd_scene header has required fields

        Required: format, load_steps
        """
        if scene.header.format <= 0:
            return False
        if scene.header.load_steps < 0:
            return False
        # load_steps should match actual resources (at least 1 if there are resources)
        actual_resources = len(scene.ext_resources) + len(scene.sub_resources)
        if actual_resources > 0 and scene.header.load_steps == 0:
            return False
        return True

    def _check_ext_resource_files_exist(self, scene: Scene) -> bool:
        """Check that all ExtResource files exist on disk

        Args:
            scene: The Scene to validate

        Returns:
            True if all ExtResource files exist, False if any file is missing.
            Returns True if project_path is not provided (skip check).
        """
        if not self.project_path:
            return True  # Skip if no project path provided

        for resource in scene.ext_resources:
            if resource.path.startswith("res://"):
                # Convert res:// to absolute path
                relative_path = resource.path.replace("res://", "")
                full_path = os.path.join(self.project_path, relative_path)

                if not os.path.exists(full_path):
                    logger.warning(f"ExtResource file does not exist: {resource.path} (resolved to {full_path})")
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
                ref_id = value[13:-2]  # SubResource(" = 13 chars
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
        """Check that parent paths are valid and all intermediate nodes exist"""
        node_names = {n.name for n in scene.nodes if n.name}
        node_parents = {n.name: n.parent for n in scene.nodes if n.name}
        node_names.add(".")  # Root parent

        for node in scene.nodes:
            if not node.parent or node.parent == ".":
                continue  # Root node or valid root parent

            # Check if direct parent exists
            if node.parent in node_names:
                continue  # Direct parent found

            # Check hierarchical path like "Player/Child/GrandChild"
            parts = node.parent.split("/")

            # Must have at least one part
            if not parts or parts[0] == "":
                return False

            # Check each part of the path exists as a node
            for i, part in enumerate(parts):
                if part == ".":
                    continue  # Root reference is valid

                if part not in node_names:
                    # This part of the path doesn't exist
                    return False

                # For nested paths, verify the chain is valid
                # e.g., for "Player/Child", "Child" must have parent="Player"
                if i > 0:
                    expected_parent = "/".join(parts[:i])
                    actual_parent = node_parents.get(part, "")
                    if actual_parent != expected_parent and actual_parent != ".":
                        # The chain is broken
                        return False

        return True

    def _check_unique_sibling_node_names(self, scene: Scene) -> bool:
        """Check that no two sibling nodes share the same name."""
        seen: dict[tuple[str, str], SceneNode] = {}  # (parent, name) -> node
        for node in scene.nodes:
            key = (node.parent, node.name)
            if key in seen:
                return False
            seen[key] = node
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
            logger.error(f"Validation failed with {len(result.errors)} errors: {result.errors}")
        if result.warnings:
            logger.warning(f"Validation found {len(result.warnings)} warnings: {result.warnings}")

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
                result.add_warning(f"Node '{node.name}' has parent '{node.parent}' that doesn't exist in scene")

        return result

    def _substitute_template(self, rule: ValidationRule, scene: Scene, message: str) -> str:
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

        # For removed/deprecated node types
        if rule.name == "removed_node_types" and "{type}" in message:
            for node in scene.nodes:
                if node.type:
                    is_removed, detail = self._node_api.is_removed_node(node.type)
                    if is_removed:
                        replacement = self._node_api.get_replacement(node.type) or "N/A"
                        reason = f"use '{replacement}' instead"
                        try:
                            return message.format(type=node.type, name=node.name, reason=reason)
                        except KeyError:
                            return f"'{node.type}' was removed in Godot 4. Use '{replacement}' instead."

        # For resource-not-node errors
        if rule.name == "resource_not_node" and "{type}" in message:
            for node in scene.nodes:
                if node.type and self._node_api.is_resource_not_node(node.type):
                    return message.format(type=node.type, name=node.name)

        # For node type/name rules
        if "{type}" in message or "{name}" in message:
            for node in scene.nodes:
                if node.type:
                    # Check for removed types
                    is_removed, _ = self._node_api.is_removed_node(node.type)
                    if is_removed:
                        try:
                            return message.format(type=node.type, name=node.name, parent=node.parent)
                        except KeyError:
                            try:
                                return message.format(type=node.type, name=node.name)
                            except KeyError:
                                return message

                    # Check for invalid types
                    validation = self._node_api.validate_type(node.type)
                    if not validation["is_valid"]:
                        try:
                            return message.format(type=node.type, name=node.name, parent=node.parent)
                        except KeyError:
                            try:
                                return message.format(type=node.type, name=node.name)
                            except KeyError:
                                return message

                    # Check for invalid types
                    validation = self._node_api.validate_type(node.type)
                    if not validation["is_valid"]:
                        try:
                            return message.format(type=node.type, name=node.name, parent=node.parent)
                        except KeyError:
                            try:
                                return message.format(type=node.type, name=node.name)
                            except KeyError:
                                return message

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
                            return message.format(ref_type=ref_type, ref=ref_id, node=node.name)
                        if ref_type == "SubResource" and ref_id not in valid_sub:
                            return message.format(ref_type=ref_type, ref=ref_id, node=node.name)

        # For parent path rules
        if "{parent}" in message:
            for node in scene.nodes:
                if node.parent not in ("", "."):
                    node_names = {n.name for n in scene.nodes}
                    if node.parent not in node_names:
                        return message.format(parent=node.parent, name=node.name)

        # For gd_scene header rule
        if rule.name == "valid_gd_scene_header" and "{detail}" in message:
            if scene.header.format <= 0:
                return message.format(detail="format must be > 0")
            if scene.header.load_steps < 0:
                return message.format(detail="load_steps must be >= 0")
            actual_resources = len(scene.ext_resources) + len(scene.sub_resources)
            if actual_resources > 0 and scene.header.load_steps == 0:
                return message.format(detail=f"load_steps=0 but {actual_resources} resources defined")
            return message.format(detail="unknown header issue")

        # For ext_resource_files_exist rule
        if rule.name == "ext_resource_files_exist" and "{path}" in message:
            if not self.project_path:
                return message.format(path="(no project_path provided)")
            for resource in scene.ext_resources:
                if resource.path.startswith("res://"):
                    relative_path = resource.path.replace("res://", "")
                    full_path = os.path.join(self.project_path, relative_path)
                    if not os.path.exists(full_path):
                        return message.format(path=resource.path)

        # For unique sibling node names rule
        if rule.name == "unique_sibling_node_names" and "{name}" in message and "{parent}" in message:
            seen: dict[tuple[str, str], str] = {}
            for node in scene.nodes:
                key = (node.parent, node.name)
                if key in seen:
                    return message.format(name=node.name, parent=node.parent)
                seen[key] = node.name

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


def validate_scene(
    scene: Scene,
    project_path: str | None = None,
    raise_on_error: bool = True,
    node_api: NodeAPI | None = None,
) -> ValidationResult:
    """
    Convenience function to validate a scene

    Args:
        scene: Scene to validate
        project_path: Absolute path to the Godot project. If provided,
            the validator will check that ExtResource files exist on disk.
        raise_on_error: If True, raise ValueError on validation failure
        node_api: Optional NodeAPI instance for type validation

    Returns:
        ValidationResult

    Raises:
        ValueError: If raise_on_error=True and validation fails
    """
    validator = TSCNValidator(project_path=project_path, node_api=node_api)
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
