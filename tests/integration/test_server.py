"""
Integration tests for the MCP server.
"""

import asyncio

import pytest

from src.mcp_boilerplate.server import MCPServer, create_server


class TestServerIntegration:
    """Integration tests for the MCP server."""

    @pytest.mark.asyncio
    async def test_server_creation(self):
        """Test server creation and initialization."""
        server = await create_server("test-server")

        assert isinstance(server, MCPServer)
        assert server.name == "test-server"
        assert server.mcp is not None

    @pytest.mark.asyncio
    async def test_server_health_check(self, test_server):
        """Test server health check."""
        health = await test_server.health_check()
        assert health is True

    @pytest.mark.asyncio
    async def test_server_info(self, test_server):
        """Test server information retrieval."""
        info = test_server.get_server_info()

        required_fields = ["name", "version", "tools_count", "resources_count", "prompts_count"]

        for field in required_fields:
            assert field in info

        # Check that some components are registered
        assert info["tools_count"] > 0
        assert info["resources_count"] > 0
        assert info["prompts_count"] > 0

    @pytest.mark.asyncio
    async def test_component_registration(self, test_server):
        """Test that all components are properly registered."""
        # Check tools
        assert len(test_server.registered_tools) > 0

        # Check resources
        assert len(test_server.registered_resources) > 0

        # Check prompts
        assert len(test_server.registered_prompts) > 0

        # Verify some expected tools exist
        expected_tools = ["add", "text_length", "generate_uuid"]
        for tool in expected_tools:
            assert tool in test_server.registered_tools

    @pytest.mark.asyncio
    async def test_error_handling_setup(self, test_server):
        """Test that error handling is properly set up."""
        assert test_server.error_handler is not None

        # Test error statistics
        stats = test_server.error_handler.get_error_statistics()
        assert "total_errors" in stats
        assert "error_counts" in stats
