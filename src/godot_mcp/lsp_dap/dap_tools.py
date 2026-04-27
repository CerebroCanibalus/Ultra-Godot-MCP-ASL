"""
DAP Tools - Herramientas para Debug Adapter Protocol de Godot.

Usa el puerto 6006 nativo del editor Godot.
Requiere que el editor esté abierto.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .client import GodotDAPClient, check_dap_available

logger = logging.getLogger(__name__)


# ==================== TOOLS ====================


def dap_start_debugging(
    project_path: str,
    scene_path: Optional[str] = None,
    host: str = "localhost",
    port: int = 6006,
) -> dict[str, Any]:
    """
    Start a debugging session in Godot.

    Args:
        project_path: Absolute path to the Godot project.
        scene_path: Optional scene to debug. If None, uses main scene.
        host: DAP server host.
        port: DAP server port.

    Returns:
        Dict with session status.

    Example:
        dap_start_debugging("D:/MyGame")
        dap_start_debugging("D:/MyGame", "res://scenes/Player.tscn")
    """
    if not check_dap_available(host, port):
        return {
            "success": False,
            "error": f"Godot DAP not available at {host}:{port}. "
                     f"Make sure Godot Editor is open with debugging enabled.",
        }
    
    client = GodotDAPClient(host, port)
    
    try:
        if not client.connect():
            return {
                "success": False,
                "error": "Failed to connect to DAP",
            }
        
        # Initialize
        init_result = client.initialize()
        
        # Launch
        launch_result = client.launch(project_path, scene_path)
        
        return {
            "success": True,
            "session_active": True,
            "capabilities": init_result.get("capabilities", {}),
            "project_path": project_path,
            "scene_path": scene_path,
            "host": host,
            "port": port,
        }
        
    except Exception as e:
        logger.error(f"DAP start error: {e}")
        client.disconnect()
        return {
            "success": False,
            "error": str(e),
        }


def dap_set_breakpoint(
    project_path: str,
    file_path: str,
    line: int,
    condition: Optional[str] = None,
    host: str = "localhost",
    port: int = 6006,
) -> dict[str, Any]:
    """
    Set a breakpoint in a GDScript file.

    Args:
        project_path: Absolute path to the Godot project.
        file_path: Path to the GDScript file.
        line: Line number (1-based for DAP).
        condition: Optional breakpoint condition.
        host: DAP server host.
        port: DAP server port.

    Returns:
        Dict with breakpoint info.

    Example:
        dap_set_breakpoint("D:/MyGame", "res://scripts/player.gd", 42)
    """
    if not check_dap_available(host, port):
        return {
            "success": False,
            "error": f"Godot DAP not available at {host}:{port}",
        }
    
    client = GodotDAPClient(host, port)
    
    try:
        if not client.connect():
            return {"success": False, "error": "Failed to connect to DAP"}
        
        client.initialize()
        
        result = client.set_breakpoint(file_path, line, condition)
        
        breakpoints = result.get("breakpoints", [])
        
        client.disconnect()
        
        return {
            "success": True,
            "breakpoints": breakpoints,
            "file_path": file_path,
            "line": line,
            "verified": all(bp.get("verified", False) for bp in breakpoints),
        }
        
    except Exception as e:
        logger.error(f"DAP breakpoint error: {e}")
        client.disconnect()
        return {"success": False, "error": str(e)}


def dap_continue(
    project_path: str,
    host: str = "localhost",
    port: int = 6006,
) -> dict[str, Any]:
    """
    Continue execution until next breakpoint.

    Args:
        project_path: Absolute path to the Godot project.
        host: DAP server host.
        port: DAP server port.

    Returns:
        Dict with success status.
    """
    if not check_dap_available(host, port):
        return {
            "success": False,
            "error": f"Godot DAP not available at {host}:{port}",
        }
    
    client = GodotDAPClient(host, port)
    
    try:
        if not client.connect():
            return {"success": False, "error": "Failed to connect to DAP"}
        
        client.initialize()
        result = client.continue_execution()
        
        client.disconnect()
        
        return {
            "success": True,
            "allThreadsContinued": result.get("allThreadsContinued", True),
        }
        
    except Exception as e:
        logger.error(f"DAP continue error: {e}")
        client.disconnect()
        return {"success": False, "error": str(e)}


def dap_step_over(
    project_path: str,
    host: str = "localhost",
    port: int = 6006,
) -> dict[str, Any]:
    """
    Step over current line.

    Args:
        project_path: Absolute path to the Godot project.
        host: DAP server host.
        port: DAP server port.

    Returns:
        Dict with success status.
    """
    if not check_dap_available(host, port):
        return {
            "success": False,
            "error": f"Godot DAP not available at {host}:{port}",
        }
    
    client = GodotDAPClient(host, port)
    
    try:
        if not client.connect():
            return {"success": False, "error": "Failed to connect to DAP"}
        
        client.initialize()
        result = client.step_over()
        
        client.disconnect()
        
        return {
            "success": True,
            "message": "Stepped over",
        }
        
    except Exception as e:
        logger.error(f"DAP step over error: {e}")
        client.disconnect()
        return {"success": False, "error": str(e)}


def dap_step_into(
    project_path: str,
    host: str = "localhost",
    port: int = 6006,
) -> dict[str, Any]:
    """
    Step into function call.

    Args:
        project_path: Absolute path to the Godot project.
        host: DAP server host.
        port: DAP server port.

    Returns:
        Dict with success status.
    """
    if not check_dap_available(host, port):
        return {
            "success": False,
            "error": f"Godot DAP not available at {host}:{port}",
        }
    
    client = GodotDAPClient(host, port)
    
    try:
        if not client.connect():
            return {"success": False, "error": "Failed to connect to DAP"}
        
        client.initialize()
        result = client.step_into()
        
        client.disconnect()
        
        return {
            "success": True,
            "message": "Stepped into",
        }
        
    except Exception as e:
        logger.error(f"DAP step into error: {e}")
        client.disconnect()
        return {"success": False, "error": str(e)}


def dap_get_stack_trace(
    project_path: str,
    host: str = "localhost",
    port: int = 6006,
) -> dict[str, Any]:
    """
    Get current stack trace with variables.

    Args:
        project_path: Absolute path to the Godot project.
        host: DAP server host.
        port: DAP server port.

    Returns:
        Dict with stack frames and variables.

    Example:
        dap_get_stack_trace("D:/MyGame")
    """
    if not check_dap_available(host, port):
        return {
            "success": False,
            "error": f"Godot DAP not available at {host}:{port}",
            "frames": [],
        }
    
    client = GodotDAPClient(host, port)
    
    try:
        if not client.connect():
            return {
                "success": False,
                "error": "Failed to connect to DAP",
                "frames": [],
            }
        
        client.initialize()
        
        # Get stack trace
        frames = client.get_stack_trace()
        
        # Get variables for each frame
        formatted_frames = []
        for frame in frames:
            frame_id = frame.get("id", 0)
            
            # Get scopes
            scopes = client.get_scopes(frame_id)
            
            # Get variables for each scope
            variables = []
            for scope in scopes:
                scope_vars = client.get_variables(scope.get("variablesReference", 0))
                variables.extend(scope_vars)
            
            formatted_frames.append({
                "function": frame.get("name", ""),
                "file": frame.get("source", {}).get("path", ""),
                "line": frame.get("line", 0),
                "column": frame.get("column", 0),
                "variables": [
                    {
                        "name": v.get("name", ""),
                        "value": v.get("value", ""),
                        "type": v.get("type", ""),
                    }
                    for v in variables
                ],
            })
        
        client.disconnect()
        
        return {
            "success": True,
            "frames": formatted_frames,
            "frame_count": len(formatted_frames),
        }
        
    except Exception as e:
        logger.error(f"DAP stack trace error: {e}")
        client.disconnect()
        return {
            "success": False,
            "error": str(e),
            "frames": [],
        }


# ==================== REGISTRATION ====================


def register_dap_tools(mcp) -> None:
    """Register all DAP tools."""
    logger.info("Registrando DAP tools...")
    
    mcp.add_tool(dap_start_debugging)
    mcp.add_tool(dap_set_breakpoint)
    mcp.add_tool(dap_continue)
    mcp.add_tool(dap_step_over)
    mcp.add_tool(dap_step_into)
    mcp.add_tool(dap_get_stack_trace)
    
    logger.info("[OK] 6 DAP tools registradas")
