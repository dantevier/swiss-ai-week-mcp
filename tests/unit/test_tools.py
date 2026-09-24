"""
Unit tests for MCP tools.
"""

import json
from unittest.mock import Mock

import pytest

from src.mcp_boilerplate.tools.math_tools import register_math_tools
from src.mcp_boilerplate.tools.text_tools import register_text_tools
from src.mcp_boilerplate.tools.utility_tools import register_utility_tools


class TestMathTools:
    """Tests for mathematical tools."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = register_math_tools(self.mock_mcp)

    def test_tools_registered(self):
        """Test that math tools are registered."""
        expected_tools = ["add", "subtract", "multiply", "divide", "power", "factorial"]
        for tool in expected_tools:
            assert tool in self.registered_tools

    def test_addition(self):
        """Test addition function if accessible."""
        # Note: In a real implementation, you might need to access the actual function
        # This is a simplified test structure
        assert "add" in self.registered_tools
        assert "Add two numbers together" in self.registered_tools["add"]

    def test_division_by_zero(self):
        """Test division by zero handling."""
        # This would test the actual division function
        # Implementation depends on how FastMCP exposes registered functions
        pass


class TestTextTools:
    """Tests for text processing tools."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = register_text_tools(self.mock_mcp)

    def test_tools_registered(self):
        """Test that text tools are registered."""
        expected_tools = [
            "text_length",
            "text_uppercase",
            "text_lowercase",
            "text_reverse",
            "word_count",
            "extract_words",
            "text_replace",
        ]
        for tool in expected_tools:
            assert tool in self.registered_tools


class TestUtilityTools:
    """Tests for utility tools."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp = Mock()
        self.registered_tools = register_utility_tools(self.mock_mcp)

    def test_tools_registered(self):
        """Test that utility tools are registered."""
        expected_tools = [
            "generate_uuid",
            "current_timestamp",
            "hash_text",
            "validate_json",
            "format_json",
            "encode_base64",
            "decode_base64",
        ]
        for tool in expected_tools:
            assert tool in self.registered_tools

    def test_uuid_generation(self):
        """Test UUID generation description."""
        assert "Generate a new UUID4 string" in self.registered_tools["generate_uuid"]

    def test_json_validation(self):
        """Test JSON validation description."""
        assert "validate_json" in self.registered_tools
        assert "Validate if text is valid JSON" in self.registered_tools["validate_json"]
