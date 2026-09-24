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
    instructions=f"This is {settings.server_name} - a robust MCP server with comprehensive tooling for AI applications.",
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
