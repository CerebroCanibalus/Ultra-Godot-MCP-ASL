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

    logger.info("Todas las herramientas registradas correctamente")


def main(transport: Optional[str] = None) -> None:
    """
    Punto de entrada principal del servidor MCP.

    Args:
        transport: Tipo de transporte a usar (stdio, sse, etc.).
                  Si es None, usa el valor por defecto de FastMCP.
    """
    try:
        logger.info("Iniciando Godot MCP Server v2.0.0...")

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
