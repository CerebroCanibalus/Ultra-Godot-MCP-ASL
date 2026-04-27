"""
Code Analysis Tools - Análisis estático de código GDScript.

Provee métricas de complejidad, detección de code smells y
análisis de calidad de código sin ejecutar.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Métricas de complejidad
MAX_FUNCTION_LINES = 50
MAX_CLASS_LINES = 300
MAX_FUNCTION_COMPLEXITY = 15
MAX_NESTING_DEPTH = 4


def _count_lines(content: str) -> int:
    """Cuenta líneas no vacías ni comentarios."""
    lines = content.split("\n")
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _analyze_function_complexity(func_content: str) -> dict:
    """Analiza complejidad ciclomática de una función."""
    complexity = 1  # Base
    nesting_depth = 0
    max_nesting = 0
    
    lines = func_content.split("\n")
    
    for line in lines:
        stripped = line.strip()
        
        # Incrementar complejidad por estructuras de control
        if any(keyword in stripped for keyword in ["if ", "elif ", "else:", "match "]):
            complexity += 1
        if any(keyword in stripped for keyword in ["for ", "while "]):
            complexity += 1
        if "and " in stripped or " or " in stripped:
            complexity += stripped.count(" and ") + stripped.count(" or ")
        
        # Calcular nesting depth
        indent = len(line) - len(line.lstrip())
        current_depth = indent // 4  # Asumiendo 4 espacios
        max_nesting = max(max_nesting, current_depth)
    
    return {
        "cyclomatic": complexity,
        "max_nesting": max_nesting,
        "lines": len(lines),
    }


def _extract_functions(content: str) -> List[dict]:
    """Extrae funciones de un script GDScript."""
    functions = []
    
    # Patrón: func name(params):
    func_pattern = r'^(\s*)func\s+(\w+)\s*\(([^)]*)\):\s*$'
    
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        match = re.match(func_pattern, lines[i])
        if match:
            indent = len(match.group(1))
            func_name = match.group(2)
            params = match.group(3).strip()
            
            # Encontrar fin de función
            start_line = i
            i += 1
            func_lines = []
            
            while i < len(lines):
                line = lines[i]
                if line.strip() == "":
                    func_lines.append(line)
                    i += 1
                    continue
                
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= indent and line.strip():
                    # Fin de función
                    break
                
                func_lines.append(line)
                i += 1
            
            func_content = "\n".join(func_lines)
            complexity = _analyze_function_complexity(func_content)
            
            functions.append({
                "name": func_name,
                "params": params,
                "line_start": start_line + 1,
                "line_end": start_line + len(func_lines) + 1,
                "lines": complexity["lines"],
                "complexity": complexity["cyclomatic"],
                "max_nesting": complexity["max_nesting"],
            })
        else:
            i += 1
    
    return functions


def _extract_classes(content: str) -> List[dict]:
    """Extrae clases de un script GDScript."""
    classes = []
    
    # class_name MyClass
    class_name_pattern = r'^class_name\s+(\w+)'
    match = re.search(class_name_pattern, content, re.MULTILINE)
    class_name = match.group(1) if match else None
    
    # extends BaseClass o extends "res://path"
    extends_pattern = r'^extends\s+(\w+|"[^"]+")'
    match = re.search(extends_pattern, content, re.MULTILINE)
    extends = match.group(1).strip('"') if match else "RefCounted"
    
    # Señales
    signals = []
    signal_pattern = r'^\s*signal\s+(\w+)\s*\(([^)]*)\)'
    for match in re.finditer(signal_pattern, content, re.MULTILINE):
        signals.append({
            "name": match.group(1),
            "params": match.group(2).strip(),
        })
    
    # @export variables
    exports = []
    export_pattern = r'^\s*@export\s+\n?\s*(?:@\w+\s+)*\n?\s*var\s+(\w+)\s*:\s*(\w+)'
    for match in re.finditer(export_pattern, content, re.MULTILINE):
        exports.append({
            "name": match.group(1),
            "type": match.group(2),
        })
    
    # @onready variables
    onready = []
    onready_pattern = r'^\s*@onready\s+\n?\s*var\s+(\w+)'
    for match in re.finditer(onready_pattern, content, re.MULTILINE):
        onready.append(match.group(1))
    
    classes.append({
        "name": class_name or "Anonymous",
        "extends": extends,
        "signals": signals,
        "exports": exports,
        "onready_vars": onready,
    })
    
    return classes


def _find_code_smells_in_file(file_path: str, content: str) -> List[dict]:
    """Encuentra code smells en un archivo GDScript."""
    smells = []
    lines = content.split("\n")
    
    # 1. Funciones muy largas
    functions = _extract_functions(content)
    for func in functions:
        if func["lines"] > MAX_FUNCTION_LINES:
            smells.append({
                "line": func["line_start"],
                "severity": "warning",
                "type": "long_function",
                "message": f"Function '{func['name']}' is too long ({func['lines']} lines, max {MAX_FUNCTION_LINES})",
                "suggestion": "Consider splitting into smaller functions",
            })
        
        if func["complexity"] > MAX_FUNCTION_COMPLEXITY:
            smells.append({
                "line": func["line_start"],
                "severity": "warning",
                "type": "high_complexity",
                "message": f"Function '{func['name']}' has high complexity ({func['complexity']})",
                "suggestion": "Simplify control flow or extract helper functions",
            })
        
        if func["max_nesting"] > MAX_NESTING_DEPTH:
            smells.append({
                "line": func["line_start"],
                "severity": "info",
                "type": "deep_nesting",
                "message": f"Function '{func['name']}' has deep nesting (depth {func['max_nesting']})",
                "suggestion": "Consider early returns or extracting nested logic",
            })
    
    # 2. Archivo muy largo
    total_lines = _count_lines(content)
    if total_lines > MAX_CLASS_LINES:
        smells.append({
            "line": 1,
            "severity": "warning",
            "type": "large_file",
            "message": f"File is very large ({total_lines} lines, max {MAX_CLASS_LINES})",
            "suggestion": "Consider splitting into multiple scripts or using composition",
        })
    
    # 3. Variables no usadas (básico)
    var_pattern = r'^\s*var\s+(\w+)'
    vars_declared = set()
    for match in re.finditer(var_pattern, content, re.MULTILINE):
        vars_declared.add(match.group(1))
    
    for var in vars_declared:
        # Contar usos (excluyendo declaración)
        uses = len(re.findall(rf'\b{re.escape(var)}\b', content)) - 1
        if uses == 0:
            smells.append({
                "line": 1,
                "severity": "info",
                "type": "unused_variable",
                "message": f"Variable '{var}' might be unused",
                "suggestion": "Remove if not needed",
            })
    
    # 4. Magic numbers
    magic_number_pattern = r'(?!")\b(\d{2,})\b(?!"|\d)'
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for match in re.finditer(magic_number_pattern, line):
            num = match.group(1)
            # Ignorar números comunes
            if num not in ["0", "1", "2", "10", "100", "1000"]:
                smells.append({
                    "line": i,
                    "severity": "info",
                    "type": "magic_number",
                    "message": f"Magic number {num} found",
                    "suggestion": "Consider using a named constant",
                })
    
    # 5. TODO/FIXME sin resolver
    todo_pattern = r'#\s*(TODO|FIXME|HACK|XXX)'
    for i, line in enumerate(lines, 1):
        match = re.search(todo_pattern, line, re.IGNORECASE)
        if match:
            smells.append({
                "line": i,
                "severity": "info",
                "type": "todo",
                "message": f"{match.group(1)} found: {line.strip()}",
                "suggestion": "Address or remove before release",
            })
    
    return smells


def analyze_script(
    project_path: str,
    script_path: str,
) -> dict:
    """
    Analiza un script GDScript en detalle.
    
    Args:
        project_path: Ruta al proyecto Godot
        script_path: Ruta al script (res:// o absoluta)
    
    Returns:
        Análisis completo del script
    """
    project_path = os.path.abspath(project_path)
    
    # Resolver path
    if script_path.startswith("res://"):
        abs_path = os.path.join(project_path, script_path[6:].replace("/", os.sep))
    else:
        abs_path = os.path.abspath(script_path)
    
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"Script not found: {abs_path}"}
    
    try:
        content = Path(abs_path).read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to read script: {e}"}
    
    # Extraer información
    classes = _extract_classes(content)
    functions = _extract_functions(content)
    smells = _find_code_smells_in_file(abs_path, content)
    
    # Calcular métricas
    total_lines = len(content.split("\n"))
    code_lines = _count_lines(content)
    
    avg_complexity = sum(f["complexity"] for f in functions) / len(functions) if functions else 0
    
    return {
        "success": True,
        "script_path": script_path,
        "absolute_path": abs_path,
        "metrics": {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "comment_lines": total_lines - code_lines,
            "function_count": len(functions),
            "class_count": len(classes),
            "avg_complexity": round(avg_complexity, 2),
            "max_complexity": max((f["complexity"] for f in functions), default=0),
        },
        "classes": classes,
        "functions": functions,
        "issues": smells,
        "issue_count": {
            "errors": len([s for s in smells if s["severity"] == "error"]),
            "warnings": len([s for s in smells if s["severity"] == "warning"]),
            "infos": len([s for s in smells if s["severity"] == "info"]),
        },
    }


def find_code_smells(
    project_path: str,
    severity: str = "warning",
) -> dict:
    """
    Encuentra code smells en todo el proyecto.
    
    Args:
        project_path: Ruta al proyecto Godot
        severity: Mínimo severity a reportar ("info", "warning", "error")
    
    Returns:
        Lista de code smells encontrados
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.isdir(project_path):
        return {"success": False, "error": f"Project not found: {project_path}"}
    
    severity_levels = {"info": 0, "warning": 1, "error": 2}
    min_level = severity_levels.get(severity, 1)
    
    all_smells = []
    files_analyzed = 0
    
    # Analizar todos los scripts GD
    gd_files = list(Path(project_path).rglob("*.gd"))
    gd_files = [f for f in gd_files if not any(p.startswith(".") for p in f.relative_to(project_path).parts)]
    
    for gd_file in gd_files:
        try:
            content = gd_file.read_text(encoding="utf-8")
            smells = _find_code_smells_in_file(str(gd_file), content)
            
            # Filtrar por severity
            filtered = [s for s in smells if severity_levels.get(s["severity"], 0) >= min_level]
            
            for smell in filtered:
                rel_path = os.path.relpath(gd_file, project_path)
                smell["file"] = f"res://{rel_path.replace(os.sep, '/')}"
                all_smells.append(smell)
            
            files_analyzed += 1
        except Exception as e:
            logger.warning(f"Failed to analyze {gd_file}: {e}")
    
    # Agrupar por tipo
    smells_by_type = {}
    for smell in all_smells:
        smell_type = smell["type"]
        if smell_type not in smells_by_type:
            smells_by_type[smell_type] = []
        smells_by_type[smell_type].append(smell)
    
    return {
        "success": True,
        "project_path": project_path,
        "files_analyzed": files_analyzed,
        "total_smells": len(all_smells),
        "smells_by_type": smells_by_type,
        "smells": all_smells,
        "summary": {
            "errors": len([s for s in all_smells if s["severity"] == "error"]),
            "warnings": len([s for s in all_smells if s["severity"] == "warning"]),
            "infos": len([s for s in all_smells if s["severity"] == "info"]),
        },
    }


def get_project_metrics(project_path: str) -> dict:
    """
    Obtiene métricas del proyecto completo.
    
    Args:
        project_path: Ruta al proyecto Godot
    
    Returns:
        Métricas agregadas del proyecto
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.isdir(project_path):
        return {"success": False, "error": f"Project not found: {project_path}"}
    
    # Contar archivos
    file_counts = {
        "scripts": 0,
        "scenes": 0,
        "resources": 0,
        "textures": 0,
        "audio": 0,
        "models": 0,
        "shaders": 0,
        "fonts": 0,
        "other": 0,
    }
    
    total_lines = 0
    total_code_lines = 0
    total_functions = 0
    total_classes = 0
    total_complexity = 0
    
    # Extensiones por tipo
    extensions = {
        "scripts": [".gd", ".cs"],
        "scenes": [".tscn", ".scn"],
        "resources": [".tres"],
        "textures": [".png", ".jpg", ".jpeg", ".webp", ".svg"],
        "audio": [".ogg", ".wav", ".mp3"],
        "models": [".glb", ".gltf", ".obj", ".fbx"],
        "shaders": [".gdshader", ".shader"],
        "fonts": [".ttf", ".otf", ".fnt"],
    }
    
    for file_path in Path(project_path).rglob("*"):
        if not file_path.is_file():
            continue
        if any(p.startswith(".") for p in file_path.relative_to(project_path).parts):
            continue
        
        ext = file_path.suffix.lower()
        
        # Clasificar
        found = False
        for file_type, exts in extensions.items():
            if ext in exts:
                file_counts[file_type] += 1
                found = True
                break
        if not found:
            file_counts["other"] += 1
        
        # Analizar scripts
        if ext == ".gd":
            try:
                content = file_path.read_text(encoding="utf-8")
                total_lines += len(content.split("\n"))
                total_code_lines += _count_lines(content)
                
                functions = _extract_functions(content)
                total_functions += len(functions)
                total_complexity += sum(f["complexity"] for f in functions)
                
                classes = _extract_classes(content)
                total_classes += len(classes)
            except Exception:
                pass
    
    total_files = sum(file_counts.values())
    avg_complexity = total_complexity / total_functions if total_functions > 0 else 0
    
    return {
        "success": True,
        "project_path": project_path,
        "files": file_counts,
        "total_files": total_files,
        "code_metrics": {
            "total_lines": total_lines,
            "code_lines": total_code_lines,
            "function_count": total_functions,
            "class_count": total_classes,
            "avg_complexity": round(avg_complexity, 2),
        },
    }


def register_code_analysis_tools(mcp) -> None:
    """Register code analysis tools."""
    logger.info("Registrando code analysis tools...")
    
    mcp.add_tool(analyze_script)
    mcp.add_tool(find_code_smells)
    mcp.add_tool(get_project_metrics)
    
    logger.info("[OK] 3 code analysis tools registradas")
