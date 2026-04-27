"""
Project Intelligence - Análisis estático de proyectos Godot.

Provee herramientas para analizar dependencias, señales y código
sin ejecutar el proyecto.
"""

from .dependency_tools import (
    get_dependency_graph,
    find_unused_assets,
    register_dependency_tools,
)
from .signal_graph_tools import (
    get_signal_graph,
    find_orphan_signals,
    register_signal_graph_tools,
)
from .code_analysis_tools import (
    analyze_script,
    find_code_smells,
    get_project_metrics,
    register_code_analysis_tools,
)

__all__ = [
    "get_dependency_graph",
    "find_unused_assets",
    "get_signal_graph",
    "find_orphan_signals",
    "analyze_script",
    "find_code_smells",
    "get_project_metrics",
    "register_dependency_tools",
    "register_signal_graph_tools",
    "register_code_analysis_tools",
]
