"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server.
"""

# Import all tool modules - the decorators will register them automatically
from . import math_tools
from . import text_tools
from . import utility_tools

# Export the tool modules for potential external use
__all__ = ['math_tools', 'text_tools', 'utility_tools']