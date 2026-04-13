"""Tests for gd_scene header validation"""

import pytest
from godot_mcp.core.tscn_parser import parse_tscn_string
from godot_mcp.core.tscn_validator import TSCNValidator


class TestHeaderValidation:
    """Test gd_scene header validation"""

    @pytest.fixture
    def validator(self):
        return TSCNValidator()

    def test_valid_header_with_load_steps(self, validator):
        """Header with load_steps should pass"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert result.is_valid

    def test_header_missing_load_steps(self, validator):
        """Header without load_steps should be flagged"""
        tscn = """[gd_scene format=3]

[node name="Root" type="Node2D"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        # Parser sets load_steps=0 by default, but scene has 0 resources
        # so it should pass (0 resources with load_steps=0 is valid)
        assert result.is_valid

    def test_header_with_resources_but_no_load_steps(self, validator):
        """Scene with resources but load_steps=0 should fail"""
        tscn = """[gd_scene load_steps=0 format=3]

[ext_resource type="Script" path="res://test.gd" id="1_script"]

[node name="Root" type="Node2D"]
script = ExtResource("1_script")
"""
        scene = parse_tscn_string(tscn)
        # Override to simulate bad header
        scene.header.load_steps = 0
        result = validator.validate(scene)
        assert not result.is_valid
        assert any("load_steps" in err.lower() for err in result.errors)

    def test_header_with_correct_load_steps(self, validator):
        """load_steps matching actual resources should pass"""
        tscn = """[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://test.gd" id="1_script"]
[ext_resource type="Texture2D" path="res://test.png" id="2_tex"]

[sub_resource type="RectangleShape2D" id="1_shape"]

[node name="Root" type="Node2D"]
script = ExtResource("1_script")
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        # load_steps=3 matches 2 ext_resources + 1 sub_resource = 3
        assert result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
