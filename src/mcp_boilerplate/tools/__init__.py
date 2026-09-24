"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server.
"""

# Import all tool modules - the decorators will register them automatically
from . import source_tools

# Export the tool modules for potential external use
__all__ = ["source_tools"]
