"""
Prompts module for the mcp-swiss-info server.

Import all prompt modules to register them with the MCP server.
"""

# Import all prompt modules - the decorators will register them automatically
from . import analysis_prompts
from . import assistant_prompts

# Export the prompt modules for potential external use
__all__ = ['analysis_prompts', 'assistant_prompts']