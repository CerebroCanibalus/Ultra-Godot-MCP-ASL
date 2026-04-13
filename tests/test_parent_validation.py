"""Tests for hierarchical parent path validation"""

import pytest
from godot_mcp.core.tscn_parser import parse_tscn_string
from godot_mcp.core.tscn_validator import TSCNValidator


class TestParentPathValidation:
    """Test hierarchical parent path validation"""

    @pytest.fixture
    def validator(self):
        return TSCNValidator()

    def test_valid_direct_parent(self, validator):
        """Direct parent reference should pass"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Player" type="CharacterBody2D"]

[node name="Sprite" type="Sprite2D" parent="Player"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert result.is_valid

    def test_valid_hierarchical_parent(self, validator):
        """Hierarchical path like Player/Arm/Hand should pass if chain exists"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Player" type="CharacterBody2D"]

[node name="Arm" type="Node2D" parent="Player"]

[node name="Hand" type="Node2D" parent="Player/Arm"]

[node name="Finger" type="Node2D" parent="Player/Arm/Hand"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert result.is_valid

    def test_invalid_hierarchical_missing_intermediate(self, validator):
        """Path with missing intermediate node should fail"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Player" type="CharacterBody2D"]

[node name="Finger" type="Node2D" parent="Player/Arm/Hand"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert not result.is_valid
        assert any("Invalid parent path" in err for err in result.errors)

    def test_invalid_parent_nonexistent_node(self, validator):
        """Parent referencing non-existent node should fail"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Player" type="CharacterBody2D"]

[node name="Enemy" type="CharacterBody2D" parent="NonExistent"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert not result.is_valid

    def test_root_parent_is_valid(self, validator):
        """parent=\".\" should be valid for root"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Player" type="CharacterBody2D" parent="."]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        # Root with parent="." is valid
        assert result.is_valid

    def test_empty_parent_is_valid(self, validator):
        """Empty parent should be treated as root"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Player" type="CharacterBody2D"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert result.is_valid

    def test_complex_scene_with_multiple_hierarchies(self, validator):
        """Complex scene with multiple nested hierarchies"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="World" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="World"]

[node name="Body" type="Node2D" parent="Player"]

[node name="Head" type="Node2D" parent="Player/Body"]

[node name="Enemy" type="CharacterBody2D" parent="World"]

[node name="Weapon" type="Node2D" parent="Enemy"]
"""
        scene = parse_tscn_string(tscn)
        result = validator.validate(scene)
        assert result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
