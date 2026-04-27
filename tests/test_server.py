"""Tests para server.py - Verificación de registro de herramientas MCP.

Tests:
1. register_all_tools no lanza excepciones
2. Todas las herramientas esperadas están registradas
3. Cada módulo de herramientas se registra correctamente
4. El objeto MCP tiene el nombre correcto
"""

import sys
import os
import asyncio

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastmcp import FastMCP

from godot_mcp.server import mcp, register_all_tools
from godot_mcp.tools.scene_tools import register_scene_tools
from godot_mcp.tools.node_tools import register_node_tools
from godot_mcp.tools.resource_tools import register_resource_tools
from godot_mcp.tools.session_tools import register_session_tools
from godot_mcp.tools.project_tools import register_project_tools
from godot_mcp.tools.validation_tools import register_validation_tools
from godot_mcp.tools.signal_and_script_tools import register_signal_and_script_tools
from godot_mcp.tools.property_tools import register_property_tools
from godot_mcp.tools.debug_tools import register_debug_tools


# Herramientas esperadas por módulo
EXPECTED_SCENE_TOOLS = {
    "create_scene",
    "get_scene_tree",
    "save_scene",
    "list_scenes",
    "instantiate_scene",
    "modify_scene",
    "set_editable_paths",
    "remove_ext_resource",
    "remove_sub_resource",
}

EXPECTED_NODE_TOOLS = {
    "add_ext_resource",
    "add_node",
    "remove_node",
    "update_node",
    "get_node_properties",
    "rename_node",
    "move_node",
    "duplicate_node",
    "find_nodes",
    "add_node_groups",
    "remove_node_groups",
}

EXPECTED_RESOURCE_TOOLS = {
    "create_resource",
    "read_resource",
    "update_resource",
    "get_uid",
    "update_project_uids",
    "list_resources",
}

EXPECTED_SESSION_TOOLS = {
    "start_session",
    "end_session",
    "get_active_session",
    "list_sessions",
    "get_session_info",
    "commit_session",
    "discard_changes",
}

EXPECTED_PROJECT_TOOLS = {
    "get_project_info",
    "list_projects",
    "get_project_structure",
    "find_scripts",
    "find_resources",
}

EXPECTED_VALIDATION_TOOLS = {
    "validate_tscn",
    "validate_gdscript",
    "validate_project",
}

EXPECTED_SIGNAL_SCRIPT_TOOLS = {
    "connect_signal",
    "disconnect_signal",
    "list_signals",
    "set_script",
    "add_sub_resource",
}

EXPECTED_PROPERTY_TOOLS = {
    "set_node_properties",
}

EXPECTED_DEBUG_TOOLS = {
    "run_debug_scene",
    "check_script_syntax",
}

# NUEVO v4.0.0: Godot CLI Bridge
EXPECTED_EXPORT_TOOLS = {
    "export_project",
    "list_export_presets",
    "validate_export_preset",
    "get_export_log",
}

EXPECTED_RUNTIME_TOOLS = {
    "run_gdscript",
    "get_scene_info_runtime",
    "get_performance_metrics",
    "test_scene_load",
    "get_classdb_info",
    "call_group_runtime",
}

EXPECTED_IMPORT_TOOLS = {
    "reimport_assets",
    "get_import_settings",
}

EXPECTED_SCREENSHOT_TOOLS = {
    "capture_scene_frame",
    "capture_scene_sequence",
}

EXPECTED_MOVIE_TOOLS = {
    "write_movie",
    "write_movie_with_script",
}

# NUEVO v4.0.0: LSP/DAP Native
EXPECTED_LSP_TOOLS = {
    "lsp_get_completions",
    "lsp_get_hover",
    "lsp_get_symbols",
    "lsp_get_diagnostics",
}

EXPECTED_DAP_TOOLS = {
    "dap_start_debugging",
    "dap_set_breakpoint",
    "dap_continue",
    "dap_step_over",
    "dap_step_into",
    "dap_get_stack_trace",
}

# NUEVO v4.0.0: Project Intelligence
EXPECTED_DEPENDENCY_TOOLS = {
    "get_dependency_graph",
    "find_unused_assets",
}

EXPECTED_SIGNAL_GRAPH_TOOLS = {
    "get_signal_graph",
    "find_orphan_signals",
}

EXPECTED_CODE_ANALYSIS_TOOLS = {
    "analyze_script",
    "find_code_smells",
    "get_project_metrics",
}

EXPECTED_SKELETON_TOOLS = {
    "create_skeleton2d",
    "add_bone2d",
    "setup_polygon2d_skinning",
    "create_skeleton3d",
    "add_bone_attachment3d",
    "setup_mesh_skinning",
}

EXPECTED_ARRAY_TOOLS = {
    "scene_array_operation",
    "preview_array_operation",
}

EXPECTED_RESOURCE_BUILDER_TOOLS = {
    "build_resource",
    "build_nested_resource",
    "create_animation",
    "create_state_machine",
    "create_blend_space_1d",
    "create_blend_space_2d",
    "create_blend_tree",
    "create_sprite_frames",
    "create_tile_set",
}

ALL_EXPECTED_TOOLS = (
    EXPECTED_SCENE_TOOLS
    | EXPECTED_NODE_TOOLS
    | EXPECTED_RESOURCE_TOOLS
    | EXPECTED_SESSION_TOOLS
    | EXPECTED_PROJECT_TOOLS
    | EXPECTED_VALIDATION_TOOLS
    | EXPECTED_SIGNAL_SCRIPT_TOOLS
    | EXPECTED_PROPERTY_TOOLS
    | EXPECTED_DEBUG_TOOLS
    | EXPECTED_EXPORT_TOOLS
    | EXPECTED_RUNTIME_TOOLS
    | EXPECTED_IMPORT_TOOLS
    | EXPECTED_SCREENSHOT_TOOLS
    | EXPECTED_MOVIE_TOOLS
    | EXPECTED_LSP_TOOLS
    | EXPECTED_DAP_TOOLS
    | EXPECTED_DEPENDENCY_TOOLS
    | EXPECTED_SIGNAL_GRAPH_TOOLS
    | EXPECTED_CODE_ANALYSIS_TOOLS
    | EXPECTED_SKELETON_TOOLS
    | EXPECTED_ARRAY_TOOLS
    | EXPECTED_RESOURCE_BUILDER_TOOLS
)


def _get_registered_tool_names(mcp_instance: FastMCP) -> set:
    """Obtener nombres de herramientas registradas usando list_tools."""
    tools = asyncio.run(mcp_instance.list_tools())
    return {t.name for t in tools}


@pytest.fixture(autouse=True)
def reset_mcp():
    """Resetear herramientas del MCP global antes de cada test."""
    # Eliminar todas las herramientas registradas
    for tool_name in _get_registered_tool_names(mcp):
        mcp.local_provider.remove_tool(tool_name)
    yield


class TestServerRegistration:
    """Tests para register_all_tools."""

    def test_register_all_tools_no_exception(self):
        """register_all_tools no debe lanzar excepciones."""
        # No debería lanzar nada
        register_all_tools()

    def test_all_tools_registered(self):
        """Todas las herramientas esperadas deben estar registradas."""
        register_all_tools()
        registered = _get_registered_tool_names(mcp)

        for tool_name in ALL_EXPECTED_TOOLS:
            assert tool_name in registered, f"Tool '{tool_name}' not registered"

    def test_tool_count(self):
        """Debe registrarse el número correcto de herramientas."""
        register_all_tools()
        registered = _get_registered_tool_names(mcp)
        assert len(registered) == len(ALL_EXPECTED_TOOLS)


class TestServerName:
    """Tests para el nombre del servidor."""

    def test_mcp_name(self):
        """El servidor MCP debe llamarse 'godot-mcp'."""
        assert mcp.name == "godot-mcp"


class TestIndividualModuleRegistration:
    """Tests para registro individual de cada módulo."""

    def test_scene_tools_registration(self):
        """Scene tools deben registrarse correctamente."""
        register_scene_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_SCENE_TOOLS.issubset(registered)

    def test_node_tools_registration(self):
        """Node tools deben registrarse correctamente."""
        register_node_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_NODE_TOOLS.issubset(registered)

    def test_resource_tools_registration(self):
        """Resource tools deben registrarse correctamente."""
        register_resource_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_RESOURCE_TOOLS.issubset(registered)

    def test_session_tools_registration(self):
        """Session tools deben registrarse correctamente."""
        register_session_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_SESSION_TOOLS.issubset(registered)

    def test_project_tools_registration(self):
        """Project tools deben registrarse correctamente."""
        register_project_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_PROJECT_TOOLS.issubset(registered)

    def test_validation_tools_registration(self):
        """Validation tools deben registrarse correctamente."""
        register_validation_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_VALIDATION_TOOLS.issubset(registered)

    def test_signal_script_tools_registration(self):
        """Signal & script tools deben registrarse correctamente."""
        register_signal_and_script_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_SIGNAL_SCRIPT_TOOLS.issubset(registered)

    def test_property_tools_registration(self):
        """Property tools deben registrarse correctamente."""
        register_property_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_PROPERTY_TOOLS.issubset(registered)

    def test_debug_tools_registration(self):
        """Debug tools deben registrarse correctamente."""
        register_debug_tools(mcp)
        registered = _get_registered_tool_names(mcp)
        assert EXPECTED_DEBUG_TOOLS.issubset(registered)


class TestToolSchemas:
    """Tests para verificar que las herramientas tienen schemas válidos."""

    def test_tools_have_descriptions(self):
        """Todas las herramientas deben tener descripción."""
        register_all_tools()
        tools = asyncio.run(mcp.list_tools())

        for tool in tools:
            assert tool.description is not None, (
                f"Tool '{tool.name}' has no description"
            )
            assert len(tool.description) > 0, (
                f"Tool '{tool.name}' has empty description"
            )

    def test_create_scene_has_required_params(self):
        """create_scene debe tener los parámetros requeridos."""
        register_all_tools()
        tools = asyncio.run(mcp.list_tools())
        create_tool = next(t for t in tools if t.name == "create_scene")

        # Verificar que tiene parámetros (formato JSON Schema)
        assert create_tool.parameters is not None
        param_names = list(create_tool.parameters.get("properties", {}).keys())
        assert "session_id" in param_names
        assert "project_path" in param_names
        assert "scene_path" in param_names

    def test_add_node_has_required_params(self):
        """add_node debe tener los parámetros requeridos."""
        register_all_tools()
        tools = asyncio.run(mcp.list_tools())
        add_tool = next(t for t in tools if t.name == "add_node")

        assert add_tool.parameters is not None
        param_names = list(add_tool.parameters.get("properties", {}).keys())
        assert "session_id" in param_names
        assert "scene_path" in param_names
        assert "parent_path" in param_names
        assert "node_type" in param_names
        assert "node_name" in param_names
