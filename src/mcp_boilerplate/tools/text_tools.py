"""
Text processing tools for the MCP Boilerplate server.
"""

import re

from ..server import mcp
from ..utils.logger import setup_logger
from ..utils.validation import sanitize_input

logger = setup_logger("mcp_boilerplate.tools.text")


@mcp.tool
def text_length(text: str) -> int:
    """Get the length of a text string."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        result = len(sanitized_text)
        logger.debug(f"Text length: {result} characters")
        return result
    except Exception as e:
        logger.error(f"Error in text_length tool: {e}")
        raise


@mcp.tool
def text_uppercase(text: str) -> str:
    """Convert text to uppercase."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        result = sanitized_text.upper()
        logger.debug("Text converted to uppercase")
        return result
    except Exception as e:
        logger.error(f"Error in text_uppercase tool: {e}")
        raise


@mcp.tool
def text_lowercase(text: str) -> str:
    """Convert text to lowercase."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        result = sanitized_text.lower()
        logger.debug("Text converted to lowercase")
        return result
    except Exception as e:
        logger.error(f"Error in text_lowercase tool: {e}")
        raise


@mcp.tool
def text_reverse(text: str) -> str:
    """Reverse the order of characters in text."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        result = sanitized_text[::-1]
        logger.debug("Text reversed")
        return result
    except Exception as e:
        logger.error(f"Error in text_reverse tool: {e}")
        raise


@mcp.tool
def word_count(text: str) -> int:
    """Count the number of words in text."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        words = sanitized_text.split()
        result = len(words)
        logger.debug(f"Word count: {result} words")
        return result
    except Exception as e:
        logger.error(f"Error in word_count tool: {e}")
        raise


@mcp.tool
def extract_words(text: str, min_length: int = 1) -> list[str]:
    """Extract words from text with optional minimum length filter."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        # Extract words using regex
        words = re.findall(r"\b\w+\b", sanitized_text)
        # Filter by minimum length
        result = [word for word in words if len(word) >= min_length]
        logger.debug(f"Extracted {len(result)} words with min length {min_length}")
        return result
    except Exception as e:
        logger.error(f"Error in extract_words tool: {e}")
        raise


@mcp.tool
def text_replace(text: str, old: str, new: str, max_replacements: int = -1) -> str:
    """Replace occurrences of old text with new text."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        sanitized_old = sanitize_input(old, max_length=1000)
        sanitized_new = sanitize_input(new, max_length=1000)

        if max_replacements == -1:
            result = sanitized_text.replace(sanitized_old, sanitized_new)
        else:
            result = sanitized_text.replace(sanitized_old, sanitized_new, max_replacements)

        logger.debug("Text replacement completed")
        return result
    except Exception as e:
        logger.error(f"Error in text_replace tool: {e}")
        raise