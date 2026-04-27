"""
Validation Tools - Herramientas MCP para validar escenas y scripts.

Expone los validadores TSCN y GDScript como herramientas MCP
para que los LLMs puedan verificar archivos antes de guardarlos.

El validador de GDScript usa una arquitectura de 3 capas:
1. Godot real (sintaxis) - via godot_check_script_syntax
2. API de Godot 4.6 (métodos/propiedades) - via godot_api.json
3. Análisis de patrones (decorators deprecated, etc.)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastmcp import FastMCP

from godot_mcp.core.gdscript_validator import (
    GDScriptValidator,
    validate_gdscript as _validate_gdscript_api,
)
from godot_mcp.core.tscn_parser import parse_tscn
from godot_mcp.core.tscn_validator import (
    TSCNValidator,
    validate_scene as _validate_tscn_core,
)

logger = logging.getLogger(__name__)


def validate_tscn(
    scene_path: str,
    project_path: str | None = None,
    strict: bool = False,
) -> dict:
    """
    Validate a TSCN scene file for common errors.

    Checks:
    - Root node has no parent attribute
    - Unique ExtResource/SubResource IDs
    - Valid resource references (no orphaned SubResources)
    - Valid node types
    - Valid parent paths (hierarchical chains)
    - ExtResource files exist on disk (if project_path provided)
    - Valid gd_scene header (load_steps, format)

    Args:
        scene_path: Absolute or relative path to the .tscn file.
        project_path: Absolute path to the Godot project (for file existence checks).
        strict: If True, warnings also block validation.

    Returns:
        Dict with validation results:
        - success: True if scene is valid
        - errors: List of error messages
        - warnings: List of warning messages
        - infos: List of informational messages
        - scene_path: The validated scene path

    Example:
        result = validate_tscn("scenes/Player.tscn", project_path="D:/MyGame")
        if not result["success"]:
            print(f"Errors: {result['errors']}")
    """
    try:
        # Normalize path
        if not scene_path.endswith(".tscn"):
            scene_path = scene_path + ".tscn"

        # Check file exists
        if not os.path.isfile(scene_path):
            return {
                "success": False,
                "error": f"Scene file not found: {scene_path}",
            }

        # Parse scene
        scene = parse_tscn(scene_path)

        # Validate
        validator = TSCNValidator(project_path=project_path)
        result = validator.validate(scene)

        # In strict mode, warnings also count as failures
        is_valid = result.is_valid
        if strict and result.warnings:
            is_valid = False

        return {
            "success": is_valid,
            "scene_path": scene_path,
            "errors": result.errors,
            "warnings": result.warnings,
            "infos": result.infos,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "info_count": len(result.infos),
        }

    except Exception as e:
        logger.exception(f"Error validating TSCN: {e}")
        return {
            "success": False,
            "error": str(e),
            "scene_path": scene_path,
        }


def validate_gdscript(
    script_path: str | None = None,
    script_content: str | None = None,
    project_path: str | None = None,
    strict: bool = False,
    use_godot_syntax: bool = True,
) -> dict:
    """
    Validate a GDScript file using intelligent validation.

    This validator uses a 3-layer architecture:
    1. Godot real syntax (via godot_check_script_syntax) - if project_path provided
    2. Godot 4.6 API (methods/properties) - always enabled
    3. Pattern analysis (deprecated decorators, etc.) - always enabled

    NOTE: This validator does NOT attempt to detect "undeclared variables"
    as GDScript is too dynamic for static analysis. Use godot_check_script_syntax
    for real syntax errors.

    Args:
        script_path: Path to the .gd file (mutually exclusive with script_content).
        script_content: Raw GDScript content (mutually exclusive with script_path).
        project_path: Path to Godot project (for syntax checking with Godot).
        strict: If True, warnings also block validation.
        use_godot_syntax: If True and project_path provided, uses Godot for
                          real syntax checking (recommended).

    Returns:
        Dict with validation results:
        - success: True if script is valid
        - issues: List of {line, severity, message, suggestion}
        - error_count: Number of errors
        - warning_count: Number of warnings
        - info_count: Number of info messages
        - validation_mode: "api_only" or "api_plus_godot"

    Example:
        # API only (no Godot needed)
        result = validate_gdscript(script_content="extends Node")

        # Full validation with Godot
        result = validate_gdscript(
            script_path="res://scripts/Player.gd",
            project_path="D:/MyGame"
        )
    """
    try:
        # Get script content
        if script_path and script_content:
            return {
                "success": False,
                "error": "Provide either script_path OR script_content, not both",
            }

        resolved_script_path = script_path
        if script_path:
            if not script_path.endswith(".gd"):
                resolved_script_path = script_path + ".gd"

            if not os.path.isfile(resolved_script_path):
                return {
                    "success": False,
                    "error": f"Script file not found: {resolved_script_path}",
                }

            with open(resolved_script_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif script_content:
            content = script_content
        else:
            return {
                "success": False,
                "error": "Provide either script_path or script_content",
            }

        # Perform validation
        validator = GDScriptValidator()
        validation_mode = "api_only"

        # Try Godot syntax check if project_path provided
        godot_result = None
        if project_path and use_godot_syntax and script_path:
            try:
                from godot_mcp.tools.debug_tools import check_script_syntax

                # Determine script path for Godot
                if script_path.startswith("res://"):
                    godot_script_path = script_path
                else:
                    # Convert absolute path to res://
                    try:
                        from pathlib import Path

                        project_abs = Path(project_path).resolve()
                        script_abs = Path(resolved_script_path).resolve()
                        relative = script_abs.relative_to(project_abs)
                        godot_script_path = f"res://{relative.as_posix()}"
                    except ValueError:
                        # Not under project, use absolute path
                        godot_script_path = resolved_script_path

                godot_result = check_script_syntax(
                    project_path=project_path,
                    script_path=godot_script_path,
                    timeout=30,
                )
                validation_mode = "api_plus_godot"
            except Exception as e:
                logger.warning(f"Godot syntax check failed: {e}")
                godot_result = None

        # Combine results
        if godot_result and godot_result.get("success") is not None:
            result = validator.validate_with_godot(content, godot_result)
        else:
            result = validator.validate(content)

        # In strict mode, warnings also count as failures
        has_errors = any(i.severity == "error" for i in result.issues)
        has_warnings = any(i.severity == "warning" for i in result.issues)

        is_valid = not has_errors
        if strict and has_warnings:
            is_valid = False

        # Convert issues to dicts for JSON serialization
        issues = [
            {
                "line": issue.line,
                "severity": issue.severity,
                "message": issue.message,
                "suggestion": issue.suggestion,
            }
            for issue in result.issues
        ]

        error_count = sum(1 for i in result.issues if i.severity == "error")
        warning_count = sum(1 for i in result.issues if i.severity == "warning")
        info_count = sum(1 for i in result.issues if i.severity == "info")

        return {
            "success": is_valid,
            "script_path": script_path or "(inline content)",
            "issues": issues,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "validation_mode": validation_mode,
        }

    except Exception as e:
        logger.exception(f"Error validating GDScript: {e}")
        return {
            "success": False,
            "error": str(e),
            "script_path": script_path or "(inline content)",
        }


def validate_project(
    project_path: str,
    strict: bool = False,
) -> dict:
    """
    Validate all TSCN and GDScript files in a Godot project.

    Scans the project directory recursively for .tscn and .gd files
    and validates each one.

    Args:
        project_path: Absolute path to the Godot project directory.
        strict: If True, warnings also count as failures.

    Returns:
        Dict with summary of validation results across all files.

    Example:
        result = validate_project("D:/MyGame")
        print(f"Validated {result['files_checked']} files")
        print(f"Errors: {result['total_errors']}, Warnings: {result['total_warnings']}")
    """
    try:
        if not os.path.isdir(project_path):
            return {
                "success": False,
                "error": f"Project path does not exist: {project_path}",
            }

        # Check for project.godot
        if not os.path.isfile(os.path.join(project_path, "project.godot")):
            return {
                "success": False,
                "error": f"Not a valid Godot project (no project.godot): {project_path}",
            }

        results = {
            "success": True,
            "project_path": project_path,
            "files_checked": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "total_infos": 0,
            "file_results": [],
        }

        # Find all .tscn and .gd files
        from pathlib import Path

        base = Path(project_path)
        tscn_files = list(base.glob("**/*.tscn"))
        gd_files = list(base.glob("**/*.gd"))

        # Validate TSCN files
        for tscn_file in tscn_files:
            file_result = validate_tscn(str(tscn_file), project_path=project_path, strict=strict)
            results["files_checked"] += 1
            results["total_errors"] += file_result.get("error_count", 0)
            results["total_warnings"] += file_result.get("warning_count", 0)
            results["total_infos"] += file_result.get("info_count", 0)

            if not file_result.get("success", True):
                results["success"] = False

            results["file_results"].append(
                {
                    "file": str(tscn_file.relative_to(base)),
                    "type": "tscn",
                    "success": file_result.get("success", False),
                    "errors": file_result.get("errors", []),
                    "warnings": file_result.get("warnings", []),
                }
            )

        # Validate GDScript files with project path for Godot syntax check
        for gd_file in gd_files:
            file_result = validate_gdscript(
                script_path=str(gd_file),
                project_path=project_path,
                strict=strict,
                use_godot_syntax=True,
            )
            results["files_checked"] += 1
            results["total_errors"] += file_result.get("error_count", 0)
            results["total_warnings"] += file_result.get("warning_count", 0)
            results["total_infos"] += file_result.get("info_count", 0)

            if not file_result.get("success", True):
                results["success"] = False

            results["file_results"].append(
                {
                    "file": str(gd_file.relative_to(base)),
                    "type": "gd",
                    "success": file_result.get("success", False),
                    "issues": file_result.get("issues", []),
                }
            )

        return results

    except Exception as e:
        logger.exception(f"Error validating project: {e}")
        return {
            "success": False,
            "error": str(e),
            "project_path": project_path,
        }


# ============ REGISTRATION ============


def register_validation_tools(mcp: FastMCP) -> None:
    """
    Register all validation tools with a FastMCP server.

    Args:
        mcp: FastMCP instance to register tools with
    """
    mcp.add_tool(validate_tscn)
    mcp.add_tool(validate_gdscript)
    mcp.add_tool(validate_project)
    logger.info("[OK] 3 validation tools registered")
