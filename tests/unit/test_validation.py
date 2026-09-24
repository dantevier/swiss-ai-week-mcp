"""
Unit tests for validation utilities.
"""

import pytest

from src.mcp_boilerplate.utils.validation import (
    MCPValidationError,
    sanitize_input,
    validate_resource_uri,
    validate_tool_name,
)


class TestToolNameValidation:
    """Tests for tool name validation."""

    def test_valid_tool_names(self):
        """Test valid tool names."""
        valid_names = [
            "add",
            "text_processor",
            "data-analyzer",
            "tool123",
            "A_Valid_Tool_Name",
            "hyphenated-tool",
        ]

        for name in valid_names:
            assert validate_tool_name(name) == name

    def test_invalid_tool_names(self):
        """Test invalid tool names."""
        invalid_names = [
            "",  # empty
            "123invalid",  # starts with number
            "invalid tool",  # contains space
            "invalid@tool",  # contains special char
            "a" * 65,  # too long
        ]

        for name in invalid_names:
            with pytest.raises(MCPValidationError):
                validate_tool_name(name)


class TestResourceUriValidation:
    """Tests for resource URI validation."""

    def test_valid_uris(self):
        """Test valid resource URIs."""
        valid_uris = [
            "http://example.com",
            "file:///path/to/file",
            "custom://resource",
            "data://store/key",
        ]

        for uri in valid_uris:
            assert validate_resource_uri(uri) == uri

    def test_invalid_uris(self):
        """Test invalid resource URIs."""
        invalid_uris = ["", "not-a-uri", "://missing-scheme"]  # empty  # no scheme  # malformed

        for uri in invalid_uris:
            with pytest.raises(MCPValidationError):
                validate_resource_uri(uri)


class TestInputSanitization:
    """Tests for input sanitization."""

    def test_normal_input(self):
        """Test normal input sanitization."""
        input_text = "Hello, World!"
        result = sanitize_input(input_text)
        assert result == input_text

    def test_dangerous_characters(self):
        """Test removal of dangerous characters."""
        input_text = 'Hello <script>alert("xss")</script> World'
        result = sanitize_input(input_text)
        assert "<script>" not in result
        assert "alert" in result  # Should keep safe parts

    def test_length_limit(self):
        """Test length limiting."""
        long_text = "a" * 2000
        with pytest.raises(MCPValidationError):
            sanitize_input(long_text, max_length=1000)

    def test_none_input(self):
        """Test None input handling."""
        result = sanitize_input(None)
        assert result == ""

    def test_non_string_input(self):
        """Test non-string input conversion."""
        result = sanitize_input(123)
        assert result == "123"
