# MCP Boilerplate Server Makefile

.PHONY: help install install-dev test lint format type-check clean run build docs

# Default target
help:
	@echo "Available commands:"
	@echo "  install        - Install production dependencies"
	@echo "  install-dev    - Install development dependencies"
	@echo "  test           - Run tests"
	@echo "  test-cov       - Run tests with coverage"
	@echo "  lint           - Run linting (ruff)"
	@echo "  format         - Format code (black + ruff)"
	@echo "  type-check     - Run type checking (mypy)"
	@echo "  clean          - Clean build artifacts"
	@echo "  run            - Run the MCP server (STDIO)"
	@echo "  run-debug      - Run the MCP server in debug mode (STDIO)"
	@echo "  run-sse        - Run the MCP server with SSE transport"
	@echo "  run-sse-debug  - Run the MCP server with SSE transport in debug mode"
	@echo "  run-inspector  - Run the MCP server with Inspector (requires FastMCP CLI)"
	@echo "  run-inspector-debug - Run the MCP server with Inspector in debug mode"
	@echo "  build          - Build the package"

# Installation
install:
	uv sync --no-dev

install-dev:
	uv sync --all-extras

# Testing
test:
	uv run pytest

test-cov:
	uv run pytest --cov=src --cov-report=html --cov-report=term

# Code quality
lint:
	uv run ruff check src tests

format:
	uv run black src tests
	uv run ruff check --fix src tests

type-check:
	uv run mypy src

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Running
run:
	uv run python -m mcp_boilerplate.main

run-debug:
	uv run python -m mcp_boilerplate.main --debug

run-sse:
	uv run python -m mcp_boilerplate.main --transport sse --port 8000

run-sse-debug:
	uv run python -m mcp_boilerplate.main --transport sse --port 8000 --debug

# MCP Inspector (requires FastMCP CLI)
run-inspector:
	@echo "Starting MCP server with Inspector..."
	@echo "This will open MCP Inspector in your browser"
	@command -v fastmcp >/dev/null 2>&1 || (echo "FastMCP CLI not found. Install with: pip install 'fastmcp[cli]>=2.0.0'" && exit 1)
	fastmcp dev src/mcp_boilerplate/inspector.py

run-inspector-debug:
	@echo "Starting MCP server with Inspector in debug mode..."
	@command -v fastmcp >/dev/null 2>&1 || (echo "FastMCP CLI not found. Install with: pip install 'fastmcp[cli]>=2.0.0'" && exit 1)
	DEBUG=1 fastmcp dev src/mcp_boilerplate/inspector.py

# Building
build:
	uv build

# Development workflow
dev-setup: install-dev
	@echo "Development environment ready!"
	@echo "Run 'make run-debug' to start the server in debug mode"

# CI workflow
ci: lint type-check test
	@echo "All checks passed!"