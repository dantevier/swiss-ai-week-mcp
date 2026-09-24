"""
Utility tools for the MCP Boilerplate server.
"""

import base64
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from ..server import mcp
from ..utils.logger import setup_logger
from ..utils.validation import sanitize_input

logger = setup_logger("mcp_boilerplate.tools.utility")


@mcp.tool
def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    try:
        result = str(uuid.uuid4())
        logger.debug(f"Generated UUID: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in generate_uuid tool: {e}")
        raise


@mcp.tool
def current_timestamp() -> str:
    """Get the current timestamp in ISO format."""
    try:
        result = datetime.now().isoformat()
        logger.debug(f"Current timestamp: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in current_timestamp tool: {e}")
        raise


@mcp.tool
def hash_text(text: str, algorithm: str = "sha256") -> str:
    """Generate a hash of the input text using the specified algorithm."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)

        # Validate algorithm
        if algorithm not in ["md5", "sha1", "sha256", "sha512"]:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        # Generate hash
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(sanitized_text.encode("utf-8"))
        result = hash_obj.hexdigest()

        logger.debug(f"Generated {algorithm} hash")
        return result
    except Exception as e:
        logger.error(f"Error in hash_text tool: {e}")
        raise


@mcp.tool
def validate_json(text: str) -> dict[str, Any]:
    """Validate if text is valid JSON and return parsing result."""
    try:
        sanitized_text = sanitize_input(text, max_length=50000)

        try:
            parsed = json.loads(sanitized_text)
            result = {
                "valid": True,
                "data": parsed,
                "type": type(parsed).__name__,
                "error": None,
            }
        except json.JSONDecodeError as e:
            result = {"valid": False, "data": None, "type": None, "error": str(e)}

        logger.debug(f"JSON validation result: {result['valid']}")
        return result
    except Exception as e:
        logger.error(f"Error in validate_json tool: {e}")
        raise


@mcp.tool
def format_json(text: str, indent: int = 2) -> str:
    """Format and prettify JSON text."""
    try:
        sanitized_text = sanitize_input(text, max_length=50000)

        # Parse and reformat
        parsed = json.loads(sanitized_text)
        result = json.dumps(parsed, indent=indent, ensure_ascii=False)

        logger.debug("JSON formatted successfully")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in format_json: {e}")
        raise ValueError(f"Invalid JSON: {e}")
    except Exception as e:
        logger.error(f"Error in format_json tool: {e}")
        raise


@mcp.tool
def encode_base64(text: str) -> str:
    """Encode text to base64."""
    try:
        sanitized_text = sanitize_input(text, max_length=10000)
        result = base64.b64encode(sanitized_text.encode("utf-8")).decode("utf-8")
        logger.debug("Text encoded to base64")
        return result
    except Exception as e:
        logger.error(f"Error in encode_base64 tool: {e}")
        raise


@mcp.tool
def decode_base64(encoded_text: str) -> str:
    """Decode base64 text."""
    try:
        sanitized_text = sanitize_input(encoded_text, max_length=20000)
        result = base64.b64decode(sanitized_text).decode("utf-8")
        logger.debug("Base64 text decoded")
        return result
    except Exception as e:
        logger.error(f"Error in decode_base64 tool: {e}")
        raise