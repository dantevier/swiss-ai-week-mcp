#!/usr/bin/env python3
"""
Inspector entry point for the MCP server.
This module provides a standalone entry point for FastMCP CLI to avoid relative import issues.
"""

import sys
import os

# Add the src directory to the path to allow absolute imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from mcp_boilerplate.server import mcp

# Set debug mode via environment variable if needed
if os.getenv('DEBUG') == '1':
    import logging
    logging.basicConfig(level=logging.DEBUG)

# Export the mcp instance for fastmcp CLI
app = mcp

if __name__ == "__main__":
    # This allows the module to be run directly as well
    mcp.run()