"""
Runtime Tools - Herramientas para ejecutar y analizar escenas en runtime.

Usa Godot CLI --headless --script para cargar escenas y obtener información.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, List, Optional

from .base import GodotCLIWrapper, find_godot_executable

logger = logging.getLogger(__name__)


# ==================== SCRIPT TEMPLATES ====================

SCENE_INFO_SCRIPT = '''
extends SceneTree

func _init():
    var scene_path = "{scene_path}"
    var scene = load(scene_path)
    
    if scene == null:
        print("TEST_OUTPUT: ERROR: Failed to load scene: " + scene_path)
        quit()
        return
    
    var instance = scene.instantiate()
    
    # Collect node info
    var nodes = []
    _collect_nodes(instance, nodes, "")
    
    # Collect scripts
    var scripts = []
    _collect_scripts(instance, scripts)
    
    # Collect resources
    var resources = []
    _collect_resources(instance, resources)
    
    var result = {{
        "node_count": nodes.size(),
        "nodes": nodes,
        "scripts": scripts,
        "resources": resources,
        "success": true
    }}
    
    print("TEST_OUTPUT: " + JSON.stringify(result))
    quit()

func _collect_nodes(node: Node, nodes: Array, parent_path: String):
    var path = parent_path + "/" + node.name if parent_path != "" else node.name
    nodes.append({{
        "name": node.name,
        "type": node.get_class(),
        "parent": parent_path,
        "groups": node.get_groups()
    }})
    
    for child in node.get_children():
        _collect_nodes(child, nodes, path)

func _collect_scripts(node: Node, scripts: Array):
    if node.get_script() != null:
        var script_path = node.get_script().resource_path
        if script_path not in scripts:
            scripts.append(script_path)
    
    for child in node.get_children():
        _collect_scripts(child, scripts)

func _collect_resources(node: Node, resources: Array):
    # Collect texture resources from Sprite2D, MeshInstance3D, etc.
    if node.has_method("get_texture"):
        var tex = node.get_texture()
        if tex != null and tex.resource_path != "" and tex.resource_path not in resources:
            resources.append(tex.resource_path)
    
    if node.has_method("get_mesh"):
        var mesh = node.get_mesh()
        if mesh != null and mesh.resource_path != "" and mesh.resource_path not in resources:
            resources.append(mesh.resource_path)
    
    for child in node.get_children():
        _collect_resources(child, resources)
'''

PERFORMANCE_SCRIPT = '''
extends SceneTree

func _init():
    var scene_path = "{scene_path}"
    var run_seconds = {run_seconds}
    
    var scene = load(scene_path)
    if scene == null:
        print("TEST_OUTPUT: ERROR: Failed to load scene")
        quit()
        return
    
    var instance = scene.instantiate()
    get_root().add_child(instance)
    
    # Performance tracking
    var fps_values = []
    var draw_calls_values = []
    var memory_values = []
    var frame_count = 0
    
    var start_time = Time.get_ticks_msec()
    
    while (Time.get_ticks_msec() - start_time) < (run_seconds * 1000):
        var fps = Engine.get_frames_per_second()
        var draw_calls = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
        var memory = OS.get_static_memory_usage() / (1024 * 1024)
        
        fps_values.append(fps)
        draw_calls_values.append(draw_calls)
        memory_values.append(memory)
        
        frame_count += 1
        await get_tree().process_frame
    
    # Calculate stats
    fps_values.sort()
    draw_calls_values.sort()
    memory_values.sort()
    
    var result = {{
        "fps_avg": _avg(fps_values),
        "fps_min": fps_values[0] if fps_values.size() > 0 else 0,
        "fps_max": fps_values[-1] if fps_values.size() > 0 else 0,
        "draw_calls_avg": _avg(draw_calls_values),
        "memory_mb_avg": _avg(memory_values),
        "frame_count": frame_count,
        "run_time_ms": Time.get_ticks_msec() - start_time,
        "success": true
    }}
    
    print("TEST_OUTPUT: " + JSON.stringify(result))
    quit()

func _avg(values: Array) -> float:
    if values.size() == 0:
        return 0.0
    var sum = 0.0
    for v in values:
        sum += v
    return sum / values.size()
'''

TEST_LOAD_SCRIPT = '''
extends SceneTree

func _init():
    var scene_path = "{scene_path}"
    var start_time = Time.get_ticks_msec()
    
    var scene = load(scene_path)
    var load_time = Time.get_ticks_msec() - start_time
    
    if scene == null:
        print("TEST_OUTPUT: " + JSON.stringify({{
            "success": false,
            "error": "Failed to load scene: " + scene_path,
            "load_time_ms": load_time
        }}))
        quit()
        return
    
    # Try to instantiate
    start_time = Time.get_ticks_msec()
    var instance = scene.instantiate()
    var instantiate_time = Time.get_ticks_msec() - start_time
    
    var result = {{
        "success": true,
        "load_time_ms": load_time,
        "instantiate_time_ms": instantiate_time,
        "total_time_ms": load_time + instantiate_time,
        "scene_class": scene.resource_path,
        "node_count": _count_nodes(instance),
        "errors": [],
        "warnings": []
    }}
    
    print("TEST_OUTPUT: " + JSON.stringify(result))
    quit()

func _count_nodes(node: Node) -> int:
    var count = 1
    for child in node.get_children():
        count += _count_nodes(child)
    return count
'''

CLASSDB_SCRIPT = '''
extends SceneTree

func _init():
    var class_name = "{class_name}"
    
    if class_name == "" or class_name == "all":
        # List all classes
        var classes = []
        for cls in ClassDB.get_class_list():
            classes.append(cls)
        
        print("TEST_OUTPUT: " + JSON.stringify({{
            "classes": classes,
            "count": classes.size(),
            "success": true
        }}))
    else:
        # Get specific class info
        if not ClassDB.class_exists(class_name):
            print("TEST_OUTPUT: " + JSON.stringify({{
                "success": false,
                "error": "Class not found: " + class_name
            }}))
            quit()
            return
        
        var methods = []
        for method in ClassDB.class_get_method_list(class_name):
            methods.append({{
                "name": method["name"],
                "args": method.get("args", []),
                "return": method.get("return", {})
            }})
        
        var properties = []
        for prop in ClassDB.class_get_property_list(class_name):
            properties.append({{
                "name": prop["name"],
                "type": prop.get("type", 0),
                "usage": prop.get("usage", 0)
            }})
        
        var signals_list = []
        for sig in ClassDB.class_get_signal_list(class_name):
            signals_list.append({{
                "name": sig["name"],
                "args": sig.get("args", [])
            }})
        
        var result = {{
            "class_name": class_name,
            "parent": ClassDB.get_parent_class(class_name),
            "methods": methods,
            "properties": properties,
            "signals": signals_list,
            "success": true
        }}
        
        print("TEST_OUTPUT: " + JSON.stringify(result))
    
    quit()
'''


# ==================== TOOLS ====================


def run_gdscript(
    project_path: str,
    script_content: str,
    godot_path: Optional[str] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Execute arbitrary GDScript code in a headless Godot instance.

    Args:
        project_path: Absolute path to the Godot project.
        script_content: GDScript code to execute. Must extend SceneTree or MainLoop.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, output, prints, errors.

    Example:
        run_gdscript(
            project_path="D:/MyGame",
            script_content='extends SceneTree\\nfunc _init():\\n    print("Hello")\\n    quit()'
        )
    """
    cli = GodotCLIWrapper(godot_path)
    
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    result = cli.run_script(script_content, project_path=project_path, timeout=timeout)
    
    # Extract TEST_OUTPUT if present
    test_output = None
    for line in result.get("prints", []):
        if line.startswith("TEST_OUTPUT:"):
            try:
                test_output = json.loads(line[12:].strip())
            except json.JSONDecodeError:
                test_output = line[12:].strip()
            break
    
    cli.cleanup()
    
    return {
        "success": result["success"],
        "output": result.get("prints", []),
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
        "test_output": test_output,
        "exit_code": result.get("exit_code", -1),
    }


def get_scene_info_runtime(
    project_path: str,
    scene_path: str,
    godot_path: Optional[str] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Get detailed information about a scene by loading it in runtime.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene (res://... or relative).
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with node_count, nodes (name, type, parent, groups), scripts, resources.

    Example:
        get_scene_info_runtime("D:/MyGame", "res://scenes/Player.tscn")
    """
    script = SCENE_INFO_SCRIPT.format(scene_path=scene_path)
    
    result = run_gdscript(project_path, script, godot_path, timeout)
    
    if result["test_output"] and isinstance(result["test_output"], dict):
        return {
            "success": result["test_output"].get("success", False),
            "node_count": result["test_output"].get("node_count", 0),
            "nodes": result["test_output"].get("nodes", []),
            "scripts": result["test_output"].get("scripts", []),
            "resources": result["test_output"].get("resources", []),
            "errors": result["errors"],
        }
    
    return {
        "success": False,
        "error": "Failed to get scene info",
        "raw_output": result.get("output", []),
        "errors": result.get("errors", []),
    }


def get_performance_metrics(
    project_path: str,
    scene_path: str,
    run_seconds: int = 5,
    godot_path: Optional[str] = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Run a scene and collect performance metrics (FPS, draw calls, memory).

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene to run.
        run_seconds: How many seconds to run the scene.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with fps_avg, fps_min, fps_max, draw_calls_avg, memory_mb_avg.

    Example:
        get_performance_metrics("D:/MyGame", "res://scenes/Main.tscn", run_seconds=10)
    """
    script = PERFORMANCE_SCRIPT.format(
        scene_path=scene_path,
        run_seconds=run_seconds
    )
    
    result = run_gdscript(project_path, script, godot_path, timeout)
    
    if result["test_output"] and isinstance(result["test_output"], dict):
        return {
            "success": result["test_output"].get("success", False),
            "fps_avg": result["test_output"].get("fps_avg", 0),
            "fps_min": result["test_output"].get("fps_min", 0),
            "fps_max": result["test_output"].get("fps_max", 0),
            "draw_calls_avg": result["test_output"].get("draw_calls_avg", 0),
            "memory_mb_avg": result["test_output"].get("memory_mb_avg", 0),
            "frame_count": result["test_output"].get("frame_count", 0),
            "run_time_ms": result["test_output"].get("run_time_ms", 0),
        }
    
    return {
        "success": False,
        "error": "Failed to collect performance metrics",
        "raw_output": result.get("output", []),
    }


def test_scene_load(
    project_path: str,
    scene_path: str,
    godot_path: Optional[str] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Test if a scene can be loaded and instantiated without errors.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene to test.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, load_time_ms, instantiate_time_ms, node_count, errors.

    Example:
        test_scene_load("D:/MyGame", "res://scenes/Player.tscn")
    """
    script = TEST_LOAD_SCRIPT.format(scene_path=scene_path)
    
    result = run_gdscript(project_path, script, godot_path, timeout)
    
    if result["test_output"] and isinstance(result["test_output"], dict):
        return {
            "success": result["test_output"].get("success", False),
            "load_time_ms": result["test_output"].get("load_time_ms", 0),
            "instantiate_time_ms": result["test_output"].get("instantiate_time_ms", 0),
            "total_time_ms": result["test_output"].get("total_time_ms", 0),
            "node_count": result["test_output"].get("node_count", 0),
            "errors": result["test_output"].get("errors", []),
            "warnings": result["test_output"].get("warnings", []),
        }
    
    return {
        "success": False,
        "error": "Failed to test scene load",
        "raw_output": result.get("output", []),
    }


def get_classdb_info(
    project_path: str,
    class_name: str = "",
    godot_path: Optional[str] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Get ClassDB information about Godot classes.

    Args:
        project_path: Absolute path to the Godot project.
        class_name: Name of the class to query. Empty string = list all classes.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with class info (methods, properties, signals) or list of all classes.

    Example:
        get_classdb_info("D:/MyGame", "CharacterBody2D")
        get_classdb_info("D:/MyGame", "")  # List all classes
    """
    script = CLASSDB_SCRIPT.format(class_name=class_name)
    
    result = run_gdscript(project_path, script, godot_path, timeout)
    
    if result["test_output"] and isinstance(result["test_output"], dict):
        return result["test_output"]
    
    return {
        "success": False,
        "error": "Failed to get ClassDB info",
        "raw_output": result.get("output", []),
    }


def call_group_runtime(
    project_path: str,
    scene_path: str,
    group: str,
    method: str,
    args: Optional[List[Any]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Call a method on all nodes in a group within a scene.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Path to the scene.
        group: Name of the group.
        method: Method to call.
        args: Optional list of arguments.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, nodes_called, results.

    Example:
        call_group_runtime("D:/MyGame", "res://scenes/Main.tscn", "enemies", "take_damage", [10])
    """
    args_str = json.dumps(args) if args else "[]"
    
    script = f'''
extends SceneTree

func _init():
    var scene = load("{scene_path}").instantiate()
    get_root().add_child(scene)
    
    var nodes = scene.get_tree().get_nodes_in_group("{group}")
    var results = []
    
    for node in nodes:
        if node.has_method("{method}"):
            var result = node.callv("{method}", {args_str})
            results.append({{"node": node.name, "result": str(result)}})
        else:
            results.append({{"node": node.name, "error": "Method not found"}})
    
    print("TEST_OUTPUT: " + JSON.stringify({{
        "success": true,
        "nodes_called": nodes.size(),
        "results": results
    }}))
    quit()
'''
    
    result = run_gdscript(project_path, script, godot_path, timeout)
    
    if result["test_output"] and isinstance(result["test_output"], dict):
        return result["test_output"]
    
    return {
        "success": False,
        "error": "Failed to call group",
        "raw_output": result.get("output", []),
    }


# ==================== REGISTRATION ====================


def register_runtime_tools(mcp) -> None:
    """Register all runtime tools."""
    logger.info("Registrando runtime tools...")
    
    mcp.add_tool(run_gdscript)
    mcp.add_tool(get_scene_info_runtime)
    mcp.add_tool(get_performance_metrics)
    mcp.add_tool(test_scene_load)
    mcp.add_tool(get_classdb_info)
    mcp.add_tool(call_group_runtime)
    
    logger.info("[OK] 6 runtime tools registradas")
