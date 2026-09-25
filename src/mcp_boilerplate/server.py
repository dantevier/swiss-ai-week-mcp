"""
Main MCP server implementation using FastMCP v2.
"""

import asyncio
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .config.settings import settings
from .utils.logger import setup_logger

# Initialize the logger
logger = setup_logger("mcp_boilerplate.server")


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Build the local SQLite data (housing, driving licence) before serving requests."""
    from .local_databases import build_local_databases

    await asyncio.to_thread(build_local_databases)
    yield


# Create the main MCP server instance
mcp = FastMCP(
    name=settings.server_name,
    instructions=(
        "Answers Swiss public-service questions grounded in official sources. "
        "Use company_info for companies in the federal commercial register (Zefix) "
        "and their SHAB publications. Use swiss_health_insurance_premiums for 2026 "
        "KVG minimum premiums by age, municipality and deductible. Use "
        "search_knowledge and get_source for the reviewed authority pages on health "
        "insurance, the reference interest rate, foreign driving licences, school "
        "holidays, waste and arrival registration. Every tool asks back when input "
        "is ambiguous and says when a source is unavailable."
    ),
    lifespan=lifespan,
)

# Import all components to register them with the mcp instance
from .tools import *  # This will register all tools

logger.info(f"Initialized FastMCP server: {settings.server_name}")


def main():
    """Run the MCP server."""
    try:
        logger.info("Starting MCP Server...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        raise
    finally:
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    main()
