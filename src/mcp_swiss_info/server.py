"""
Main MCP server implementation using FastMCP v2.
"""

import asyncio
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .config.settings import settings
from .utils.logger import setup_logger

# Initialize the logger
logger = setup_logger("mcp_swiss_info.server")


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
        "Choose the most specific tool for the question first: company_info for Zefix "
        "companies and SHAB publications; swiss_health_insurance_premiums for 2026 "
        "KVG premiums; swiss_geo_search and swiss_geo_context for places and municipality "
        "codes; swiss_reference_interest_rate and swiss_housing_info for renting; "
        "get_driving_licence_exchange_info for foreign licence exchange; "
        "swiss_school_holidays for school holidays; swiss_residence_permit_guidance "
        "for migration; swiss_federal_political_rights for federal political rules; "
        "swiss_import_parcel_vat for parcel import VAT; bfs_population for population; "
        "opendata_search_datasets and opendata_dataset for open-data catalogues; "
        "swiss_weather_forecast and swiss_weather_observations for weather. "
        "Use search_knowledge only as a last resort when no specific tool covers the "
        "question or the relevant specific tools return no applicable result. Use "
        "get_source only to inspect a saved source when more context is needed. "
        "Check tool results for dates, scope and conditions; ask for missing details "
        "rather than guessing, and say when reliable source data is unavailable."
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
