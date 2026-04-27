"""
Import Tools - Herramientas para reimportar assets y gestionar import settings.

Wrapper sobre Godot CLI --import y análisis de archivos .import.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List, Optional

from .base import GodotCLIWrapper

logger = logging.getLogger(__name__)


# ==================== TOOLS ====================


def reimport_assets(
    project_path: str,
    asset_paths: Optional[List[str]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """
    Reimport assets in the Godot project.

    Args:
        project_path: Absolute path to the Godot project.
        asset_paths: Optional list of specific assets to reimport.
                     If None, reimports all assets.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait.

    Returns:
        Dict with success, reimported_count, errors.

    Example:
        # Reimport all assets
        reimport_assets("D:/MyGame")
        
        # Reimport specific assets
        reimport_assets("D:/MyGame", ["res://sprites/player.png", "res://audio/music.ogg"])
    """
    cli = GodotCLIWrapper(godot_path)
    
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    # Build command
    args = ["--headless", "--import"]
    
    # If specific assets provided, we need to use --script approach
    # because --import doesn't accept specific files
    if asset_paths and len(asset_paths) > 0:
        # Build a script to reimport specific files
        files_str = ", ".join([f'"{path}"' for path in asset_paths])
        
        script = f'''
extends SceneTree

func _init():
    var files = [{files_str}]
    var editor = EditorInterface if Engine.is_editor_hint() else null
    
    if editor == null:
        print("TEST_OUTPUT: ERROR: Editor not available")
        quit()
        return
    
    var fs = editor.get_resource_filesystem()
    var reimported = 0
    
    for file_path in files:
        if FileAccess.file_exists(file_path):
            fs.reimport_files([file_path])
            reimported += 1
            print("Reimported: " + file_path)
        else:
            print("WARNING: File not found: " + file_path)
    
    print("TEST_OUTPUT: " + JSON.stringify({{
        "success": true,
        "reimported_count": reimported,
        "requested_count": files.size()
    }}))
    quit()
'''
        result = cli.run_script(script, project_path=project_path, timeout=timeout)
        
        # Extract test output
        test_output = None
        for line in result.get("prints", []):
            if line.startswith("TEST_OUTPUT:"):
                import json
                try:
                    test_output = json.loads(line[12:].strip())
                except:
                    pass
                break
        
        cli.cleanup()
        
        if test_output:
            return {
                "success": test_output.get("success", False),
                "reimported_count": test_output.get("reimported_count", 0),
                "requested_count": test_output.get("requested_count", 0),
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
            }
        
        return {
            "success": result["success"],
            "error": "Failed to reimport specific assets",
            "output": result.get("prints", []),
        }
    
    # Reimport all assets using --import
    result = cli.run_command(args, project_path=project_path, timeout=timeout)
    
    cli.cleanup()
    
    return {
        "success": result["success"],
        "message": "Reimported all assets" if result["success"] else "Reimport failed",
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
    }


def get_import_settings(
    project_path: str,
    asset_path: str,
) -> dict[str, Any]:
    """
    Get import settings for an asset from its .import file.

    Args:
        project_path: Absolute path to the Godot project.
        asset_path: Path to the asset (res://... or relative).

    Returns:
        Dict with import settings (importer, params, etc.).

    Example:
        get_import_settings("D:/MyGame", "res://sprites/player.png")
    """
    # Convert res:// to absolute path
    if asset_path.startswith("res://"):
        relative_path = asset_path[6:]
    else:
        relative_path = asset_path
    
    import_file = os.path.join(project_path, relative_path + ".import")
    
    if not os.path.isfile(import_file):
        return {
            "success": False,
            "error": f"Import file not found: {import_file}",
            "asset_path": asset_path,
        }
    
    try:
        settings = {}
        current_section = None
        
        with open(import_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                
                if not line or line.startswith(";"):
                    continue
                
                # Section header
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    settings[current_section] = {}
                    continue
                
                # Key-value pair
                if "=" in line and current_section:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    
                    # Try to parse as different types
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    elif "." in value and value.replace(".", "").replace("-", "").isdigit():
                        try:
                            value = float(value)
                        except:
                            pass
                    
                    settings[current_section][key] = value
        
        # Extract key info
        importer = settings.get("remap", {}).get("importer", "unknown")
        
        return {
            "success": True,
            "asset_path": asset_path,
            "importer": importer,
            "settings": settings,
            "import_file": import_file,
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read import settings: {e}",
            "asset_path": asset_path,
        }


# ==================== REGISTRATION ====================


def register_import_tools(mcp) -> None:
    """Register all import tools."""
    logger.info("Registrando import tools...")
    
    mcp.add_tool(reimport_assets)
    mcp.add_tool(get_import_settings)
    
    logger.info("[OK] 2 import tools registradas")
