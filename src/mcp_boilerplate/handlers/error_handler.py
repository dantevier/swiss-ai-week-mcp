"""
Error handling utilities for the MCP Boilerplate server.
"""

import traceback
from datetime import datetime
from typing import Any

from ..config.settings import settings
from ..utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.handlers.error")


class MCPError(Exception):
    """Base exception class for MCP-related errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()


class ToolError(MCPError):
    """Exception for tool-related errors."""

    pass


class ResourceError(MCPError):
    """Exception for resource-related errors."""

    pass


class PromptError(MCPError):
    """Exception for prompt-related errors."""

    pass


class ValidationError(MCPError):
    """Exception for validation errors."""

    pass


class ErrorHandler:
    """
    Centralized error handling for the MCP server.
    """

    def __init__(self) -> None:
        self.logger = setup_logger("mcp_boilerplate.error_handler")
        self.error_counts: dict[str, int] = {}

    def handle_error(
        self,
        error: Exception,
        context: str | None = None,
        additional_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle and log an error, returning a standardized error response.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            additional_info: Additional information to include in the error response

        Returns:
            Standardized error response dictionary
        """
        # Determine error type and code
        if isinstance(error, MCPError):
            error_code = error.error_code
            error_message = error.message
            error_details = error.details
        else:
            error_code = type(error).__name__
            error_message = str(error)
            error_details = {}

        # Update error counts for monitoring
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1

        # Create error response
        error_response = {
            "error": True,
            "error_code": error_code,
            "message": error_message,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "details": error_details,
        }

        # Add additional info if provided
        if additional_info:
            error_response.update(additional_info)

        # Add debug information if enabled
        if settings.enable_debug:
            error_response["traceback"] = traceback.format_exc()
            error_response["error_type"] = type(error).__name__

        # Log the error
        log_message = f"Error in {context or 'unknown context'}: {error_message}"
        if isinstance(error, (ToolError, ResourceError, PromptError)):
            self.logger.warning(log_message)
        else:
            self.logger.error(log_message, exc_info=True)

        return error_response

    def handle_tool_error(
        self, tool_name: str, error: Exception, args: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Handle errors that occur in tool execution.

        Args:
            tool_name: Name of the tool where the error occurred
            error: The exception that occurred
            args: Arguments passed to the tool

        Returns:
            Standardized error response
        """
        context = f"tool:{tool_name}"
        additional_info = {"tool_name": tool_name, "tool_args": args}

        return self.handle_error(error, context, additional_info)

    def handle_resource_error(self, resource_uri: str, error: Exception) -> dict[str, Any]:
        """
        Handle errors that occur in resource access.

        Args:
            resource_uri: URI of the resource where the error occurred
            error: The exception that occurred

        Returns:
            Standardized error response
        """
        context = f"resource:{resource_uri}"
        additional_info = {"resource_uri": resource_uri}

        return self.handle_error(error, context, additional_info)

    def handle_prompt_error(
        self, prompt_name: str, error: Exception, args: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Handle errors that occur in prompt generation.

        Args:
            prompt_name: Name of the prompt where the error occurred
            error: The exception that occurred
            args: Arguments passed to the prompt

        Returns:
            Standardized error response
        """
        context = f"prompt:{prompt_name}"
        additional_info = {"prompt_name": prompt_name, "prompt_args": args}

        return self.handle_error(error, context, additional_info)

    def get_error_statistics(self) -> dict[str, Any]:
        """
        Get error statistics for monitoring.

        Returns:
            Dictionary containing error statistics
        """
        total_errors = sum(self.error_counts.values())

        return {
            "total_errors": total_errors,
            "error_counts": self.error_counts.copy(),
            "most_common_error": (
                max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None
            ),
            "timestamp": datetime.now().isoformat(),
        }

    def reset_error_counts(self) -> None:
        """Reset error count statistics."""
        self.error_counts.clear()
        self.logger.info("Error count statistics reset")


# Global error handler instance
error_handler = ErrorHandler()
