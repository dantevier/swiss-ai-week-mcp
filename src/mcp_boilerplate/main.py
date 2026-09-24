"""
Main entry point for the MCP server using FastMCP v2.
"""

import sys
from .config.settings import settings
from .server import main as server_main
from .utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.main")


def main() -> None:
    """
    Main entry point for the CLI.
    """
    import argparse

    parser = argparse.ArgumentParser(description="MCP Boilerplate Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set log level",
    )
    parser.add_argument("--name", type=str, help="Custom server name (default: from settings)")
    parser.add_argument("--transport", type=str, choices=["stdio", "sse"], 
                       default="stdio", help="Transport protocol (default: stdio)")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")

    args = parser.parse_args()

    # Override settings if provided
    if args.debug:
        settings.enable_debug = True
        settings.log_level = "DEBUG"

    if args.log_level:
        settings.log_level = args.log_level

    if args.name:
        settings.server_name = args.name

    # Update the server name if provided
    if args.name:
        from .server import mcp
        mcp.name = args.name

    # Run the server
    try:
        if args.transport == "sse":
            # For SSE transport, we need to import and use the run method with transport
            from .server import mcp
            mcp.run(transport="sse", port=args.port)
        else:
            # For stdio (default), use the main function
            server_main()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()