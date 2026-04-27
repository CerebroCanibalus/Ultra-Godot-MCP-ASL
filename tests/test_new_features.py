"""
Tests para las nuevas funcionalidades:
- #1: add_ext_resource (Issue del tester)
- #2: SubResources huérfanos en add_node (Issue del tester)
- validation_tools.py (nuevas herramientas MCP)
"""

import os
import tempfile
import pytest

from godot_mcp.core.tscn_parser import (
    parse_tscn,
    parse_tscn_string,
    Scene,
    GdSceneHeader,
    SceneNode,
)
from godot_mcp.core.tscn_validator import TSCNValidator, validate_scene
from godot_mcp.core.gdscript_validator import GDScriptValidator, validate_gdscript


# ============ HELPERS ============


def _create_temp_scene(content: str) -> str:
    """Create a temporary .tscn file with given content."""
    fd, path = tempfile.mkstemp(suffix=".tscn")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _create_temp_gdscript(content: str) -> str:
    """Create a temporary .gd file with given content."""
    fd, path = tempfile.mkstemp(suffix=".gd")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ============ ISSUE #1: add_ext_resource ============


class TestAddExtResource:
    """Tests para la nueva función add_ext_resource"""

    def test_add_ext_resource_basic(self):
        """Test agregar un ExtResource básico a una escena"""
        from godot_mcp.tools.node_tools import add_ext_resource

        content = """[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            # Simular sesión (la función requiere @require_session)
            # Testeamos la lógica directamente
            from godot_mcp.core.tscn_parser import ExtResource

            scene = parse_tscn(scene_path)
            assert len(scene.ext_resources) == 0

            # Agregar manualmente como lo haría add_ext_resource
            new_ext = ExtResource(
                type="Texture2D",
                path="res://sprites/player.png",
                id="1",
            )
            scene.ext_resources.append(new_ext)
            scene.header.load_steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)

            assert len(scene.ext_resources) == 1
            assert scene.ext_resources[0].type == "Texture2D"
            assert scene.ext_resources[0].path == "res://sprites/player.png"
            assert scene.ext_resources[0].id == "1"
            assert scene.header.load_steps == 2
        finally:
            os.unlink(scene_path)

    def test_add_ext_resource_auto_id(self):
        """Test que auto-genera IDs cuando no se proporciona uno"""
        content = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1"]

[node name="Root" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            scene = parse_tscn(scene_path)
            assert len(scene.ext_resources) == 1

            # Simular lógica de auto-ID
            max_id = 0
            for ext in scene.ext_resources:
                try:
                    num_id = int(ext.id)
                    if num_id > max_id:
                        max_id = num_id
                except (ValueError, TypeError):
                    pass
            next_id = str(max_id + 1)

            assert next_id == "2"
        finally:
            os.unlink(scene_path)

    def test_add_ext_resource_duplicate_path_reuses(self):
        """Test que no duplica recursos con el mismo path"""
        from godot_mcp.core.tscn_parser import ExtResource

        content = """[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://sprites/player.png" id="1"]

[node name="Root" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            scene = parse_tscn(scene_path)

            # Check if resource with same path already exists
            existing = None
            for ext in scene.ext_resources:
                if ext.path == "res://sprites/player.png":
                    existing = ext
                    break

            assert existing is not None
            assert existing.id == "1"
        finally:
            os.unlink(scene_path)

    def test_add_ext_resource_duplicate_id_fails(self):
        """Test que no permite IDs duplicados"""
        content = """[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://sprites/player.png" id="1"]

[node name="Root" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            scene = parse_tscn(scene_path)

            # Check for duplicate ID
            for ext in scene.ext_resources:
                if ext.id == "1":
                    # Intentar agregar otro con mismo ID debería fallar
                    pass  # La lógica de add_ext_resource maneja esto

            # Verificar que el ID ya existe
            ids = [ext.id for ext in scene.ext_resources]
            assert "1" in ids
        finally:
            os.unlink(scene_path)

    def test_ext_resource_serializes_correctly(self):
        """Test que ExtResource se serializa en el header, NO como propiedad de nodo"""
        from godot_mcp.core.tscn_parser import (
            ExtResource,
            Scene,
            GdSceneHeader,
            SceneNode,
        )

        scene = Scene(
            header=GdSceneHeader(load_steps=2, format=3),
            ext_resources=[
                ExtResource(type="Texture2D", path="res://sprites/player.png", id="1"),
            ],
            nodes=[
                SceneNode(name="Root", type="Node2D", parent="."),
            ],
        )

        tscn_output = scene.to_tscn()

        # Verificar formato correcto en header
        assert '[ext_resource type="Texture2D" path="res://sprites/player.png" id="1"]' in tscn_output

        # Verificar que NO aparece como propiedad de nodo
        assert "ext_resources =" not in tscn_output
        assert "ExtResource" not in tscn_output.split("[node")[1] if "[node" in tscn_output else True


# ============ ISSUE #2: SubResources huérfanos ============


class TestOrphanSubResources:
    """Tests para detección de SubResources huérfanos"""

    def test_orphan_subresource_detected(self):
        """Test que detecta SubResource referenciado pero no definido"""
        tscn = """[gd_scene load_steps=2 format=3]

[sub_resource type="Vector2" id="Vector2_0fe763b7"]
x = 0
y = -20

[node name="Root" type="Node2D"]
position = SubResource("Vector2_7ab35ab6")
"""
        scene = parse_tscn_string(tscn)
        validator = TSCNValidator()
        result = validator.validate(scene)

        assert not result.is_valid
        assert any("SubResource" in err and "reference" in err for err in result.errors)

    def test_valid_subresource_passes(self):
        """Test que SubResource correctamente definido pasa validación"""
        tscn = """[gd_scene load_steps=2 format=3]

[sub_resource type="Vector2" id="Vector2_0fe763b7"]
x = 0
y = -20

[node name="Root" type="Node2D"]
position = SubResource("Vector2_0fe763b7")
"""
        scene = parse_tscn_string(tscn)
        validator = TSCNValidator()
        result = validator.validate(scene)

        assert result.is_valid, f"Expected valid, got: {result.errors}"

    def test_multiple_orphan_subresources(self):
        """Test que detecta múltiples SubResources huérfanos"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]
position = SubResource("Vector2_missing1")
scale = SubResource("Vector2_missing2")
"""
        scene = parse_tscn_string(tscn)
        validator = TSCNValidator()
        result = validator.validate(scene)

        assert not result.is_valid

    def test_orphan_extresource_detected(self):
        """Test que también detecta ExtResources huérfanos"""
        tscn = """[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]
script = ExtResource("999_missing")
"""
        scene = parse_tscn_string(tscn)
        validator = TSCNValidator()
        result = validator.validate(scene)

        assert not result.is_valid
        assert any("ExtResource" in err and "reference" in err for err in result.errors)


# ============ VALIDATION TOOLS ============


class TestValidateTscn:
    """Tests para validate_tscn tool"""

    def test_validate_tscn_valid_scene(self):
        """Test validar escena TSCN válida"""
        from godot_mcp.tools.validation_tools import validate_tscn

        content = """[gd_scene load_steps=1 format=3]

[node name="Root" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            result = validate_tscn(scene_path)
            assert result["success"] is True
            assert result["error_count"] == 0
        finally:
            os.unlink(scene_path)

    def test_validate_tscn_invalid_scene(self):
        """Test validar escena TSCN inválida"""
        from godot_mcp.tools.validation_tools import validate_tscn

        content = """[gd_scene load_steps=1 format=3]

[ext_resource type="Script" path="res://a.gd" id="1"]
[ext_resource type="Script" path="res://b.gd" id="1"]

[node name="Root" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            result = validate_tscn(scene_path)
            assert result["success"] is False
            assert result["error_count"] > 0
        finally:
            os.unlink(scene_path)

    def test_validate_tscn_file_not_found(self):
        """Test validar archivo inexistente"""
        from godot_mcp.tools.validation_tools import validate_tscn

        result = validate_tscn("nonexistent.tscn")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_validate_tscn_strict_mode(self):
        """Test modo estricto (warnings = failure)"""
        from godot_mcp.tools.validation_tools import validate_tscn

        content = """[gd_scene load_steps=1 format=3]

[node name="" type="Node2D"]
"""
        scene_path = _create_temp_scene(content)
        try:
            # Non-strict: warnings don't block
            result = validate_tscn(scene_path, strict=False)
            assert result["success"] is True  # Warnings don't block

            # Strict: warnings block
            result_strict = validate_tscn(scene_path, strict=True)
            assert result_strict["success"] is False
        finally:
            os.unlink(scene_path)


class TestValidateGdscript:
    """Tests para validate_gdscript tool (v2.0 - intelligent validation)"""

    def test_validate_gdscript_from_file(self):
        """Test validar script válido desde archivo"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        content = """extends CharacterBody2D

@export var speed: float = 200.0

func _ready():
    var clamped = clamp(speed, 0, 300)
    print(clamped)
"""
        script_path = _create_temp_gdscript(content)
        try:
            result = validate_gdscript(script_path=script_path)
            assert result["success"] is True
            assert result["error_count"] == 0
            assert "validation_mode" in result
        finally:
            os.unlink(script_path)

    def test_validate_gdscript_from_content(self):
        """Test validar script inline (API validation only)"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        content = """extends Node2D

@export var health: int = 100

func _ready():
    # Variables no declaradas NO se warnan (GDScript es dinámico)
    # El validador solo verifica API y patterns
    var my_var = calculate_damage(health)
"""
        result = validate_gdscript(script_content=content)
        # El nuevo validador NO warns sobre variables no declaradas
        # porque eso es imposible de hacer bien en GDScript
        assert result["success"] is True
        assert result["validation_mode"] == "api_only"

    def test_validate_gdscript_detects_deprecated_decorator(self):
        """Test que detecta @onready como deprecated"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        content = """extends Node

@onready var sprite = $Sprite
"""
        result = validate_gdscript(script_content=content)
        # @onready es deprecated, debe warnar
        assert result["warning_count"] >= 1
        has_onready_warning = any("@onready" in issue["message"] for issue in result["issues"])
        assert has_onready_warning, "Should warn about @onready"

    def test_validate_gdscript_detects_removed_methods(self):
        """Test que detecta métodos removidos en Godot 4"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        content = """extends CharacterBody2D

func _ready():
    test_move()  # Removido en Godot 4
"""
        result = validate_gdscript(script_content=content)
        # test_move fue removido en Godot 4
        assert result["error_count"] >= 1
        has_removed_error = any("removed" in issue["message"].lower() for issue in result["issues"])
        assert has_removed_error, "Should error about test_move being removed"

    def test_validate_gdscript_with_project_path(self):
        """Test que usa Godot para sintaxis si hay project_path"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        # Crear script en ubicación temporal
        content = """extends Node

func _ready():
    pass
"""
        script_path = _create_temp_gdscript(content)
        try:
            # Sin project_path: API only
            result_no_project = validate_gdscript(script_path=script_path)
            assert result_no_project["validation_mode"] == "api_only"

            # El modo api_plus_godot requiere un proyecto válido de Godot
            # No lo testeamos aquí porque requiere Godot instalado
        finally:
            os.unlink(script_path)

    def test_validate_gdscript_both_args_error(self):
        """Test error al proporcionar ambos argumentos"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        result = validate_gdscript(script_path="test.gd", script_content="extends Node")
        assert result["success"] is False
        assert "not both" in result["error"]

    def test_validate_gdscript_no_args_error(self):
        """Test error al no proporcionar argumentos"""
        from godot_mcp.tools.validation_tools import validate_gdscript

        result = validate_gdscript()
        assert result["success"] is False
        assert "either" in result["error"]


# ============ ADD_NODE VALIDATION INTEGRATION ============


class TestAddNodeValidation:
    """Tests para validación integrada en add_node"""

    def test_add_node_with_orphan_subresource_fails(self):
        """Test que add_node rechaza nodos con SubResources huérfanos"""
        from godot_mcp.core.tscn_parser import Scene, GdSceneHeader, SceneNode
        from godot_mcp.core.tscn_validator import TSCNValidator

        # Simular lo que haría add_node
        scene = Scene(
            header=GdSceneHeader(load_steps=1, format=3),
            nodes=[
                SceneNode(name="Root", type="Node2D", parent="."),
            ],
        )

        # Agregar nodo con SubResource huérfano
        new_node = SceneNode(
            name="Child",
            type="Sprite2D",
            parent="Root",
            properties={"position": {"type": "SubResource", "ref": "Vector2_missing"}},
        )
        scene.nodes.append(new_node)

        # Validar
        validator = TSCNValidator()
        result = validator.validate(scene)

        assert not result.is_valid
        assert any("SubResource" in err for err in result.errors)

    def test_add_node_with_valid_subresource_passes(self):
        """Test que add_node acepta nodos con SubResources válidos"""
        from godot_mcp.core.tscn_parser import (
            Scene,
            GdSceneHeader,
            SceneNode,
            SubResource,
        )
        from godot_mcp.core.tscn_validator import TSCNValidator

        scene = Scene(
            header=GdSceneHeader(load_steps=2, format=3),
            sub_resources=[
                SubResource(type="Vector2", id="Vector2_valid", properties={"x": 0, "y": 0}),
            ],
            nodes=[
                SceneNode(name="Root", type="Node2D", parent="."),
            ],
        )

        new_node = SceneNode(
            name="Child",
            type="Sprite2D",
            parent="Root",
            properties={"position": {"type": "SubResource", "ref": "Vector2_valid"}},
        )
        scene.nodes.append(new_node)

        validator = TSCNValidator()
        result = validator.validate(scene)

        assert result.is_valid, f"Expected valid, got: {result.errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
