"""
Signal Graph Tools - Análisis de señales en proyectos Godot.

Construye grafos de conexiones de señales y detecta señales huérfanas
mediante análisis estático de archivos .tscn y .gd
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _extract_connections_from_tscn(tscn_path: str) -> List[dict]:
    """Extrae conexiones de señales de un archivo .tscn."""
    connections = []
    
    try:
        content = Path(tscn_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {tscn_path}: {e}")
        return connections
    
    # Formato: [connection signal="name" from="NodePath" to="NodePath" method="method_name"]
    pattern = r'\[connection\s+signal="([^"]+)"\s+from="([^"]*)"\s+to="([^"]*)"\s+method="([^"]+)"'
    
    for match in re.finditer(pattern, content):
        connections.append({
            "signal": match.group(1),
            "from": match.group(2),
            "to": match.group(3),
            "method": match.group(4),
            "source_file": tscn_path,
        })
    
    return connections


def _extract_signals_from_gd(gd_path: str) -> Tuple[List[str], List[dict]]:
    """
    Extrae señales declaradas y conexiones dinámicas de un script GDScript.
    
    Returns:
        (signals_declared, connections_dynamic)
    """
    signals_declared = []
    connections_dynamic = []
    
    try:
        content = Path(gd_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {gd_path}: {e}")
        return signals_declared, connections_dynamic
    
    # Señales declaradas: signal name(params)
    signal_pattern = r'^\s*signal\s+(\w+)\s*\(([^)]*)\)'
    for match in re.finditer(signal_pattern, content, re.MULTILINE):
        signals_declared.append({
            "name": match.group(1),
            "params": match.group(2).strip(),
            "source_file": gd_path,
        })
    
    # Conexiones dinámicas: connect("signal", target, "method")
    connect_pattern = r'\.connect\s*\(\s*"([^"]+)"\s*,\s*([^,]+)\s*,\s*"([^"]+)"\s*\)'
    for match in re.finditer(connect_pattern, content):
        connections_dynamic.append({
            "signal": match.group(1),
            "target": match.group(2).strip(),
            "method": match.group(3),
            "source_file": gd_path,
            "type": "dynamic",
        })
    
    # Conexiones con Callable: connect("signal", callable(target, "method"))
    connect_callable_pattern = r'\.connect\s*\(\s*"([^"]+)"\s*,\s*Callable\s*\(\s*([^,]+)\s*,\s*"([^"]+)"\s*\)\s*\)'
    for match in re.finditer(connect_callable_pattern, content):
        connections_dynamic.append({
            "signal": match.group(1),
            "target": match.group(2).strip(),
            "method": match.group(3),
            "source_file": gd_path,
            "type": "dynamic_callable",
        })
    
    return signals_declared, connections_dynamic


def _extract_methods_from_gd(gd_path: str) -> Set[str]:
    """Extrae nombres de métodos de un script GDScript."""
    methods = set()
    
    try:
        content = Path(gd_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {gd_path}: {e}")
        return methods
    
    # Funciones: func name(params):
    func_pattern = r'^\s*func\s+(\w+)\s*\('
    for match in re.finditer(func_pattern, content, re.MULTILINE):
        methods.add(match.group(1))
    
    return methods


def _find_script_for_node(tscn_path: str, node_path: str) -> Optional[str]:
    """
    Encuentra el script asociado a un nodo en una escena.
    
    Args:
        tscn_path: Ruta al archivo .tscn
        node_path: Path del nodo (ej: "Player/Sprite2D")
    
    Returns:
        Ruta al script .gd o None
    """
    try:
        content = Path(tscn_path).read_text(encoding="utf-8")
    except Exception:
        return None
    
    # Buscar nodo
    node_name = node_path.split("/")[-1]
    
    # Patrón para encontrar el nodo y su script
    # [node name="NodeName" ...]
    # script = ExtResource("id")
    node_pattern = rf'\[node\s+name="{re.escape(node_name)}"[^\]]*\]'
    
    for match in re.finditer(node_pattern, content):
        start = match.end()
        # Buscar script en las siguientes líneas
        lines_after = content[start:start + 500]
        script_match = re.search(r'script\s*=\s*ExtResource\("([^"]+)"\)', lines_after)
        if script_match:
            ext_id = script_match.group(1)
            # Buscar el ext_resource correspondiente
            ext_pattern = rf'\[ext_resource\s+[^\]]*id="{ext_id}"[^\]]*\]'
            for ext_match in re.finditer(ext_pattern, content):
                path_match = re.search(r'path="([^"]+)"', ext_match.group(0))
                if path_match:
                    return path_match.group(1)
    
    return None


def get_signal_graph(
    project_path: str,
    scene_path: Optional[str] = None,
) -> dict:
    """
    Construye un grafo de señales del proyecto.
    
    Analiza conexiones estáticas (en .tscn) y dinámicas (en .gd).
    
    Args:
        project_path: Ruta al proyecto Godot
        scene_path: Escena específica (None = todo el proyecto)
    
    Returns:
        Grafo de señales con emisores, receptores y métodos
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.isdir(project_path):
        return {"success": False, "error": f"Project not found: {project_path}"}
    
    signals = []
    signals_declared = []
    connections_dynamic = []
    
    # Encontrar archivos a analizar
    if scene_path:
        abs_scene = os.path.join(project_path, scene_path.replace("res://", "").replace("/", os.sep))
        tscn_files = [abs_scene] if os.path.exists(abs_scene) and abs_scene.endswith(".tscn") else []
    else:
        tscn_files = list(Path(project_path).rglob("*.tscn"))
        tscn_files = [str(f) for f in tscn_files if not any(p.startswith(".") for p in f.relative_to(project_path).parts)]
    
    # Analizar conexiones estáticas en .tscn
    for tscn_file in tscn_files:
        rel_path = os.path.relpath(tscn_file, project_path)
        res_path = f"res://{rel_path.replace(os.sep, '/')}"
        
        connections = _extract_connections_from_tscn(tscn_file)
        for conn in connections:
            signals.append({
                "emitter": f"{res_path}:{conn['from']}" if conn['from'] else res_path,
                "signal": conn["signal"],
                "receiver": f"{res_path}:{conn['to']}" if conn['to'] else res_path,
                "method": conn["method"],
                "type": "static",
                "source_file": res_path,
            })
    
    # Analizar scripts
    gd_files = list(Path(project_path).rglob("*.gd"))
    gd_files = [f for f in gd_files if not any(p.startswith(".") for p in f.relative_to(project_path).parts)]
    
    for gd_file in gd_files:
        rel_path = os.path.relpath(gd_file, project_path)
        res_path = f"res://{rel_path.replace(os.sep, '/')}"
        
        declared, dynamic = _extract_signals_from_gd(str(gd_file))
        
        for sig in declared:
            sig["source_file"] = res_path
            signals_declared.append(sig)
        
        for conn in dynamic:
            conn["source_file"] = res_path
            connections_dynamic.append(conn)
            
            signals.append({
                "emitter": res_path,
                "signal": conn["signal"],
                "receiver": conn["target"],
                "method": conn["method"],
                "type": conn["type"],
                "source_file": res_path,
            })
    
    return {
        "success": True,
        "project_path": project_path,
        "scene_path": scene_path,
        "signals": signals,
        "signals_declared": signals_declared,
        "connections_dynamic": connections_dynamic,
        "signal_count": len(signals),
        "declared_count": len(signals_declared),
        "dynamic_count": len(connections_dynamic),
    }


def find_orphan_signals(project_path: str) -> dict:
    """
    Encuentra señales conectadas a métodos que no existen.
    
    Args:
        project_path: Ruta al proyecto Godot
    
    Returns:
        Lista de señales huérfanas
    """
    project_path = os.path.abspath(project_path)
    
    if not os.path.isdir(project_path):
        return {"success": False, "error": f"Project not found: {project_path}"}
    
    # Obtener grafo de señales
    graph = get_signal_graph(project_path)
    if not graph["success"]:
        return graph
    
    # Indexar todos los métodos por archivo
    methods_by_file = {}
    
    gd_files = list(Path(project_path).rglob("*.gd"))
    gd_files = [f for f in gd_files if not any(p.startswith(".") for p in f.relative_to(project_path).parts)]
    
    for gd_file in gd_files:
        rel_path = os.path.relpath(gd_file, project_path)
        res_path = f"res://{rel_path.replace(os.sep, '/')}"
        methods = _extract_methods_from_gd(str(gd_file))
        methods_by_file[res_path] = methods
    
    # Verificar cada conexión
    orphan_signals = []
    
    for signal in graph["signals"]:
        if signal["type"] == "static":
            # Para conexiones estáticas, verificar si el método existe
            # en el script del nodo receptor
            receiver = signal["receiver"]
            method = signal["method"]
            
            # Extraer archivo de escena del receptor
            if ":" in receiver:
                scene_file = receiver.split(":")[0]
                node_path = receiver.split(":")[1]
            else:
                scene_file = receiver
                node_path = "."
            
            # Buscar script del nodo receptor
            abs_scene = os.path.join(project_path, scene_file.replace("res://", "").replace("/", os.sep))
            script_path = _find_script_for_node(abs_scene, node_path)
            
            if script_path:
                # Verificar si el método existe
                if script_path not in methods_by_file:
                    # Script no analizado, intentar leer directamente
                    abs_script = os.path.join(project_path, script_path.replace("res://", "").replace("/", os.sep))
                    if os.path.exists(abs_script):
                        methods_by_file[script_path] = _extract_methods_from_gd(abs_script)
                
                if script_path in methods_by_file:
                    if method not in methods_by_file[script_path]:
                        orphan_signals.append({
                            "signal": signal["signal"],
                            "receiver": receiver,
                            "method": method,
                            "source_file": signal["source_file"],
                            "reason": f"Method '{method}' not found in script {script_path}",
                        })
            else:
                # No se encontró script, podría ser un nodo built-in
                # Verificar métodos built-in comunes
                builtin_methods = {
                    "_ready", "_process", "_physics_process",
                    "_input", "_unhandled_input", "_draw",
                    "_on_body_entered", "_on_body_exited",
                    "_on_area_entered", "_on_area_exited",
                    "_on_pressed", "_on_toggled",
                }
                if method not in builtin_methods and not method.startswith("_on_"):
                    orphan_signals.append({
                        "signal": signal["signal"],
                        "receiver": receiver,
                        "method": method,
                        "source_file": signal["source_file"],
                        "reason": "No script found for receiver node",
                    })
    
    return {
        "success": True,
        "project_path": project_path,
        "orphan_count": len(orphan_signals),
        "orphan_signals": orphan_signals,
        "total_signals": len(graph["signals"]),
    }


def register_signal_graph_tools(mcp) -> None:
    """Register signal graph analysis tools."""
    logger.info("Registrando signal graph tools...")
    
    mcp.add_tool(get_signal_graph)
    mcp.add_tool(find_orphan_signals)
    
    logger.info("[OK] 2 signal graph tools registradas")
