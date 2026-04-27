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
    EDITABLE = "editable"


@dataclass
class GdSceneHeader:
    """Header section [gd_scene]
    
    Supports inherited scenes with the 'inherits' attribute (Godot 4.x).
    """

    load_steps: int = 0
    format: int = 3
    uid: str = ""
    scene_unique_name: str = ""
    inherits: str = ""  # Path to base scene for inherited scenes

    def to_dict(self) -> dict:
        result = {
            "load_steps": self.load_steps,
            "format": self.format,
        }
        if self.uid:
            result["uid"] = self.uid
        if self.scene_unique_name:
            result["scene_unique_name"] = self.scene_unique_name
        if self.inherits:
            result["inherits"] = self.inherits
        return result

    def to_tscn(self) -> str:
        parts = [f"load_steps={self.load_steps}", f"format={self.format}"]
        if self.uid:
            parts.append(f'uid="{self.uid}"')
        if self.scene_unique_name:
            parts.append(f'scene_unique_name="{self.scene_unique_name}"')
        if self.inherits:
            parts.append(f'inherits="{self.inherits}"')
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
    """Scene node [node]

    Supports all Godot 4.6 node header fields:
    - name, type, parent, unique_name_in_owner, instance
    - unique_id: Stable scene-local ID for robust inheritance (Godot 4.6+)
    - index: Order of appearance in tree (for inherited nodes precedence)
    - owner: Node owner path
    - groups: List of node groups
    - instance_placeholder: Instance placeholder path
    """

    name: str = ""
    type: str = ""
    parent: str = "."
    unique_name_in_owner: bool = False
    instance: str = ""  # ExtResource ID for scene instantiation
    instance_placeholder: str = ""  # Instance placeholder path
    unique_id: int = 0  # Godot 4.6+ stable scene-local ID
    index: int = -1  # Order in tree (-1 = not set)
    owner: str = ""  # Node owner path
    groups: list = field(default_factory=list)  # Node groups
    properties: dict = field(default_factory=dict)
    # Raw unknown fields preserved for forward compatibility
    _unknown_fields: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "type": self.type,
            "parent": self.parent,
            "unique_name_in_owner": self.unique_name_in_owner,
            "instance": self.instance,
            "instance_placeholder": self.instance_placeholder,
            "unique_id": self.unique_id,
            "index": self.index,
            "owner": self.owner,
            "groups": self.groups,
            "properties": self.properties,
        }
        return result

    def to_tscn(self, is_root: bool = False, scene: Optional["Scene"] = None) -> str:
        lines = []

        # Generate unique_id if missing (new nodes)
        if self.unique_id <= 0:
            self.unique_id = _generate_unique_id()

        # Node header
        header_parts = []
        if self.name:
            header_parts.append(f'name="{self.name}"')
        if self.type:
            header_parts.append(f'type="{self.type}"')
        # Root node MUST NOT have a parent attribute (Godot rejects it)
        if self.parent and not is_root:
            header_parts.append(f'parent="{self.parent}"')
            # Calculate parent_id_path from unique_ids (Godot 4.6+ format)
            if scene:
                parent_id_path = _build_parent_id_path(scene, self.parent)
                if parent_id_path:
                    ids_str = ", ".join(str(uid) for uid in parent_id_path)
                    header_parts.append(f"parent_id_path=PackedInt32Array({ids_str})")
        if self.unique_name_in_owner:
            header_parts.append("unique_name_in_owner=true")
        # Instance attribute for scene instantiation (Godot format)
        if self.instance:
            header_parts.append(f'instance=ExtResource("{self.instance}")')
        # Instance placeholder
        if self.instance_placeholder:
            header_parts.append(f'instance_placeholder="{self.instance_placeholder}"')
        # Godot 4.6+ unique_id (stable scene-local ID)
        if self.unique_id > 0:
            header_parts.append(f"unique_id={self.unique_id}")
        # index (order in tree)
        if self.index >= 0:
            header_parts.append(f'index="{self.index}"')
        # owner
        if self.owner:
            header_parts.append(f'owner="{self.owner}"')
        # groups
        if self.groups:
            header_parts.append(f'groups={_format_gdscript_value(self.groups)}')
        # Unknown fields (forward compatibility)
        for key, value in self._unknown_fields.items():
            if isinstance(value, bool):
                header_parts.append(f"{key}={str(value).lower()}")
            elif isinstance(value, (int, float)):
                header_parts.append(f"{key}={value}")
            else:
                header_parts.append(f'{key}="{value}"')

        if header_parts:
            lines.append(f"[node {' '.join(header_parts)}]")

        # Properties (skip scene_file_path if instance is set)
        for key, value in self.properties.items():
            if key == "scene_file_path" and self.instance:
                continue  # Don't write scene_file_path as property when using instance=
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
class EditablePath:
    """Editable child path declaration [editable path=\"...\"]"""

    path: str = ""

    def to_dict(self) -> dict:
        return {"path": self.path}

    def to_tscn(self) -> str:
        return f'[editable path="{self.path}"]'


@dataclass
class Scene:
    """Complete parsed TSCN scene"""

    header: GdSceneHeader = field(default_factory=GdSceneHeader)
    ext_resources: list[ExtResource] = field(default_factory=list)
    sub_resources: list[SubResource] = field(default_factory=list)
    nodes: list[SceneNode] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    editable_paths: list[EditablePath] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "header": self.header.to_dict(),
            "ext_resources": [r.to_dict() for r in self.ext_resources],
            "sub_resources": [r.to_dict() for r in self.sub_resources],
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections],
            "editable_paths": [e.to_dict() for e in self.editable_paths],
        }

    def to_tscn(self) -> str:
        lines = []

        # load_steps is deprecated in Godot 4.6+ but preserved for backwards compatibility.
        # We only auto-calculate if it was not present in the original file (load_steps=0).
        # If the original file had load_steps set, we preserve it to avoid unnecessary diffs.
        if self.header.load_steps == 0:
            actual_resources = len(self.ext_resources) + len(self.sub_resources)
            if actual_resources > 0:
                self.header.load_steps = 1 + actual_resources
            else:
                self.header.load_steps = 1  # At least the scene itself

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
            lines.append(node.to_tscn(is_root=is_root, scene=self))
            lines.append("")

        # Connections
        for conn in self.connections:
            lines.append(conn.to_tscn())

        # Editable paths (Godot 4.x format for editable children)
        for editable in self.editable_paths:
            lines.append(editable.to_tscn())

        # Remove trailing empty lines but keep structure
        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)

    def deduplicate_ext_resources(self, project_path: str | None = None) -> dict:
        """
        Remove duplicate ExtResources and remap all node references.

        Deduplication strategy (in order of priority):
        1. If project_path is provided, resolve each res:// path to a real
           filesystem path. Two resources pointing to the same file on disk
           are considered duplicates (even if their res:// paths differ).
        2. Fuzzy match by filename: if a path doesn't exist on disk, check if
           another ExtResource of the same type has the same filename (stem+ext).
           This catches cases like res://test_player.tscn vs
           res://src/test/.../test_player.tscn.
        3. Normalize res:// paths (collapse .., ., //) and compare by
           (normalized_path, type).

        Keeps the first occurrence (canonical) and remaps all references.

        Args:
            project_path: Absolute path to the Godot project root.
                          Enables filesystem-based deduplication.

        Returns:
            Dict with summary: {"removed": int, "remapped": int, "kept": int,
                                "resolved_paths": int, "fuzzy_matched": int}
        """
        import os
        from pathlib import PurePosixPath

        def _normalize_path(p: str) -> str:
            """Normalize a res:// path: collapse .., ., and standardize separators."""
            if not p.startswith("res://"):
                return p
            prefix = "res://"
            rel = p[len(prefix) :]
            rel = rel.replace("\\", "/")
            while "//" in rel:
                rel = rel.replace("//", "/")
            parts = rel.split("/")
            resolved = []
            for part in parts:
                if part == "..":
                    if resolved:
                        resolved.pop()
                elif part == "." or part == "":
                    continue
                else:
                    resolved.append(part)
            return prefix + "/".join(resolved)

        def _resolve_to_real_path(res_path: str) -> str | None:
            """Resolve a res:// path to a real filesystem path."""
            if not res_path.startswith("res://") or not project_path:
                return None
            rel = res_path[len("res://") :].replace("/", os.sep).replace("\\", os.sep)
            real = os.path.normpath(os.path.join(project_path, rel))
            if os.path.isfile(real):
                return os.path.realpath(real)
            return None

        def _get_filename(p: str) -> str:
            """Extract filename from res:// path."""
            if p.startswith("res://"):
                return PurePosixPath(p).name
            return os.path.basename(p)

        # Phase 0: Pre-compute filename index for fuzzy matching
        # filename_type -> list of (index, id)
        filename_index: dict[str, list[tuple[int, str]]] = {}
        for i, res in enumerate(self.ext_resources):
            fname = _get_filename(res.path)
            key = f"{fname}|{res.type}"
            filename_index.setdefault(key, []).append((i, res.id))

        # Phase 1: Build dedup keys
        key_to_canonical: dict[str, str] = {}  # dedup_key -> canonical_id
        duplicates_to_remove: list[int] = []
        resolved_count = 0
        fuzzy_count = 0

        for i, res in enumerate(self.ext_resources):
            norm_path = _normalize_path(res.path)
            res.path = norm_path  # Normalize in-place

            # Strategy 1: Filesystem resolution
            real_path = _resolve_to_real_path(norm_path)
            if real_path:
                dedup_key = f"real:{real_path}|{res.type}"
                resolved_count += 1
            else:
                # Strategy 2: Fuzzy match by filename
                fname = _get_filename(norm_path)
                fname_key = f"{fname}|{res.type}"
                entries = filename_index.get(fname_key, [])
                if len(entries) > 1:
                    # Multiple resources share this filename+type
                    # Find the canonical (first one that resolved to disk OR first entry)
                    canonical_dedup_key = None
                    for entry_idx, entry_id in entries:
                        if entry_idx == i:
                            continue  # Skip self
                        # Check if this entry resolved to a real path
                        entry_res = self.ext_resources[entry_idx]
                        entry_real = _resolve_to_real_path(entry_res.path)
                        if entry_real:
                            canonical_dedup_key = f"real:{entry_real}|{entry_res.type}"
                            break
                    if canonical_dedup_key is None:
                        # No entry resolved to disk, use first entry as canonical
                        canonical_dedup_key = f"fname:{fname_key}"
                        fuzzy_count += 1
                    dedup_key = canonical_dedup_key
                else:
                    # Strategy 3: Fallback to normalized path + type
                    dedup_key = f"path:{norm_path}|{res.type}"

            if dedup_key in key_to_canonical:
                duplicates_to_remove.append(i)
            else:
                key_to_canonical[dedup_key] = res.id

        # Phase 2: Build remap
        id_remap: dict[str, str] = {}
        for i in duplicates_to_remove:
            old_res = self.ext_resources[i]
            norm_path = _normalize_path(old_res.path)
            real_path = _resolve_to_real_path(norm_path)
            if real_path:
                dedup_key = f"real:{real_path}|{old_res.type}"
            else:
                fname = _get_filename(norm_path)
                fname_key = f"{fname}|{old_res.type}"
                entries = filename_index.get(fname_key, [])
                if len(entries) > 1:
                    # Find the canonical dedup_key (same logic as Phase 1)
                    canonical_dedup_key = None
                    for entry_idx, entry_id in entries:
                        if entry_idx == i:
                            continue
                        entry_res = self.ext_resources[entry_idx]
                        entry_real = _resolve_to_real_path(entry_res.path)
                        if entry_real:
                            canonical_dedup_key = f"real:{entry_real}|{entry_res.type}"
                            break
                    if canonical_dedup_key is None:
                        canonical_dedup_key = f"fname:{fname_key}"
                    dedup_key = canonical_dedup_key
                else:
                    dedup_key = f"path:{norm_path}|{old_res.type}"
            canonical_id = key_to_canonical[dedup_key]
            if old_res.id != canonical_id:
                id_remap[old_res.id] = canonical_id

        # Phase 3: Recursive remap
        def _remap_ext_refs(value: Any) -> int:
            """Recursively find and remap ExtResource references. Returns count."""
            count = 0
            if isinstance(value, dict):
                if value.get("type") == "ExtResource":
                    old_ref = str(value.get("ref", ""))
                    if old_ref in id_remap:
                        value["ref"] = id_remap[old_ref]
                        count += 1
                elif value.get("type") == "Array":
                    for item in value.get("items", []):
                        count += _remap_ext_refs(item)
                elif value.get("type") == "Dictionary":
                    for k, v in value.get("items", {}).items():
                        count += _remap_ext_refs(k)
                        count += _remap_ext_refs(v)
                else:
                    for k, v in value.items():
                        count += _remap_ext_refs(v)
            elif isinstance(value, list):
                for item in value:
                    count += _remap_ext_refs(item)
            elif isinstance(value, str):
                for old_id, new_id in id_remap.items():
                    pattern = f'ExtResource("{old_id}")'
                    if pattern in value:
                        value = value.replace(pattern, f'ExtResource("{new_id}")')
                        count += 1
            return count

        remapped_count = 0
        for node in self.nodes:
            for key in list(node.properties.keys()):
                value = node.properties[key]
                if isinstance(value, str):
                    # Handle raw string references directly (strings are immutable)
                    new_value = value
                    for old_id, new_id in id_remap.items():
                        pattern = f'ExtResource("{old_id}")'
                        if pattern in new_value:
                            new_value = new_value.replace(
                                pattern, f'ExtResource("{new_id}")'
                            )
                            remapped_count += 1
                    node.properties[key] = new_value
                else:
                    remapped_count += _remap_ext_refs(value)

        for sub in self.sub_resources:
            for key in list(sub.properties.keys()):
                value = sub.properties[key]
                if isinstance(value, str):
                    new_value = value
                    for old_id, new_id in id_remap.items():
                        pattern = f'ExtResource("{old_id}")'
                        if pattern in new_value:
                            new_value = new_value.replace(
                                pattern, f'ExtResource("{new_id}")'
                            )
                            remapped_count += 1
                    sub.properties[key] = new_value
                else:
                    remapped_count += _remap_ext_refs(value)

        # Phase 4: Remove duplicates
        for i in reversed(duplicates_to_remove):
            self.ext_resources.pop(i)

        return {
            "removed": len(duplicates_to_remove),
            "remapped": remapped_count,
            "kept": len(self.ext_resources),
            "resolved_paths": resolved_count,
            "fuzzy_matched": fuzzy_count,
        }
        remapped_count = 0
        for node in self.nodes:
            for key, value in node.properties.items():
                remapped_count += _remap_ext_refs(value)

        # Also remap sub-resource properties
        for sub in self.sub_resources:
            for key, value in sub.properties.items():
                remapped_count += _remap_ext_refs(value)

        # Remove duplicates (in reverse order to preserve indices)
        for i in reversed(duplicates_to_remove):
            self.ext_resources.pop(i)

        return {
            "removed": len(duplicates_to_remove),
            "remapped": remapped_count,
            "kept": len(self.ext_resources),
        }


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
    """Parse [ext_resource] line using regex to handle paths with spaces."""
    import re

    result = {}
    content = line.strip().strip("[]")

    # Use regex to match key="value" or key=value patterns
    # This handles values with spaces inside quotes correctly
    pattern = r'(\w+)="([^"]*)"|(\w+)=(\S+)'
    for match in re.finditer(pattern, content):
        if match.group(1) is not None:
            # Quoted value (may contain spaces)
            key = match.group(1)
            value = match.group(2)
        else:
            # Unquoted value
            key = match.group(3)
            value = match.group(4)
        result[key] = value

    return result


def _parse_sub_resource_header(line: str) -> dict:
    """Parse [sub_resource] header"""
    return _parse_ext_resource_line(line)


def _parse_node_header(line: str) -> dict:
    """Parse [node] header line using regex to handle names with spaces.

    Supports all Godot 4.6 node header fields:
    - name, type, parent, unique_name_in_owner, instance
    - unique_id (int), index (int), owner (str)
    - groups (list), instance_placeholder (str)
    - Preserves unknown fields for forward compatibility
    """
    import re

    result = {
        "parent": ".",
        "instance": "",
        "instance_placeholder": "",
        "unique_id": 0,
        "index": -1,
        "owner": "",
        "groups": [],
        "_unknown_fields": {},
    }

    content = line.strip()
    # strip("[]") is too aggressive - it removes ALL [ and ] from ends,
    # which breaks groups=["a", "b"] by eating the closing ].
    # Only strip the outermost [ and ].
    if content.startswith("["):
        content = content[1:]
    if content.endswith("]"):
        content = content[:-1]

    # Handle groups specially (value may contain spaces: groups=["a", "b"])
    groups_match = re.search(r'groups=\[([^\]]*)\]', content)
    if groups_match:
        groups_value = "[" + groups_match.group(1) + "]"
        try:
            parsed = _parse_gdscript_value(groups_value)
            # _parse_gdscript_value returns dict for Array type
            if isinstance(parsed, dict) and parsed.get("type") == "Array":
                result["groups"] = parsed.get("items", [])
            else:
                result["groups"] = parsed
        except Exception:
            result["groups"] = []
        # Remove groups from content to avoid double-parsing by regex
        content = re.sub(r'groups=\[([^\]]*)\]', '', content)

    # Use regex to match key="value" or key=value patterns
    pattern = r'(\w+)="([^"]*)"|(\w+)=(\S+)'
    for match in re.finditer(pattern, content):
        if match.group(1) is not None:
            key = match.group(1)
            value = match.group(2)
        else:
            key = match.group(3)
            value = match.group(4)

        if key == "instance":
            # instance=ExtResource("id")
            if value.startswith('ExtResource("') and value.endswith('")'):
                result[key] = value[13:-2]
            else:
                result[key] = value
        elif key == "unique_id":
            # unique_id is an integer (Godot 4.6+)
            try:
                result[key] = int(value)
            except (ValueError, TypeError):
                result[key] = 0
        elif key == "index":
            # index is an integer (order in tree)
            try:
                result[key] = int(value)
            except (ValueError, TypeError):
                result[key] = -1
        elif key == "groups":
            # groups is a list like ["group1", "group2"]
            try:
                result[key] = _parse_gdscript_value(value)
            except Exception:
                result[key] = []
        elif value == "true":
            result[key] = True
        elif value == "false":
            result[key] = False
        elif key in ("name", "type", "parent", "owner", "instance_placeholder"):
            result[key] = value
        elif key == "unique_name_in_owner":
            result[key] = value == "true"
        else:
            # Unknown field - preserve for forward compatibility
            result["_unknown_fields"][key] = value

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

    # Handle StringName &"name"
    if value_str.startswith('&"') and value_str.endswith('"'):
        return value_str  # Keep as-is (StringName literal)

    # Handle Vector2(x, y)
    if value_str.startswith("Vector2(") and value_str.endswith(")"):
        inner = value_str[8:-1]
        parts = inner.split(", ")
        return {"type": "Vector2", "x": float(parts[0]), "y": float(parts[1])}

    # Handle Vector2i(x, y)
    if value_str.startswith("Vector2i(") and value_str.endswith(")"):
        inner = value_str[9:-1]
        parts = inner.split(", ")
        return {"type": "Vector2i", "x": int(parts[0]), "y": int(parts[1])}

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

    # Handle Vector3i(x, y, z)
    if value_str.startswith("Vector3i(") and value_str.endswith(")"):
        inner = value_str[9:-1]
        parts = inner.split(", ")
        return {
            "type": "Vector3i",
            "x": int(parts[0]),
            "y": int(parts[1]),
            "z": int(parts[2]),
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
        inner = value_str[6:-1]
        parts = inner.split(", ")
        result = {"type": "Color"}
        for i, part in enumerate(parts):
            if i == 3 and len(parts) == 4:
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

    # Handle typed arrays: Array[Type]([...]) or Array([...])
    if value_str.startswith("Array"):
        # Extract the array content after Array[Type]( or Array(
        # Format: Array[PackedScene]([...]) or Array([...])
        import re
        
        # Match Array[Type](content) or Array(content)
        typed_array_match = re.match(r'Array\[(\w+)\]\((.*)\)$', value_str, re.DOTALL)
        plain_array_match = re.match(r'Array\((.*)\)$', value_str, re.DOTALL)
        
        if typed_array_match:
            array_type = typed_array_match.group(1)
            inner = typed_array_match.group(2)
            # The content might be wrapped in [...]
            if inner.startswith("[") and inner.endswith("]"):
                inner = inner[1:-1]
            if inner.strip():
                items = _parse_array_items(inner)
                return {"type": "Array", "array_type": array_type, "items": items}
            return {"type": "Array", "array_type": array_type, "items": []}
        elif plain_array_match:
            inner = plain_array_match.group(1)
            if inner.startswith("[") and inner.endswith("]"):
                inner = inner[1:-1]
            if inner.strip():
                items = _parse_array_items(inner)
                return {"type": "Array", "items": items}
            return {"type": "Array", "items": []}
    
    # Handle plain Array [...]
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
    """Parse array items, handling nested structures and strings with commas."""
    items = []
    current = ""
    depth = 0
    in_string = False
    string_char = None

    for char in content:
        # Handle string boundaries
        if char in '"\'':
            if not in_string:
                in_string = True
                string_char = char
            elif string_char == char:
                # Check if escaped (preceded by odd number of backslashes)
                backslash_count = 0
                for i in range(len(current) - 1, -1, -1):
                    if current[i] == '\\':
                        backslash_count += 1
                    else:
                        break
                if backslash_count % 2 == 0:
                    in_string = False
                    string_char = None
            current += char
            continue

        if in_string:
            current += char
            continue

        # Handle nested structures
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
        # StringName literal: &"name"
        if stripped.startswith('&"') and stripped.endswith('"'):
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
        if value.get("type") == "Vector2i":
            return f"Vector2i({value.get('x', 0)}, {value.get('y', 0)})"
        if value.get("type") == "Vector3":
            return f"Vector3({value.get('x', 0)}, {value.get('y', 0)}, {value.get('z', 0)})"
        if value.get("type") == "Vector3i":
            return f"Vector3i({value.get('x', 0)}, {value.get('y', 0)}, {value.get('z', 0)})"
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
        if value.get("type") == "Rect2i":
            return f"Rect2i({value.get('x', 0)}, {value.get('y', 0)}, {value.get('width', 0)}, {value.get('height', 0)})"
        if value.get("type") == "Array":
            items = [_format_gdscript_value(i) for i in value.get("items", [])]
            array_type = value.get("array_type")
            if array_type:
                # Typed array: Array[Type]([...])
                return f"Array[{array_type}]([{', '.join(items)}])"
            return f"[{', '.join(items)}]"
        if value.get("type") == "Dictionary":
            items = {
                k: _format_gdscript_value(v) for k, v in value.get("items", {}).items()
            }
            pairs = [f'"{k}": {v}' for k, v in items.items()]
            return f"{{{', '.join(pairs)}}}"
        # Generic dict → serialize as GDScript dictionary
        # This handles Animation track keys, state machine states, etc.
        pairs = []
        for k, v in value.items():
            formatted_k = f'"{k}"' if isinstance(k, str) else str(k)
            formatted_v = _format_gdscript_value(v)
            pairs.append(f'{formatted_k}: {formatted_v}')
        return f"{{{', '.join(pairs)}}}"

    if isinstance(value, list):
        items = [_format_gdscript_value(i) for i in value]
        return f"[{', '.join(items)}]"

    return str(value)


def _generate_unique_id() -> int:
    """Generate a stable random unique_id (Godot 4.6+ scene-local ID).
    
    Godot uses random 32-bit integers. We generate them in the range
    1000000000-4294967295 to match the 10-digit format seen in real scenes.
    """
    import random
    return random.randint(1_000_000_000, 4_294_967_295)


def _build_parent_id_path(scene: "Scene", parent_path: str) -> list[int] | None:
    """Build a PackedInt32Array of unique_ids from root to the given parent.
    
    Traverses the node hierarchy using parent references to build the path.
    Supports multi-level paths like "Kitchen/Entities".
    Returns None if the parent is '.' (root) or if any node lacks unique_id.
    """
    if parent_path == "." or not parent_path:
        return None
    
    # Build name -> node lookup
    name_to_node = {n.name: n for n in scene.nodes}
    
    # Build path from parent to root
    path_ids = []
    current = parent_path
    visited = set()
    
    while current and current != ".":
        if current in visited:
            break  # Circular reference protection
        visited.add(current)
        
        # Handle multi-level paths: get the last component
        if "/" in current:
            node_name = current.split("/")[-1]
        else:
            node_name = current
        
        node = name_to_node.get(node_name)
        if not node:
            return None
        if node.unique_id <= 0:
            return None
        path_ids.append(node.unique_id)
        current = node.parent
    
    # Reverse to get root -> leaf order
    path_ids.reverse()
    return path_ids


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
        elif content == "editable":
            return SectionType.EDITABLE

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
                inherits=data.get("inherits", ""),
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
                instance=data.get("instance", ""),
                instance_placeholder=data.get("instance_placeholder", ""),
                unique_id=data.get("unique_id", 0),
                index=data.get("index", -1),
                owner=data.get("owner", ""),
                groups=data.get("groups", []),
                _unknown_fields=data.get("_unknown_fields", {}),
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

        elif section == SectionType.EDITABLE:
            # Parse [editable path="..."] line
            # Extract path="..." value
            import re
            match = re.search(r'path="([^"]*)"', line)
            if match:
                scene.editable_paths.append(EditablePath(path=match.group(1)))
            current_section = None

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
