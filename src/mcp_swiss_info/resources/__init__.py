"""
Resources module for the mcp-swiss-info server.

Import all resource modules to register them with the MCP server.
"""

# Import all resource modules - the decorators will register them automatically
from . import data_resources
from . import system_resources

# Export the resource modules for potential external use
__all__ = ['data_resources', 'system_resources']