"""
Validation utilities for the MCP Boilerplate server.
"""

import re
from typing import Any

from pydantic import BaseModel, field_validator


class MCPValidationError(Exception):
    """Custom exception for MCP validation errors."""

    pass


def validate_tool_name(name: str) -> str:
    """
    Validate tool name follows MCP conventions.

    Args:
        name: Tool name to validate

    Returns:
        Validated tool name

    Raises:
        MCPValidationError: If name is invalid
    """
    if not name:
        raise MCPValidationError("Tool name cannot be empty")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
        raise MCPValidationError(
            "Tool name must start with a letter and contain only letters, numbers, underscores, and hyphens"
        )

    if len(name) > 64:
        raise MCPValidationError("Tool name must be 64 characters or less")

    return name


def validate_resource_uri(uri: str) -> str:
    """
    Validate resource URI follows MCP conventions.

    Args:
        uri: Resource URI to validate

    Returns:
        Validated URI

    Raises:
        MCPValidationError: If URI is invalid
    """
    if not uri:
        raise MCPValidationError("Resource URI cannot be empty")

    # Basic URI pattern validation
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", uri):
        raise MCPValidationError("Resource URI must have a valid scheme")

    return uri


def sanitize_input(value: Any, max_length: int = 1000) -> str:
    """
    Sanitize user input for security.

    Args:
        value: Input value to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        MCPValidationError: If input is invalid
    """
    if value is None:
        return ""

    # Convert to string
    str_value = str(value)

    # Check length
    if len(str_value) > max_length:
        raise MCPValidationError(f"Input exceeds maximum length of {max_length}")

    # Remove potential security risks
    sanitized = re.sub(r'[<>"\']', "", str_value)

    return sanitized.strip()


class RequestValidator(BaseModel):
    """Base validator for MCP requests."""

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_strings(cls, v: Any) -> Any:
        """Sanitize all string fields."""
        if isinstance(v, str):
            return sanitize_input(v)
        return v
