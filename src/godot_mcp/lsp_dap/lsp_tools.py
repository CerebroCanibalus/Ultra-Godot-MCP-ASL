"""
LSP Tools - Herramientas para Language Server Protocol de Godot.

Usa el puerto 6005 nativo del editor Godot.
Requiere que el editor esté abierto.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .client import GodotLSPClient, check_lsp_available

logger = logging.getLogger(__name__)


# ==================== TOOLS ====================


def lsp_get_completions(
    project_path: str,
    file_path: str,
    line: int,
    column: int,
    host: str = "localhost",
    port: int = 6005,
) -> dict[str, Any]:
    """
    Get code completions at a specific position in a GDScript file.

    Args:
        project_path: Absolute path to the Godot project.
        file_path: Path to the GDScript file.
        line: Line number (0-based).
        column: Column number (0-based).
        host: LSP server host.
        port: LSP server port.

    Returns:
        Dict with completions list.

    Example:
        lsp_get_completions(
            project_path="D:/MyGame",
            file_path="res://scripts/player.gd",
            line=10,
            column=5
        )
    """
    if not check_lsp_available(host, port):
        return {
            "success": False,
            "error": f"Godot LSP not available at {host}:{port}. "
                     f"Make sure Godot Editor is open.",
            "completions": [],
        }
    
    client = GodotLSPClient(host, port)
    
    try:
        if not client.connect():
            return {
                "success": False,
                "error": "Failed to connect to LSP",
                "completions": [],
            }
        
        # Initialize
        client.initialize(project_path)
        
        # Get completions
        completions = client.get_completions(file_path, line, column)
        
        # Format results
        formatted = []
        for item in completions:
            formatted.append({
                "label": item.get("label", ""),
                "kind": item.get("kind", 0),
                "detail": item.get("detail", ""),
                "documentation": item.get("documentation", ""),
                "insertText": item.get("insertText", ""),
            })
        
        client.shutdown()
        
        return {
            "success": True,
            "completions": formatted,
            "count": len(formatted),
            "file_path": file_path,
            "line": line,
            "column": column,
        }
        
    except Exception as e:
        logger.error(f"LSP completion error: {e}")
        client.disconnect()
        return {
            "success": False,
            "error": str(e),
            "completions": [],
        }


def lsp_get_hover(
    project_path: str,
    file_path: str,
    line: int,
    column: int,
    host: str = "localhost",
    port: int = 6005,
) -> dict[str, Any]:
    """
    Get hover information (documentation) for a symbol at position.

    Args:
        project_path: Absolute path to the Godot project.
        file_path: Path to the GDScript file.
        line: Line number (0-based).
        column: Column number (0-based).
        host: LSP server host.
        port: LSP server port.

    Returns:
        Dict with hover info.

    Example:
        lsp_get_hover("D:/MyGame", "res://scripts/player.gd", 15, 8)
    """
    if not check_lsp_available(host, port):
        return {
            "success": False,
            "error": f"Godot LSP not available at {host}:{port}",
        }
    
    client = GodotLSPClient(host, port)
    
    try:
        if not client.connect():
            return {"success": False, "error": "Failed to connect to LSP"}
        
        client.initialize(project_path)
        
        hover = client.get_hover(file_path, line, column)
        
        client.shutdown()
        
        if hover:
            contents = hover.get("contents", {})
            if isinstance(contents, dict):
                documentation = contents.get("value", "")
            else:
                documentation = str(contents)
            
            return {
                "success": True,
                "documentation": documentation,
                "range": hover.get("range"),
                "file_path": file_path,
                "line": line,
                "column": column,
            }
        
        return {
            "success": True,
            "documentation": "",
            "message": "No hover information available",
        }
        
    except Exception as e:
        logger.error(f"LSP hover error: {e}")
        client.disconnect()
        return {"success": False, "error": str(e)}


def lsp_get_symbols(
    project_path: str,
    file_path: str,
    host: str = "localhost",
    port: int = 6005,
) -> dict[str, Any]:
    """
    Get all symbols (classes, methods, variables) in a GDScript file.

    Args:
        project_path: Absolute path to the Godot project.
        file_path: Path to the GDScript file.
        host: LSP server host.
        port: LSP server port.

    Returns:
        Dict with symbols list.

    Example:
        lsp_get_symbols("D:/MyGame", "res://scripts/player.gd")
    """
    if not check_lsp_available(host, port):
        return {
            "success": False,
            "error": f"Godot LSP not available at {host}:{port}",
            "symbols": [],
        }
    
    client = GodotLSPClient(host, port)
    
    try:
        if not client.connect():
            return {
                "success": False,
                "error": "Failed to connect to LSP",
                "symbols": [],
            }
        
        client.initialize(project_path)
        
        symbols = client.get_document_symbols(file_path)
        
        # Format results
        formatted = []
        for symbol in symbols:
            formatted.append({
                "name": symbol.get("name", ""),
                "kind": symbol.get("kind", 0),
                "detail": symbol.get("detail", ""),
                "range": symbol.get("range", {}),
                "selectionRange": symbol.get("selectionRange", {}),
            })
        
        client.shutdown()
        
        return {
            "success": True,
            "symbols": formatted,
            "count": len(formatted),
            "file_path": file_path,
        }
        
    except Exception as e:
        logger.error(f"LSP symbols error: {e}")
        client.disconnect()
        return {
            "success": False,
            "error": str(e),
            "symbols": [],
        }


def lsp_get_diagnostics(
    project_path: str,
    file_path: str,
    host: str = "localhost",
    port: int = 6005,
) -> dict[str, Any]:
    """
    Get diagnostics (errors and warnings) for a GDScript file.

    Args:
        project_path: Absolute path to the Godot project.
        file_path: Path to the GDScript file.
        host: LSP server host.
        port: LSP server port.

    Returns:
        Dict with diagnostics list.

    Example:
        lsp_get_diagnostics("D:/MyGame", "res://scripts/player.gd")
    """
    if not check_lsp_available(host, port):
        return {
            "success": False,
            "error": f"Godot LSP not available at {host}:{port}",
            "diagnostics": [],
        }
    
    client = GodotLSPClient(host, port)
    
    try:
        if not client.connect():
            return {
                "success": False,
                "error": "Failed to connect to LSP",
                "diagnostics": [],
            }
        
        client.initialize(project_path)
        
        # Open document to trigger diagnostics
        diagnostics = client.get_diagnostics(file_path)
        
        client.shutdown()
        
        formatted = []
        for diag in diagnostics:
            formatted.append({
                "severity": diag.get("severity", 1),  # 1=Error, 2=Warning, 3=Info, 4=Hint
                "message": diag.get("message", ""),
                "range": diag.get("range", {}),
                "code": diag.get("code"),
                "source": diag.get("source", ""),
            })
        
        return {
            "success": True,
            "diagnostics": formatted,
            "count": len(formatted),
            "file_path": file_path,
        }
        
    except Exception as e:
        logger.error(f"LSP diagnostics error: {e}")
        client.disconnect()
        return {
            "success": False,
            "error": str(e),
            "diagnostics": [],
        }


# ==================== REGISTRATION ====================


def register_lsp_tools(mcp) -> None:
    """Register all LSP tools."""
    logger.info("Registrando LSP tools...")
    
    mcp.add_tool(lsp_get_completions)
    mcp.add_tool(lsp_get_hover)
    mcp.add_tool(lsp_get_symbols)
    mcp.add_tool(lsp_get_diagnostics)
    
    logger.info("[OK] 4 LSP tools registradas")
