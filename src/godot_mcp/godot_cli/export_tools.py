"""
Export Tools - Herramientas para exportar proyectos Godot.

Wrapper sobre Godot CLI --export-release, --export-debug, --export-pack.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from .base import GodotCLIWrapper, find_godot_executable

logger = logging.getLogger(__name__)


def _parse_export_presets(content: str) -> List[dict]:
    """Parse export_presets.cfg file."""
    presets = []
    current_preset = None
    
    for line in content.splitlines():
        line = line.strip()
        
        # New preset section
        if line.startswith("[preset."):
            if current_preset:
                presets.append(current_preset)
            current_preset = {"id": line[8:-1], "name": "", "platform": ""}
        
        elif current_preset and line.startswith("name="):
            current_preset["name"] = line[5:].strip('"')
        
        elif current_preset and line.startswith("platform="):
            current_preset["platform"] = line[9:].strip('"')
    
    if current_preset:
        presets.append(current_preset)
    
    return presets


# ==================== TOOLS ====================


def export_project(
    project_path: str,
    export_preset: str,
    output_path: str,
    export_mode: str = "release",
    patches: Optional[List[str]] = None,
    godot_path: Optional[str] = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Export a Godot project using an export preset.

    Args:
        project_path: Absolute path to the Godot project.
        export_preset: Name of the export preset to use.
        output_path: Path for the exported file.
        export_mode: "release", "debug", or "pack".
        patches: Optional list of PCK patch files to include.
        godot_path: Optional path to Godot executable.
        timeout: Maximum seconds to wait for export.

    Returns:
        Dict with success, output_path, export_time, warnings, file_size_mb.

    Example:
        export_project(
            project_path="D:/MyGame",
            export_preset="Windows Desktop",
            output_path="D:/builds/game.exe",
            export_mode="release"
        )
    """
    import time
    
    start_time = time.time()
    
    cli = GodotCLIWrapper(godot_path)
    
    # Validate project
    is_valid, error = cli.validate_project(project_path)
    if not is_valid:
        return {"success": False, "error": error}
    
    # Build export command
    export_flags = {
        "release": "--export-release",
        "debug": "--export-debug",
        "pack": "--export-pack",
    }
    
    if export_mode not in export_flags:
        return {
            "success": False,
            "error": f"Invalid export_mode: {export_mode}. Use: release, debug, pack"
        }
    
    args = [
        "--headless",
        export_flags[export_mode],
        export_preset,
        output_path,
    ]
    
    # Add patches if provided
    if patches:
        for patch in patches:
            args.extend(["--patch", patch])
    
    result = cli.run_command(args, project_path=project_path, timeout=timeout)
    
    export_time = time.time() - start_time
    
    # Get file size if export succeeded
    file_size_mb = None
    if result["success"] and os.path.exists(output_path):
        file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
    
    cli.cleanup()
    
    return {
        "success": result["success"],
        "output_path": output_path,
        "export_time_ms": round(export_time * 1000),
        "export_mode": export_mode,
        "preset": export_preset,
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
        "file_size_mb": file_size_mb,
        "godot_path": cli.godot_path,
    }


def list_export_presets(
    project_path: str
) -> dict[str, Any]:
    """
    List all export presets configured in the project.

    Args:
        project_path: Absolute path to the Godot project.

    Returns:
        Dict with list of presets (name, platform, id).

    Example:
        list_export_presets("D:/MyGame")
        # Returns:
        # {
        #   "presets": [
        #     {"name": "Windows Desktop", "platform": "Windows", "id": "0"},
        #     {"name": "Web", "platform": "Web", "id": "1"}
        #   ]
        # }
    """
    project_path = os.path.abspath(project_path)
    presets_file = os.path.join(project_path, "export_presets.cfg")
    
    if not os.path.isfile(presets_file):
        return {
            "success": True,
            "presets": [],
            "message": "No export_presets.cfg found. Configure presets in Godot Editor."
        }
    
    try:
        with open(presets_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        presets = _parse_export_presets(content)
        
        return {
            "success": True,
            "presets": presets,
            "count": len(presets),
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read export_presets.cfg: {e}",
        }


def validate_export_preset(
    project_path: str,
    preset_name: str
) -> dict[str, Any]:
    """
    Validate that an export preset exists and is properly configured.

    Args:
        project_path: Absolute path to the Godot project.
        preset_name: Name of the export preset to validate.

    Returns:
        Dict with valid (bool), errors, warnings.
    """
    result = list_export_presets(project_path)
    
    if not result["success"]:
        return result
    
    presets = result["presets"]
    preset_names = [p["name"] for p in presets]
    
    if preset_name not in preset_names:
        return {
            "success": False,
            "valid": False,
            "error": f"Preset '{preset_name}' not found",
            "available_presets": preset_names,
        }
    
    # Find the preset
    preset = next(p for p in presets if p["name"] == preset_name)
    
    return {
        "success": True,
        "valid": True,
        "preset": preset,
        "message": f"Preset '{preset_name}' is valid and ready for export",
    }


def get_export_log(
    project_path: str,
    lines: int = 50
) -> dict[str, Any]:
    """
    Get the last lines from the Godot export log.

    Args:
        project_path: Absolute path to the Godot project.
        lines: Number of lines to retrieve.

    Returns:
        Dict with log_lines, log_path.
    """
    # Godot stores logs in different locations per OS
    log_paths = []
    
    if os.name == "nt":  # Windows
        app_data = os.environ.get("APPDATA", "")
        log_paths.append(os.path.join(app_data, "Godot", "app_userdata", "logs", "godot.log"))
    else:  # Linux/macOS
        home = os.path.expanduser("~")
        log_paths.append(os.path.join(home, ".local", "share", "godot", "app_userdata", "logs", "godot.log"))
        log_paths.append(os.path.join(home, "Library", "Application Support", "Godot", "logs", "godot.log"))
    
    # Also check project-specific log
    log_paths.append(os.path.join(project_path, ".godot", "editor", "editor.log"))
    
    for log_path in log_paths:
        if os.path.isfile(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    
                    return {
                        "success": True,
                        "log_lines": [line.rstrip() for line in last_lines],
                        "log_path": log_path,
                        "total_lines": len(all_lines),
                        "retrieved_lines": len(last_lines),
                    }
            except Exception as e:
                logger.warning(f"Failed to read log {log_path}: {e}")
                continue
    
    return {
        "success": False,
        "error": "No export log found",
        "searched_paths": log_paths,
    }


# ==================== REGISTRATION ====================


def register_export_tools(mcp) -> None:
    """Register all export tools."""
    logger.info("Registrando export tools...")
    
    mcp.add_tool(export_project)
    mcp.add_tool(list_export_presets)
    mcp.add_tool(validate_export_preset)
    mcp.add_tool(get_export_log)
    
    logger.info("[OK] 4 export tools registradas")
