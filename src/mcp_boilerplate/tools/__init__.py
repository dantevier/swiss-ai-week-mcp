"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server.
"""

# Import all tool modules - the decorators will register them automatically
from . import health_insurance_tools, math_tools, tax_tools, text_tools, utility_tools

# Export the tool modules for potential external use
__all__ = ['math_tools', 'text_tools', 'utility_tools', 'tax_tools', 'health_insurance_tools']
