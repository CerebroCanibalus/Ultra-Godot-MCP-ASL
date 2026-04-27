"""
Godot MCP Server - Ultra-fast MCP server for Godot Engine.

Entry point del servidor MCP usando FastMCP.
"""

import logging
import sys
from typing import Optional

from fastmcp import FastMCP

# Importar y registrar todas las herramientas desde tools/
from .tools.scene_tools import register_scene_tools
from .tools.node_tools import register_node_tools
from .tools.resource_tools import register_resource_tools
from .tools.session_tools import register_session_tools
from .tools.project_tools import register_project_tools
from .tools.validation_tools import register_validation_tools
from .tools.signal_and_script_tools import register_signal_and_script_tools
from .tools.property_tools import register_property_tools
from .tools.debug_tools import register_debug_tools
# Capa 2: Godot CLI Bridge (v4.0.0)
from .godot_cli.export_tools import register_export_tools
from .godot_cli.runtime_tools import register_runtime_tools
from .godot_cli.import_tools import register_import_tools
from .godot_cli.screenshot_tools import register_screenshot_tools
from .godot_cli.movie_tools import register_movie_tools
# Capa 3: LSP/DAP Native (v4.0.0)
from .lsp_dap.lsp_tools import register_lsp_tools
from .lsp_dap.dap_tools import register_dap_tools
# Capa 4: Project Intelligence (v4.0.0)
from .intelligence.dependency_tools import register_dependency_tools
from .intelligence.signal_graph_tools import register_signal_graph_tools
from .intelligence.code_analysis_tools import register_code_analysis_tools
# Capa 5: Skeleton Tools (v4.1.0)
from .tools.skeleton_tools import register_skeleton_tools
# Capa 6: Array Operations (v4.2.0)
from .tools.array_tools import register_array_tools
# Capa 7: Resource Builder (v4.3.0)
from .tools.resource_builder_tools import register_resource_builder_tools

# Inicializar FastMCP con nombre "godot-mcp"
mcp = FastMCP("godot-mcp")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# Registrar todas las herramientas
def register_all_tools() -> None:
    """Registrar todas las herramientas disponibles en el servidor MCP."""
    logger.info("Registrando herramientas del servidor MCP...")

    try:
        register_scene_tools(mcp)
        logger.info("[OK] Scene tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar scene_tools: {e}")
        raise

    try:
        register_node_tools(mcp)
        logger.info("[OK] Node tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar node_tools: {e}")
        raise

    try:
        register_resource_tools(mcp)
        logger.info("[OK] Resource tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar resource_tools: {e}")
        raise

    try:
        register_session_tools(mcp)
        logger.info("[OK] Session tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar session_tools: {e}")
        raise

    try:
        register_project_tools(mcp)
        logger.info("[OK] Project tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar project_tools: {e}")
        raise

    try:
        register_validation_tools(mcp)
        logger.info("[OK] Validation tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar validation_tools: {e}")
        raise

    try:
        register_signal_and_script_tools(mcp)
        logger.info("[OK] Signal & script tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar signal_and_script_tools: {e}")
        raise

    try:
        register_property_tools(mcp)
        logger.info("[OK] Property tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar property_tools: {e}")
        raise

    try:
        register_debug_tools(mcp)
        logger.info("[OK] Debug tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar debug_tools: {e}")
        raise

    # Capa 2: Godot CLI Bridge
    try:
        register_export_tools(mcp)
        logger.info("[OK] Export tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar export_tools: {e}")
        raise

    try:
        register_runtime_tools(mcp)
        logger.info("[OK] Runtime tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar runtime_tools: {e}")
        raise

    try:
        register_import_tools(mcp)
        logger.info("[OK] Import tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar import_tools: {e}")
        raise

    try:
        register_screenshot_tools(mcp)
        logger.info("[OK] Screenshot tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar screenshot_tools: {e}")
        raise

    try:
        register_movie_tools(mcp)
        logger.info("[OK] Movie tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar movie_tools: {e}")
        raise

    # Capa 3: LSP/DAP
    try:
        register_lsp_tools(mcp)
        logger.info("[OK] LSP tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar lsp_tools: {e}")
        raise

    try:
        register_dap_tools(mcp)
        logger.info("[OK] DAP tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar dap_tools: {e}")
        raise

    # Capa 4: Project Intelligence
    try:
        register_dependency_tools(mcp)
        logger.info("[OK] Dependency tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar dependency_tools: {e}")
        raise

    try:
        register_signal_graph_tools(mcp)
        logger.info("[OK] Signal graph tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar signal_graph_tools: {e}")
        raise

    try:
        register_code_analysis_tools(mcp)
        logger.info("[OK] Code analysis tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar code_analysis_tools: {e}")
        raise

    # Capa 5: Skeleton
    try:
        register_skeleton_tools(mcp)
        logger.info("[OK] Skeleton tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar skeleton_tools: {e}")
        raise

    # Capa 6: Array Operations
    try:
        register_array_tools(mcp)
        logger.info("[OK] Array tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar array_tools: {e}")
        raise

    # Capa 7: Resource Builder
    try:
        register_resource_builder_tools(mcp)
        logger.info("[OK] Resource builder tools registradas")
    except Exception as e:
        logger.error(f"Error al registrar resource_builder_tools: {e}")
        raise

    logger.info("Todas las herramientas registradas correctamente")


def main(transport: Optional[str] = None) -> None:
    """
    Punto de entrada principal del servidor MCP.

    Args:
        transport: Tipo de transporte a usar (stdio, sse, etc.).
                  Si es None, usa el valor por defecto de FastMCP.
    """
    try:
        logger.info("Iniciando Ultra Godot MCP v3.1.0 - Plus Ultra...")

        # Registrar todas las herramientas
        register_all_tools()

        logger.info("Servidor MCP listo para aceptar conexiones")

        # Ejecutar el servidor
        mcp.run(transport=transport)

    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Error fatal al iniciar el servidor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
