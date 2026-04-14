"""
Tests para property_tools.py - Herramienta unificada del inspector.
"""

import sys
import os
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from godot_mcp.core.tscn_parser import (
    parse_tscn_string,
    Scene,
    SceneNode,
    SubResource,
    ExtResource,
)
from godot_mcp.tools.property_tools import (
    set_node_properties,
    NODE_PROPERTY_SCHEMAS,
    _process_property_value,
    _validate_properties,
    _get_shape_resource_type,
    SHAPE_2D_NODES,
    SHAPE_3D_NODES,
)
from godot_mcp.tools.session_tools import (
    get_session_manager,
    set_session_manager,
    start_session,
    end_session,
)


# ============ FIXTURES ============


@pytest.fixture(autouse=True)
def reset_session_manager():
    """Reset session manager before each test."""
    from godot_mcp.session_manager import SessionManager

    set_session_manager(SessionManager(auto_save=False))
    yield


@pytest.fixture
def temp_project():
    """Create a temporary Godot project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_file = os.path.join(tmpdir, "project.godot")
        with open(project_file, "w", encoding="utf-8") as f:
            f.write("""[configuration]
config_version=5

[application]
config/name="TestProject"
config/features=PackedStringArray("4.6")
""")
        yield tmpdir


@pytest.fixture
def session_id(temp_project):
    """Create a real session for testing."""
    result = start_session(temp_project)
    assert result["success"] is True
    return result["session_id"]


# ============ TEST SCHEMA LOOKUP ============


class TestSchemaLookup:
    def test_collision_shape_2d_has_shape_schema(self):
        schema = NODE_PROPERTY_SCHEMAS.get("CollisionShape2D")
        assert schema is not None
        assert "shape" in schema
        assert schema["shape"]["type"] == "sub_resource"

    def test_sprite_2d_has_texture_schema(self):
        schema = NODE_PROPERTY_SCHEMAS.get("Sprite2D")
        assert schema is not None
        assert "texture" in schema
        assert schema["texture"]["type"] == "ext_resource"

    def test_label_has_text_schema(self):
        schema = NODE_PROPERTY_SCHEMAS.get("Label")
        assert schema is not None
        assert "text" in schema
        assert schema["text"]["type"] == "string"

    def test_timer_has_wait_time_schema(self):
        schema = NODE_PROPERTY_SCHEMAS.get("Timer")
        assert schema is not None
        assert "wait_time" in schema
        assert schema["wait_time"]["type"] == "float"

    def test_node_base_type_has_empty_schema(self):
        schema = NODE_PROPERTY_SCHEMAS.get("Node")
        assert schema is not None
        assert len(schema) == 0

    def test_unknown_node_type_returns_none(self):
        schema = NODE_PROPERTY_SCHEMAS.get("NonExistentNode")
        assert schema is None


class TestShapeTypeDetection:
    def test_2d_node_uses_shape2d(self):
        assert _get_shape_resource_type("CollisionShape2D") == "Shape2D"
        assert _get_shape_resource_type("Area2D") == "Shape2D"
        assert _get_shape_resource_type("RigidBody2D") == "Shape2D"

    def test_3d_node_uses_shape3d(self):
        assert _get_shape_resource_type("CollisionShape3D") == "Shape3D"
        assert _get_shape_resource_type("Area3D") == "Shape3D"
        assert _get_shape_resource_type("RigidBody3D") == "Shape3D"

    def test_default_is_shape2d(self):
        assert _get_shape_resource_type("UnknownNode") == "Shape2D"


class TestPropertyValidation:
    def test_valid_enum_value(self):
        schema = {"mode": {"type": "int", "enum": {"RIGID": 0, "STATIC": 1}}}
        is_valid, errors = _validate_properties("Test", {"mode": "RIGID"}, schema)
        assert is_valid

    def test_invalid_enum_value(self):
        schema = {"mode": {"type": "int", "enum": {"RIGID": 0, "STATIC": 1}}}
        is_valid, errors = _validate_properties("Test", {"mode": "INVALID"}, schema)
        assert not is_valid
        assert len(errors) == 1

    def test_unknown_property_allowed(self):
        schema = {"known_prop": {"type": "string"}}
        is_valid, errors = _validate_properties("Test", {"unknown_prop": 42}, schema)
        assert is_valid  # Unknown properties are allowed

    def test_no_schema_allows_all(self):
        is_valid, errors = _validate_properties("Test", {"anything": "goes"}, None)
        assert is_valid


# ============ TEST PROPERTY PROCESSING ============


class TestPropertyProcessing:
    def test_simple_string_value(self):
        scene = Scene()
        node = SceneNode(name="Label", type="Label")
        schema = {"text": {"type": "string"}}

        result, messages = _process_property_value(scene, node, "text", "Hello", schema)
        assert result == "Hello"
        assert len(messages) == 0

    def test_simple_number_value(self):
        scene = Scene()
        node = SceneNode(name="Timer", type="Timer")
        schema = {"wait_time": {"type": "float"}}

        result, messages = _process_property_value(
            scene, node, "wait_time", 5.0, schema
        )
        assert result == 5.0

    def test_simple_bool_value(self):
        scene = Scene()
        node = SceneNode(name="Timer", type="Timer")
        schema = {"one_shot": {"type": "bool"}}

        result, messages = _process_property_value(
            scene, node, "one_shot", True, schema
        )
        assert result is True

    def test_file_path_creates_ext_resource(self):
        scene = Scene()
        node = SceneNode(name="Sprite2D", type="Sprite2D")
        # Pass the individual property schema, not the full node schema
        prop_schema = {"type": "ext_resource", "resource_type": "Texture2D"}

        result, messages = _process_property_value(
            scene, node, "texture", "res://sprites/player.png", prop_schema
        )
        assert 'ExtResource("1")' == result
        assert len(scene.ext_resources) == 1
        assert scene.ext_resources[0].type == "Texture2D"
        assert scene.ext_resources[0].path == "res://sprites/player.png"

    def test_file_path_reuses_existing_ext_resource(self):
        scene = Scene()
        scene.ext_resources.append(
            ExtResource(type="Texture2D", path="res://sprites/player.png", id="1")
        )
        node = SceneNode(name="Sprite2D", type="Sprite2D")
        prop_schema = {"type": "ext_resource", "resource_type": "Texture2D"}

        result, messages = _process_property_value(
            scene, node, "texture", "res://sprites/player.png", prop_schema
        )
        assert 'ExtResource("1")' == result
        assert len(scene.ext_resources) == 1  # No new resource created

    def test_sub_resource_reference(self):
        scene = Scene()
        node = SceneNode(name="CollisionShape2D", type="CollisionShape2D")
        prop_schema = {"type": "sub_resource"}

        result, messages = _process_property_value(
            scene,
            node,
            "shape",
            {"type": "SubResource", "ref": "my_shape"},
            prop_schema,
        )
        assert 'SubResource("my_shape")' == result

    def test_shape_definition_creates_sub_resource(self):
        scene = Scene()
        node = SceneNode(name="CollisionShape2D", type="CollisionShape2D")
        prop_schema = {"type": "sub_resource", "resource_type": "Shape2D"}

        result, messages = _process_property_value(
            scene,
            node,
            "shape",
            {"size": {"type": "Vector2", "x": 32, "y": 32}},
            prop_schema,
        )
        assert result.startswith('SubResource("')
        assert len(scene.sub_resources) == 1
        assert scene.sub_resources[0].type == "RectangleShape2D"  # Default Shape2D

    def test_shape_definition_with_explicit_type(self):
        scene = Scene()
        node = SceneNode(name="CollisionShape2D", type="CollisionShape2D")
        prop_schema = {"type": "sub_resource", "resource_type": "Shape2D"}

        result, messages = _process_property_value(
            scene,
            node,
            "shape",
            {"shape_type": "CircleShape2D", "radius": 16.0},
            prop_schema,
        )
        assert result.startswith('SubResource("')
        assert len(scene.sub_resources) == 1
        assert scene.sub_resources[0].type == "CircleShape2D"

    def test_typed_vector_value(self):
        scene = Scene()
        node = SceneNode(name="Sprite2D", type="Sprite2D")

        result, messages = _process_property_value(
            scene, node, "position", {"type": "Vector2", "x": 100, "y": 200}
        )
        assert result == {"type": "Vector2", "x": 100, "y": 200}

    def test_typed_color_value(self):
        scene = Scene()
        node = SceneNode(name="Sprite2D", type="Sprite2D")

        result, messages = _process_property_value(
            scene,
            node,
            "modulate",
            {"type": "Color", "r": 1.0, "g": 0.5, "b": 0.5, "a": 1.0},
        )
        assert result == {"type": "Color", "r": 1.0, "g": 0.5, "b": 0.5, "a": 1.0}


# ============ TEST SET_NODE_PROPERTIES ============


class TestSetNodeProperties:
    def test_set_simple_properties(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Label" type="Label" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Label",
            properties={"text": "Hello World", "visible": True},
        )

        assert result["success"] is True
        assert "text" in result["properties_set"]
        assert "visible" in result["properties_set"]

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        label = next(n for n in scene.nodes if n.name == "Label")
        assert label.properties["text"] == "Hello World"
        assert label.properties["visible"] is True

    def test_set_shape_property(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Collision" type="CollisionShape2D" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Collision",
            properties={"shape": {"size": {"type": "Vector2", "x": 32, "y": 32}}},
        )

        assert result["success"] is True
        assert len(result["messages"]) > 0

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        assert len(scene.sub_resources) == 1
        assert scene.sub_resources[0].type == "RectangleShape2D"

        collision = next(n for n in scene.nodes if n.name == "Collision")
        assert "shape" in collision.properties
        # Shape is stored as a dict reference
        shape_ref = collision.properties["shape"]
        assert isinstance(shape_ref, dict)
        assert shape_ref["type"] == "SubResource"
        assert "ref" in shape_ref

    def test_set_circle_shape(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Collision" type="CollisionShape2D" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Collision",
            properties={"shape": {"shape_type": "CircleShape2D", "radius": 16.0}},
        )

        assert result["success"] is True

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        assert len(scene.sub_resources) == 1
        assert scene.sub_resources[0].type == "CircleShape2D"
        assert scene.sub_resources[0].properties["radius"] == 16.0

    def test_set_texture_from_path(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Sprite" type="Sprite2D" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Sprite",
            properties={"texture": "res://sprites/player.png"},
        )

        assert result["success"] is True

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        assert len(scene.ext_resources) == 1
        assert scene.ext_resources[0].type == "Texture2D"

    def test_set_timer_properties(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Timer" type="Timer" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Timer",
            properties={"wait_time": 2.5, "one_shot": True, "autostart": True},
        )

        assert result["success"] is True

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        timer = next(n for n in scene.nodes if n.name == "Timer")
        assert timer.properties["wait_time"] == 2.5
        assert timer.properties["one_shot"] is True
        assert timer.properties["autostart"] is True

    def test_node_not_found(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="NonExistent",
            properties={"text": "Hello"},
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_scene_file_not_found(self, session_id):
        result = set_node_properties(
            session_id=session_id,
            scene_path="/nonexistent/test.tscn",
            node_path="Root",
            properties={"text": "Hello"},
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_set_multiple_properties_at_once(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Sprite" type="Sprite2D" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Sprite",
            properties={
                "position": {"type": "Vector2", "x": 100, "y": 200},
                "scale": {"type": "Vector2", "x": 2.0, "y": 2.0},
                "flip_h": True,
                "modulate": {"type": "Color", "r": 1.0, "g": 0.5, "b": 0.5, "a": 1.0},
            },
        )

        assert result["success"] is True
        assert len(result["properties_set"]) == 4

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        sprite = next(n for n in scene.nodes if n.name == "Sprite")
        assert sprite.properties["position"]["x"] == 100
        assert sprite.properties["position"]["y"] == 200
        assert sprite.properties["flip_h"] is True

    def test_update_load_steps(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Sprite" type="Sprite2D" parent="Root"]
""")

        set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Sprite",
            properties={"texture": "res://sprites/player.png"},
        )

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        assert scene.header.load_steps == 2

    def test_set_audio_stream(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Audio" type="AudioStreamPlayer" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Audio",
            properties={
                "stream": "res://audio/music.ogg",
                "autoplay": True,
                "volume_db": -10.0,
            },
        )

        assert result["success"] is True

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        assert len(scene.ext_resources) == 1
        assert scene.ext_resources[0].type == "AudioStream"

        audio = next(n for n in scene.nodes if n.name == "Audio")
        assert audio.properties["autoplay"] is True
        assert audio.properties["volume_db"] == -10.0

    def test_set_light_properties(self, session_id, temp_project):
        scene_path = os.path.join(temp_project, "test.tscn")
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write("""[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]

[node name="Light" type="PointLight2D" parent="Root"]
""")

        result = set_node_properties(
            session_id=session_id,
            scene_path=scene_path,
            node_path="Light",
            properties={
                "color": {"type": "Color", "r": 1.0, "g": 0.8, "b": 0.5, "a": 1.0},
                "energy": 2.0,
                "range": 200.0,
                "shadow_enabled": True,
            },
        )

        assert result["success"] is True

        scene = parse_tscn_string(open(scene_path, encoding="utf-8").read())
        light = next(n for n in scene.nodes if n.name == "Light")
        assert light.properties["energy"] == 2.0
        assert light.properties["range"] == 200.0
        assert light.properties["shadow_enabled"] is True
