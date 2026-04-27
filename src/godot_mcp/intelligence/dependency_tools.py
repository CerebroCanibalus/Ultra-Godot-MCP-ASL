"""
Dependency Tools - Análisis de dependencias entre archivos del proyecto.

Construye grafos de dependencias y encuentra assets no usados
mediante análisis estático de archivos .tscn, .gd, .tres
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Extensiones de assets por tipo
ASSET_EXTENSIONS = {
    "texture": [".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".tga"],
    "audio": [".ogg", ".wav", ".mp3"],
    "model": [".glb", ".gltf", ".obj", ".fbx"],
    "font": [".ttf", ".otf", ".fnt"],
    "shader": [".gdshader", ".shader"],
    "animation": [".anim", ".gltf"],
    "resource": [".tres"],
    "scene": [".tscn", ".scn"],
    "script": [".gd", ".cs", ".c#"],
}


def _get_all_project_files(project_path: str) -> Dict[str, List[str]]:
    """Obtiene todos los archivos del proyecto organizados por tipo."""
    files_by_type = {t: [] for t in ASSET_EXTENSIONS}
    files_by_type["other"] = []
    
    project = Path(project_path)
    
    for file_path in project.rglob("*"):
        if not file_path.is_file():
            continue
        
        # Ignorar carpetas de sistema
        if any(part.startswith(".") for part in file_path.relative_to(project).parts):
            continue
        
        ext = file_path.suffix.lower()
        
        found = False
        for asset_type, extensions in ASSET_EXTENSIONS.items():
            if ext in extensions:
                files_by_type[asset_type].append(str(file_path))
                found = True
                break
        
        if not found:
            files_by_type["other"].append(str(file_path))
    
    return files_by_type


def _extract_references_from_tscn(tscn_path: str) -> Set[str]:
    """Extrae todas las referencias res:// de un archivo .tscn."""
    references = set()
    
    try:
        content = Path(tscn_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {tscn_path}: {e}")
        return references
    
    # Patrones de referencia en TSCN
    patterns = [
        r'path="(res://[^"]+)"',  # ext_resource path
        r'="(res://[^"]+)"',  # propiedades con res://
        r'load\("(res://[^"]+)"\)',  # load() calls en propiedades
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            ref = match.group(1)
            references.add(ref)
    
    return references


def _extract_references_from_gd(gd_path: str) -> Set[str]:
    """Extrae todas las referencias res:// de un script GDScript."""
    references = set()
    
    try:
        content = Path(gd_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {gd_path}: {e}")
        return references
    
    # Patrones de referencia en GDScript
    patterns = [
        r'load\("(res://[^"]+)"\)',
        r'preload\("(res://[^"]+)"\)',
        r'extends\s+"(res://[^"]+)"',
        r'ResourceLoader\.load\("(res://[^"]+)"\)',
        # Referencias en strings
        r'"(res://[^"]+)"',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            ref = match.group(1)
            references.add(ref)
    
    return references


def _extract_references_from_tres(tres_path: str) -> Set[str]:
    """Extrae referencias de un archivo .tres."""
    references = set()
    
    try:
        content = Path(tres_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {tres_path}: {e}")
        return references
    
    # Patrones similares a TSCN
    patterns = [
        r'path="(res://[^"]+)"',
        r'="(res://[^"]+)"',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            ref = match.group(1)
            references.add(ref)
    
    return references


def _resolve_reference(ref: str, project_path: str) -> Optional[str]:
    """Resuelve una referencia res:// a path absoluto."""
    if ref.startswith("res://"):
        rel_path = ref[6:]  # Quitar "res://"
        abs_path = os.path.join(project_path, rel_path)
        if os.path.exists(abs_path):
            return abs_path
    return None


def get_dependency_graph(
    project_path: str,
    file_path: Optional[str] = None,
    depth: int = 3,
) -> dict:
    """
    Construye un grafo de dependencias del proyecto.
    
    Analiza archivos .tscn, .gd, .tres para encontrar referencias
    entre archivos.
    
    Args:
        project_path: Ruta al proyecto Godot
        file_path: Archivo específico (None = todo el proyecto)
        depth: Profundidad máxima de dependencias
    
    Returns:
        Grafo con nodos y edges
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.isdir(project_path):
        return {"success": False, "error": f"Project not found: {project_path}"}
    
    nodes = []
    edges = []
    visited = set()
    
    def analyze_file(file_path: str, current_depth: int):
        """Analiza un archivo y sus dependencias recursivamente."""
        if current_depth > depth or file_path in visited:
            return
        
        visited.add(file_path)
        
        # Determinar tipo
        ext = Path(file_path).suffix.lower()
        file_type = "other"
        for asset_type, extensions in ASSET_EXTENSIONS.items():
            if ext in extensions:
                file_type = asset_type
                break
        
        rel_path = os.path.relpath(file_path, project_path)
        res_path = f"res://{rel_path.replace(os.sep, '/')}"
        
        nodes.append({
            "id": res_path,
            "path": file_path,
            "type": file_type,
            "name": Path(file_path).name,
        })
        
        # Extraer referencias según tipo
        references = set()
        if ext == ".tscn":
            references = _extract_references_from_tscn(file_path)
        elif ext == ".gd":
            references = _extract_references_from_gd(file_path)
        elif ext == ".tres":
            references = _extract_references_from_tres(file_path)
        
        # Resolver y agregar edges
        for ref in references:
            resolved = _resolve_reference(ref, project_path)
            if resolved and os.path.exists(resolved):
                edges.append({
                    "from": res_path,
                    "to": ref,
                    "type": "reference",
                })
                
                # Recursión
                analyze_file(resolved, current_depth + 1)
    
    # Analizar
    if file_path:
        abs_path = os.path.join(project_path, file_path.replace("res://", "").replace("/", os.sep))
        if os.path.exists(abs_path):
            analyze_file(abs_path, 0)
    else:
        # Analizar todo el proyecto
        files = _get_all_project_files(project_path)
        for file_list in files.values():
            for f in file_list:
                analyze_file(f, 0)
    
    return {
        "success": True,
        "project_path": project_path,
        "file_path": file_path,
        "depth": depth,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def find_unused_assets(
    project_path: str,
    asset_types: Optional[List[str]] = None,
) -> dict:
    """
    Encuentra assets que no son referenciados por ninguna escena o script.
    
    Args:
        project_path: Ruta al proyecto Godot
        asset_types: Tipos de assets a verificar (None = todos)
    
    Returns:
        Lista de assets no usados
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.isdir(project_path):
        return {"success": False, "error": f"Project not found: {project_path}"}
    
    # Obtener todos los assets
    all_files = _get_all_project_files(project_path)
    
    # Filtrar por tipo si se especifica
    if asset_types:
        assets_to_check = {}
        for t in asset_types:
            if t in all_files:
                assets_to_check[t] = all_files[t]
    else:
        assets_to_check = {k: v for k, v in all_files.items() 
                          if k not in ["script", "scene"]}
    
    # Obtener todas las referencias
    all_references = set()
    
    # Analizar escenas
    for scene_path in all_files.get("scene", []):
        refs = _extract_references_from_tscn(scene_path)
        all_references.update(refs)
    
    # Analizar scripts
    for script_path in all_files.get("script", []):
        refs = _extract_references_from_gd(script_path)
        all_references.update(refs)
    
    # Analizar recursos
    for tres_path in all_files.get("resource", []):
        refs = _extract_references_from_tres(tres_path)
        all_references.update(refs)
    
    # Encontrar no referenciados
    unused = []
    
    for asset_type, files in assets_to_check.items():
        for file_path in files:
            rel_path = os.path.relpath(file_path, project_path)
            res_path = f"res://{rel_path.replace(os.sep, '/')}"
            
            # Verificar si está referenciado
            is_referenced = False
            for ref in all_references:
                if res_path in ref or ref in res_path:
                    is_referenced = True
                    break
            
            if not is_referenced:
                unused.append({
                    "path": res_path,
                    "absolute_path": file_path,
                    "type": asset_type,
                    "size_bytes": os.path.getsize(file_path),
                })
    
    # Calcular espacio total
    total_size = sum(u["size_bytes"] for u in unused)
    
    return {
        "success": True,
        "project_path": project_path,
        "unused_count": len(unused),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "unused_assets": unused,
    }


def register_dependency_tools(mcp) -> None:
    """Register dependency analysis tools."""
    logger.info("Registrando dependency tools...")
    
    mcp.add_tool(get_dependency_graph)
    mcp.add_tool(find_unused_assets)
    
    logger.info("[OK] 2 dependency tools registradas")
