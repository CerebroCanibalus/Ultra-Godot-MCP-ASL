"""
TSCN Parser - Native Python parser for Godot 4.x .tscn files

Parses .tscn files directly without Godot headless.
Supports all TSCN sections: [gd_scene], [ext_resource], [sub_resource], [node]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class SectionType(Enum):
    GD_SCENE = "gd_scene"
    EXT_RESOURCE = "ext_resource"
    SUB_RESOURCE = "sub_resource"
    NODE = "node"
    CONNECT = "connection"


@dataclass
class GdSceneHeader:
    """Header section [gd_scene]"""

    load_steps: int = 0
    format: int = 3
    uid: str = ""
    scene_unique_name: str = ""

    def to_dict(self) -> dict:
        result = {
            "load_steps": self.load_steps,
            "format": self.format,
        }
        if self.uid:
            result["uid"] = self.uid
        if self.scene_unique_name:
            result["scene_unique_name"] = self.scene_unique_name
        return result

    def to_tscn(self) -> str:
        parts = [f"load_steps={self.load_steps}", f"format={self.format}"]
        if self.uid:
            parts.append(f'uid="{self.uid}"')
        if self.scene_unique_name:
            parts.append(f'scene_unique_name="{self.scene_unique_name}"')
        return f"[gd_scene {' '.join(parts)}]"


@dataclass
class ExtResource:
    """External resource reference [ext_resource]"""

    type: str = ""
    path: str = ""
    id: str = ""
    uid: str = ""

    def to_dict(self) -> dict:
        result = {"type": self.type, "path": self.path, "id": self.id}
        if self.uid:
            result["uid"] = self.uid
        return result

    def to_tscn(self) -> str:
        parts = [f'type="{self.type}"', f'path="{self.path}"', f'id="{self.id}"']
        if self.uid:
            parts.append(f'uid="{self.uid}"')
        return f"[ext_resource {' '.join(parts)}]"


@dataclass
class SubResource:
    """Sub-resource [sub_resource]"""

    type: str = ""
    id: str = ""
    uid: str = ""
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "id": self.id,
            "uid": self.uid,
            "properties": self.properties,
        }

    def to_tscn(self) -> str:
        parts = [f'type="{self.type}"', f'id="{self.id}"']
        if self.uid:
            parts.append(f'uid="{self.uid}"')
        lines = [f"[sub_resource {' '.join(parts)}]"]
        for key, value in self.properties.items():
            formatted_value = _format_gdscript_value(value)
            lines.append(f"{key} = {formatted_value}")
        lines.append("")
        return "\n".join(lines)


@dataclass
class NodeProperty:
    """A single property of a node"""

    key: str
    value: Any


@dataclass
class SceneNode:
    """Scene node [node]"""

    name: str = ""
    type: str = ""
    parent: str = "."
    unique_name_in_owner: bool = False
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "type": self.type,
            "parent": self.parent,
            "unique_name_in_owner": self.unique_name_in_owner,
            "properties": self.properties,
        }
        return result

    def to_tscn(self, is_root: bool = False) -> str:
        lines = []

        # Node header
        header_parts = []
        if self.name:
            header_parts.append(f'name="{self.name}"')
        if self.type:
            header_parts.append(f'type="{self.type}"')
        # Root node MUST NOT have a parent attribute (Godot rejects it)
        if self.parent and not is_root:
            header_parts.append(f'parent="{self.parent}"')
        if self.unique_name_in_owner:
            header_parts.append("unique_name_in_owner=true")

        if header_parts:
            lines.append(f"[node {' '.join(header_parts)}]")

        # Properties
        for key, value in self.properties.items():
            formatted_value = _format_gdscript_value(value)
            lines.append(f"{key} = {formatted_value}")

        return "\n".join(lines)


@dataclass
class Connection:
    """Signal connection [connection]"""

    from_node: str = ""
    signal: str = ""
    to_node: str = ""
    method: str = ""
    flags: int = 0
    binds: list = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "from_node": self.from_node,
            "signal": self.signal,
            "to_node": self.to_node,
            "method": self.method,
            "flags": self.flags,
        }
        if self.binds:
            result["binds"] = self.binds
        return result

    def to_tscn(self) -> str:
        parts = [
            f'from="{self.from_node}"',
            f'signal="{self.signal}"',
            f'to="{self.to_node}"',
            f'method="{self.method}"',
            f"flags={self.flags}",
        ]
        return f"[connection {' '.join(parts)}]"


@dataclass
class Scene:
    """Complete parsed TSCN scene"""

    header: GdSceneHeader = field(default_factory=GdSceneHeader)
    ext_resources: list[ExtResource] = field(default_factory=list)
    sub_resources: list[SubResource] = field(default_factory=list)
    nodes: list[SceneNode] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "ext_resources": [r.to_dict() for r in self.ext_resources],
            "sub_resources": [r.to_dict() for r in self.sub_resources],
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections],
        }

    def to_tscn(self) -> str:
        lines = []

        # Header
        lines.append(self.header.to_tscn())
        lines.append("")

        # External resources
        for resource in self.ext_resources:
            lines.append(resource.to_tscn())

        # Sub resources
        for sub_resource in self.sub_resources:
            lines.append(sub_resource.to_tscn())

        # Nodes
        for i, node in enumerate(self.nodes):
            is_root = i == 0
            lines.append(node.to_tscn(is_root=is_root))
            lines.append("")

        # Connections
        for conn in self.connections:
            lines.append(conn.to_tscn())

        # Remove trailing empty lines but keep structure
        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)


# ============ PARSING FUNCTIONS ============


def _parse_header_line(line: str) -> dict:
    """Parse [gd_scene] header line"""
    result = {}

    # Remove brackets
    content = line.strip().strip("[]")
    parts = content.split()

    # First part is section type, skip it
    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            value = value.strip('"')
            result[key] = int(value) if value.isdigit() else value

    return result


def _parse_ext_resource_line(line: str) -> dict:
    """Parse [ext_resource] line"""
    result = {}

    content = line.strip().strip("[]")
    parts = content.split()

    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            value = value.strip('"')
            result[key] = value

    return result


def _parse_sub_resource_header(line: str) -> dict:
    """Parse [sub_resource] header"""
    return _parse_ext_resource_line(line)


def _parse_node_header(line: str) -> dict:
    """Parse [node] header line"""
    result = {"parent": "."}

    content = line.strip().strip("[]")
    parts = content.split()

    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            value = value.strip('"')

            if value == "true":
                result[key] = True
            elif value == "false":
                result[key] = False
            else:
                result[key] = value

    return result


def _parse_connection_line(line: str) -> dict:
    """Parse [connection] line"""
    result = {"flags": 0, "binds": []}

    content = line.strip().strip("[]")
    parts = content.split()

    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            value = value.strip('"')

            if key == "flags":
                result[key] = int(value)
            elif key == "binds":
                result[key] = _parse_gdscript_value(value)
            else:
                result[key] = value

    return result


def _parse_gdscript_value(value_str: str) -> Any:
    """Parse GDScript literal values"""
    value_str = value_str.strip()

    # Handle ExtResource("id") references
    if value_str.startswith('ExtResource("') and value_str.endswith('")'):
        ref = value_str[13:-2]  # Remove ExtResource(" and ")
        return {"type": "ExtResource", "ref": ref}

    # Handle SubResource("id") references
    if value_str.startswith('SubResource("') and value_str.endswith('")'):
        ref = value_str[13:-2]  # Remove SubResource(" and ")
        return {"type": "SubResource", "ref": ref}

    # Handle NodePath("path") references
    if value_str.startswith('NodePath("') and value_str.endswith('")'):
        ref = value_str[10:-2]  # Remove NodePath(" and ")
        return {"type": "NodePath", "ref": ref}

    # Handle Vector2(x, y)
    if value_str.startswith("Vector2(") and value_str.endswith(")"):
        inner = value_str[8:-1]
        parts = inner.split(", ")
        return {"type": "Vector2", "x": float(parts[0]), "y": float(parts[1])}

    # Handle Vector3(x, y, z)
    if value_str.startswith("Vector3(") and value_str.endswith(")"):
        inner = value_str[8:-1]
        parts = inner.split(", ")
        return {
            "type": "Vector3",
            "x": float(parts[0]),
            "y": float(parts[1]),
            "z": float(parts[2]),
        }

    # Handle Vector4(x, y, z, w)
    if value_str.startswith("Vector4(") and value_str.endswith(")"):
        inner = value_str[7:-1]
        parts = inner.split(", ")
        return {
            "type": "Vector4",
            "x": float(parts[0]),
            "y": float(parts[1]),
            "z": float(parts[2]),
            "w": float(parts[3]),
        }

    # Handle Transform2D(angle, origin, x, y) or Transform2D(Vector2, Vector2, Vector2)
    if value_str.startswith("Transform2D(") and value_str.endswith(")"):
        inner = value_str[13:-1]  # Remove "Transform2D(" and ")"
        # Try to parse as (angle, origin, x, y) format
        parts = inner.split(", ")
        if len(parts) == 4:
            try:
                return {
                    "type": "Transform2D",
                    "angle": float(parts[0]),
                    "origin": {
                        "type": "Vector2",
                        "x": float(parts[1].split(",")[0]),
                        "y": float(parts[1].split(",")[1].split(")")[0]),
                    },
                    "x": {
                        "type": "Vector2",
                        "x": float(parts[2].split(",")[0]),
                        "y": float(parts[2].split(",")[1]),
                    },
                    "y": {
                        "type": "Vector2",
                        "x": float(parts[3].split(",")[0]),
                        "y": float(parts[3]),
                    },
                }
            except (ValueError, IndexError):
                pass
        # Try Vector2 format
        if "Vector2" in inner:
            return {"type": "Transform2D", "raw": inner}
        return {"type": "Transform2D", "raw": inner}

    # Handle Color(r, g, b, a)
    if value_str.startswith("Color(") and value_str.endswith(")"):
        inner = value_str[7:-1]
        parts = inner.split(", ")
        result = {"type": "Color"}
        for i, part in enumerate(parts):
            if part.endswith("a") and i == 3:
                result["a"] = float(part)
            else:
                try:
                    if i == 0:
                        result["r"] = float(part)
                    elif i == 1:
                        result["g"] = float(part)
                    elif i == 2:
                        result["b"] = float(part)
                except ValueError:
                    result[f"part{i}"] = part
        return result

    # Handle Rect2(x, y, width, height)
    if value_str.startswith("Rect2(") and value_str.endswith(")"):
        inner = value_str[6:-1]
        parts = inner.split(", ")
        return {
            "type": "Rect2",
            "x": float(parts[0]),
            "y": float(parts[1]),
            "width": float(parts[2]),
            "height": float(parts[3]),
        }

    # Handle Rect2i (same as Rect2)
    if value_str.startswith("Rect2i(") and value_str.endswith(")"):
        inner = value_str[7:-1]
        parts = inner.split(", ")
        return {
            "type": "Rect2i",
            "x": int(float(parts[0])),
            "y": int(float(parts[1])),
            "width": int(float(parts[2])),
            "height": int(float(parts[3])),
        }

    # Handle Array [...]
    if value_str.startswith("[") and value_str.endswith("]"):
        inner = value_str[1:-1]
        if inner.strip():
            items = _parse_array_items(inner)
            return {"type": "Array", "items": items}
        return {"type": "Array", "items": []}

    # Handle {...} dictionary
    if value_str.startswith("{") and value_str.endswith("}"):
        inner = value_str[1:-1]
        if inner.strip():
            items = _parse_dict_items(inner)
            return {"type": "Dictionary", "items": items}
        return {"type": "Dictionary", "items": {}}

    # Handle boolean
    if value_str == "true":
        return True
    if value_str == "false":
        return False

    # Handle integer
    if value_str.isdigit() or (value_str.startswith("-") and value_str[1:].isdigit()):
        return int(value_str)

    # Handle float
    try:
        return float(value_str)
    except ValueError:
        pass

    # Handle string (remove quotes if present)
    return value_str.strip('"')


def _parse_array_items(content: str) -> list:
    """Parse array items"""
    items = []
    current = ""
    depth = 0

    for char in content:
        if char in "([{":
            depth += 1
            current += char
        elif char in ")]}":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            if current.strip():
                items.append(_parse_gdscript_value(current.strip()))
            current = ""
        else:
            current += char

    if current.strip():
        items.append(_parse_gdscript_value(current.strip()))

    return items


def _parse_dict_items(content: str) -> dict:
    """Parse dictionary items"""
    result = {}
    current_key = ""
    current_value = ""
    in_key = True
    depth = 0

    for char in content:
        if char in "([{":
            depth += 1
            if in_key:
                current_key += char
            else:
                current_value += char
        elif char in ")]}":
            depth -= 1
            if in_key:
                current_key += char
            else:
                current_value += char
        elif char == ":" and depth == 0 and in_key:
            in_key = False
        elif char == "," and depth == 0 and not in_key:
            result[_parse_gdscript_value(current_key.strip())] = _parse_gdscript_value(
                current_value.strip()
            )
            current_key = ""
            current_value = ""
            in_key = True
        else:
            if in_key:
                current_key += char
            else:
                current_value += char

    if current_key.strip():
        result[_parse_gdscript_value(current_key.strip())] = _parse_gdscript_value(
            current_value.strip()
        )

    return result


def _format_gdscript_value(value: Any) -> str:
    """Format a Python value back to GDScript literal"""
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return str(value)

    if isinstance(value, str):
        # Check if string is already an ExtResource/SubResource/NodePath reference
        # Don't wrap in quotes if it's already a GDScript literal reference
        stripped = value.strip()
        if stripped.startswith('ExtResource("') and stripped.endswith('")'):
            return stripped
        if stripped.startswith('SubResource("') and stripped.endswith('")'):
            return stripped
        if stripped.startswith('NodePath("') and stripped.endswith('")'):
            return stripped
        # Also check for malformed references (with extra quotes)
        if (
            'ExtResource("' in stripped
            or 'SubResource("' in stripped
            or 'NodePath("' in stripped
        ):
            # Extract just the reference part
            import re

            match = re.search(
                r'(ExtResource|SubResource|NodePath)\("([^"]+)"\)', stripped
            )
            if match:
                ref_type = match.group(1)
                ref_id = match.group(2)
                return f'{ref_type}("{ref_id}")'
        return f'"{value}"'

    if isinstance(value, dict):
        if value.get("type") == "ExtResource":
            ref_id = str(value.get("ref", ""))
            # Clean any surrounding quotes from the ref ID
            ref_id = ref_id.strip().strip("\"'")
            return f'ExtResource("{ref_id}")'
        if value.get("type") == "SubResource":
            ref_id = str(value.get("ref", ""))
            # Clean any surrounding quotes from the ref ID
            ref_id = ref_id.strip().strip("\"'")
            return f'SubResource("{ref_id}")'
        if value.get("type") == "NodePath":
            ref_id = str(value.get("ref", ""))
            # Clean any surrounding quotes from the ref ID
            ref_id = ref_id.strip().strip("\"'")
            return f'NodePath("{ref_id}")'
        if value.get("type") == "Vector2":
            return f"Vector2({value.get('x', 0)}, {value.get('y', 0)})"
        if value.get("type") == "Vector3":
            return f"Vector3({value.get('x', 0)}, {value.get('y', 0)}, {value.get('z', 0)})"
        if value.get("type") == "Vector4":
            return f"Vector4({value.get('x', 0)}, {value.get('y', 0)}, {value.get('z', 0)}, {value.get('w', 0)})"
        if value.get("type") == "Color":
            parts = [
                str(value.get("r", 0)),
                str(value.get("g", 0)),
                str(value.get("b", 0)),
            ]
            if "a" in value:
                parts.append(str(value.get("a", 1)))
            return f"Color({', '.join(parts)})"
        if value.get("type") == "Rect2":
            return f"Rect2({value.get('x', 0)}, {value.get('y', 0)}, {value.get('width', 0)}, {value.get('height', 0)})"
        if value.get("type") == "Array":
            items = [_format_gdscript_value(i) for i in value.get("items", [])]
            return f"[{', '.join(items)}]"
        if value.get("type") == "Dictionary":
            items = {
                k: _format_gdscript_value(v) for k, v in value.get("items", {}).items()
            }
            pairs = [f'"{k}": {v}' for k, v in items.items()]
            return f"{{{', '.join(pairs)}}}"
        # Generic dict
        return str(value)

    if isinstance(value, list):
        items = [_format_gdscript_value(i) for i in value]
        return f"[{', '.join(items)}]"

    return str(value)


def _detect_section_type(line: str) -> Optional[SectionType]:
    """Detect which section type a line represents"""
    line = line.strip()

    if line.startswith("[") and line.endswith("]"):
        content = line[1:-1].split()[0]

        if content == "gd_scene":
            return SectionType.GD_SCENE
        elif content == "ext_resource":
            return SectionType.EXT_RESOURCE
        elif content == "sub_resource":
            return SectionType.SUB_RESOURCE
        elif content == "node":
            return SectionType.NODE
        elif content == "connection":
            return SectionType.CONNECT

    return None


def _is_property_line(line: str) -> bool:
    """Check if line is a property assignment"""
    return " = " in line and not line.strip().startswith("[")


# ============ MAIN PARSING FUNCTIONS ============


def parse_tscn_string(content: str) -> Scene:
    """Parse TSCN content from string"""
    lines = content.split("\n")

    scene = Scene()

    current_section: Optional[SectionType] = None
    current_sub_resource: Optional[SubResource] = None
    current_node: Optional[SceneNode] = None
    current_conn: Optional[Connection] = None
    ext_id_counter = 1

    for line in lines:
        line = line.strip()

        if not line or line.startswith(";"):
            continue

        # Check for section header
        section = _detect_section_type(line)

        if section == SectionType.GD_SCENE:
            current_section = section
            data = _parse_header_line(line)
            scene.header = GdSceneHeader(
                load_steps=data.get("load_steps", 0),
                format=data.get("format", 3),
                uid=data.get("uid", ""),
                scene_unique_name=data.get("scene_unique_name", ""),
            )

        elif section == SectionType.EXT_RESOURCE:
            # Save previous ext_resource before creating new one
            current_section = section
            data = _parse_ext_resource_line(line)
            scene.ext_resources.append(
                ExtResource(
                    type=data.get("type", ""),
                    path=data.get("path", ""),
                    id=data.get("id", ""),
                    uid=data.get("uid", ""),
                )
            )

        elif section == SectionType.SUB_RESOURCE:
            # Flush pending sub_resource before creating new one
            if current_sub_resource:
                scene.sub_resources.append(current_sub_resource)
            current_section = section
            data = _parse_sub_resource_header(line)
            current_sub_resource = SubResource(
                type=data.get("type", ""),
                id=data.get("id", ""),
                uid=data.get("uid", ""),
            )

        elif section == SectionType.NODE:
            # Flush pending sub_resource before switching to node section
            if current_sub_resource:
                scene.sub_resources.append(current_sub_resource)
                current_sub_resource = None
            # Save previous node before creating new one
            if current_node:
                scene.nodes.append(current_node)
            current_section = section
            data = _parse_node_header(line)
            current_node = SceneNode(
                name=data.get("name", ""),
                type=data.get("type", ""),
                parent=data.get("parent", "."),
                unique_name_in_owner=data.get("unique_name_in_owner", False),
            )

        elif section == SectionType.CONNECT:
            current_section = section
            data = _parse_connection_line(line)
            current_conn = Connection(
                from_node=data.get("from", ""),
                signal=data.get("signal", ""),
                to_node=data.get("to", ""),
                method=data.get("method", ""),
                flags=data.get("flags", 0),
                binds=data.get("binds", []),
            )
            if current_conn:
                scene.connections.append(current_conn)
            current_conn = None

        # Property line (not a section header)
        elif _is_property_line(line):
            key, value = line.split(" = ", 1)
            key = key.strip()
            value = value.strip()
            parsed_value = _parse_gdscript_value(value)

            if current_section == SectionType.SUB_RESOURCE and current_sub_resource:
                current_sub_resource.properties[key] = parsed_value

            elif current_section == SectionType.NODE and current_node:
                current_node.properties[key] = parsed_value

        # Empty line - section ended
        elif line == "":
            if current_sub_resource:
                scene.sub_resources.append(current_sub_resource)
                current_sub_resource = None

            if current_node:
                scene.nodes.append(current_node)
                current_node = None

    # Add any remaining objects
    if current_sub_resource:
        scene.sub_resources.append(current_sub_resource)

    if current_node:
        scene.nodes.append(current_node)

    return scene


def parse_tscn(file_path: str) -> Scene:
    """Parse TSCN file from path"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return parse_tscn_string(content)


def main():
    """Test parser with example TSCN content"""
    example = """[gd_scene load_steps=3 format=3 uid="uid://abc123"]

[ext_resource type="Script" path="res://player.gd" id="1_abc"]
[ext_resource type="PackedScene" uid="uid://def456" path="res://sprite.tscn" id="2_def"]

[sub_resource type="RectangleShape2D" id="1_shape"]
size = Vector2(32, 32)

[node name="Player" type="CharacterBody2D"]
position = Vector2(100, 200)
rotation = 0.5
scale = Vector2(1.5, 1.5)
script = ExtResource("1_abc")

[node name="Sprite2D" type="Sprite2D" parent="."]
position = Vector2(0, -20)
texture = ExtResource("2_def")

[connection signal="body_entered" from="Player" to="." method="_on_body_entered" flags=0]
"""

    print("=" * 60)
    print("Parsing example TSCN...")
    print("=" * 60)

    scene = parse_tscn_string(example)

    print(f"\nHeader: {scene.header}")
    print(f"  load_steps: {scene.header.load_steps}")
    print(f"  format: {scene.header.format}")
    print(f"  uid: {scene.header.uid}")

    print(f"\nExternal Resources: {len(scene.ext_resources)}")
    for res in scene.ext_resources:
        print(f"  - type={res.type}, path={res.path}, id={res.id}")

    print(f"\nSub Resources: {len(scene.sub_resources)}")
    for sub in scene.sub_resources:
        print(f"  - type={sub.type}, id={sub.id}, props={sub.properties}")

    print(f"\nNodes: {len(scene.nodes)}")
    for node in scene.nodes:
        print(f"  - name={node.name}, type={node.type}, parent={node.parent}")
        for k, v in node.properties.items():
            print(f"      {k} = {v}")

    print(f"\nConnections: {len(scene.connections)}")
    for conn in scene.connections:
        print(f"  - {conn.from_node}.{conn.signal} -> {conn.to_node}.{conn.method}")

    print("\n" + "=" * 60)
    print("Converting back to TSCN...")
    print("=" * 60)

    output = scene.to_tscn()
    print(output)

    print("\n" + "=" * 60)
    print("Converting to dict...")
    print("=" * 60)

    result_dict = scene.to_dict()
    import json

    print(json.dumps(result_dict, indent=2))


if __name__ == "__main__":
    main()
