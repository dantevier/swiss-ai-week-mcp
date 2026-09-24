"""
Pytest configuration and fixtures for MCP Boilerplate server tests.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest

from src.mcp_boilerplate.config.settings import Settings
from src.mcp_boilerplate.server import MCPServer, create_server


@pytest.fixture
def test_settings():
    """Provide test-specific settings."""
    return Settings(
        server_name="mcp-boilerplate-test",
        log_level="DEBUG",
        enable_debug=True,
        enable_metrics=False,
    )


@pytest.fixture
async def test_server(test_settings) -> AsyncGenerator[MCPServer, None]:
    """Create a test MCP server instance."""
    server = await create_server("mcp-boilerplate-test")
    yield server
    # Cleanup if needed


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_data():
    """Provide sample test data."""
    return {
        "test_text": "Hello, World! This is a test string.",
        "test_numbers": [1, 2, 3, 4, 5],
        "test_json": '{"name": "test", "value": 42}',
        "invalid_json": '{"invalid": json}',
        "test_calculations": [
            {"a": 5, "b": 3, "expected_sum": 8},
            {"a": 10, "b": 2, "expected_product": 20},
            {"a": 15, "b": 3, "expected_division": 5},
        ],
    }
