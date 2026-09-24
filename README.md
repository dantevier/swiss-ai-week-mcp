# MCP Boilerplate

A robust, production-ready boilerplate template for Model Context Protocol (MCP) servers built with Python and FastMCP v2.

## 🎯 **About This Template**

This boilerplate provides everything you need to build professional MCP servers:

- **🏗️ Robust Architecture**: Modular design with clear separation of concerns
- **🔧 Comprehensive Tooling**: Math, text processing, and utility functions out of the box
- **📊 Rich Resources**: System metrics, data stores, and sample data
- **🤖 AI Prompts**: Ready-to-use prompt templates for various scenarios
- **🛡️ Production Ready**: Error handling, logging, validation, and testing
- **📋 Developer Experience**: Make commands, code quality tools, and comprehensive docs
- **⚡ FastMCP v2**: Latest FastMCP version with improved API and multiple transport support

## Features

🔧 **Example Tools Included**
- Mathematical operations (add, subtract, multiply, divide, power, factorial)
- Text processing (length, case conversion, word extraction, replacement)
- Utility functions (UUID generation, hashing, JSON validation, base64 encoding)

📊 **Example Resources**
- System information and performance metrics
- In-memory data store with statistics
- Sample data in multiple formats (JSON, CSV, XML)

🤖 **Example Prompts**
- Code review and explanation prompts
- Data analysis and problem-solving templates
- Comparative analysis frameworks

🛡️ **Production Features**
- Comprehensive error handling and logging
- Input validation and security measures
- Health checks and monitoring
- Extensive test coverage
- Type safety with MyPy

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### 1. Use This Template

```bash
# Clone the template
git clone <your-repo-url> your-mcp-server
cd your-mcp-server

# Remove existing git history (optional)
rm -rf .git
git init
```

#### Rename the Package

**Option A: Manual Rename**
1. Rename `src/mcp_boilerplate/` to `src/your_server_name/`
2. Update imports in all Python files
3. Update `pyproject.toml` package references

**Option B: Automated Rename (Recommended)**
```bash
# Test what changes would be made (dry run)
python scripts/rename_project.py --dry-run your_server_name

# Rename everything at once
python scripts/rename_project.py your_server_name
```

### 2. Install Dependencies

```bash
# Install development dependencies
uv sync --all-extras

# Copy environment configuration
cp .env.example .env
```

### 3. Customize Your Server

1. **Update Project Info** in `pyproject.toml`:
   ```toml
   [project]
   name = "your-mcp-server"
   description = "Your custom MCP server description"
   authors = [
       {name = "Your Name", email = "your.email@example.com"}
   ]
   keywords = ["mcp", "your", "keywords"]
   
   [project.urls]
   Homepage = "https://github.com/yourusername/your-mcp-server"
   Repository = "https://github.com/yourusername/your-mcp-server"
   Issues = "https://github.com/yourusername/your-mcp-server/issues"
   
   [project.scripts]
   your-mcp-server = "your_server_name.main:main"
   
   [tool.hatch.build.targets.wheel]
   packages = ["src/your_server_name"]
   ```

2. **Modify Server Name** in `src/your_server_name/config/settings.py`:
   ```python
   server_name: str = Field(default="your-server-name", description="Name of the MCP server")
   ```

3. **Update Environment Variables** in `.env`:
   ```bash
   SERVER_NAME=your-server-name
   # Add your custom variables
   YOUR_API_KEY=your-api-key
   YOUR_DATABASE_URL=postgresql://...
   ```

4. **Add Your Tools** in `src/your_server_name/tools/`:
   - Create new tool files
   - Register them in `tools/__init__.py`

5. **Add Your Resources** in `src/your_server_name/resources/`:
   - Create new resource files  
   - Register them in `resources/__init__.py`

### 4. Run Your Server

```bash
# Run with STDIO transport (default)
make run

# Or run directly
uv run python -m mcp_boilerplate.main

# Debug mode
make run-debug

# Run with SSE transport for web integration
make run-sse

# Or run SSE directly
uv run --extra sse python -m mcp_boilerplate.main --transport sse --port 8000
```

### 5. Test Your Server

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Code quality checks
make lint
make type-check
```

## Using with Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_boilerplate.main"],
      "cwd": "/path/to/your-mcp-server"
    }
  }
}
```

## Project Structure

```
src/mcp_boilerplate/
├── __init__.py
├── main.py              # CLI entry point
├── server.py            # Core server implementation
├── config/
│   ├── __init__.py
│   └── settings.py      # Configuration management
├── tools/               # MCP tools
│   ├── __init__.py
│   ├── math_tools.py
│   ├── text_tools.py
│   └── utility_tools.py
├── resources/           # MCP resources
│   ├── __init__.py
│   ├── system_resources.py
│   └── data_resources.py
├── prompts/             # MCP prompts
│   ├── __init__.py
│   ├── assistant_prompts.py
│   └── analysis_prompts.py
├── handlers/            # Error handling
│   ├── __init__.py
│   └── error_handler.py
└── utils/               # Utilities
    ├── __init__.py
    ├── logger.py
    └── validation.py
```

## Customization Guide

### Remove Example Components

The boilerplate includes example tools, resources, and prompts. Remove what you don't need:

```bash
# Remove example tools (keep only what you want)
rm src/your_server_name/tools/math_tools.py
rm src/your_server_name/tools/text_tools.py
# Keep utility_tools.py or customize it

# Remove example resources
rm src/your_server_name/resources/data_resources.py
# Keep system_resources.py for monitoring

# Remove example prompts (if you don't need them)
rm -rf src/your_server_name/prompts/
```

**Important**: Update the `__init__.py` files to remove references to deleted modules.

### Adding New Tools

1. Create a new file in `src/your_server_name/tools/`:
   ```python
   # src/your_server_name/tools/your_tools.py
   from ..server import mcp
   
   @mcp.tool
   def your_tool(param: str) -> str:
       """Your tool description."""
       return f"Result: {param}"
   ```

2. Register in `src/your_server_name/tools/__init__.py`:
   ```python
   # Import to register the tools
   from . import your_tools
   ```

### Adding New Resources

1. Create a new file in `src/your_server_name/resources/`:
   ```python
   # src/your_server_name/resources/your_resources.py
   from ..server import mcp
   import json
   
   @mcp.resource("your-domain://data/{id}")
   def get_your_data(id: str) -> str:
       """Get your domain-specific data."""
       return json.dumps({"id": id, "data": "your_data"})
   ```

2. Register in `src/your_server_name/resources/__init__.py`:
   ```python
   # Import to register the resources
   from . import your_resources
   ```

### Adding New Prompts

1. Create a new file in `src/your_server_name/prompts/`:
   ```python
   # src/your_server_name/prompts/your_prompts.py
   from ..server import mcp
   
   @mcp.prompt
   def your_prompt(task: str, style: str = "professional") -> str:
       """Generate a custom prompt."""
       return f"Task: {task}\nStyle: {style}"
   ```

2. Register in `src/your_server_name/prompts/__init__.py`:
   ```python
   # Import to register the prompts
   from . import your_prompts
   ```

## Common Integration Patterns

### Database Integration

```python
# Add to pyproject.toml dependencies
dependencies = [
    # ... existing dependencies
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.28.0",  # for PostgreSQL
]

# Create database tools
@mcp.tool
def query_database(sql: str) -> str:
    """Execute a database query."""
    # Your database implementation with proper validation
    pass
```

### API Integration

```python
# Add HTTP client dependency
dependencies = [
    # ... existing dependencies
    "httpx>=0.24.0",
]

# Create API tools
@mcp.tool
async def call_external_api(endpoint: str) -> str:
    """Call an external API."""
    # Your API implementation with error handling
    pass
```

### File System Operations

```python
@mcp.tool
def read_file(file_path: str) -> str:
    """Read a file from the filesystem."""
    # Implement with proper security checks and path validation
    pass

@mcp.resource("file://{path}")
def get_file_content(path: str) -> str:
    """Get file content as a resource."""
    # Your implementation with security validation
    pass
```

## Development Commands

```bash
# Setup development environment
make install-dev

# Run server
make run              # Production mode
make run-debug        # Debug mode

# Testing
make test             # Run tests
make test-cov         # Run with coverage

# Code quality
make lint             # Linting
make format           # Code formatting
make type-check       # Type checking

# All quality checks
make ci

# Build package
make build
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
# Server Configuration
SERVER_NAME=your-server-name
LOG_LEVEL=INFO
ENABLE_DEBUG=false
ENABLE_METRICS=true
MAX_REQUEST_SIZE=1048576
REQUEST_TIMEOUT=30

# Your Custom Variables
YOUR_API_KEY=your-api-key
YOUR_DATABASE_URL=postgresql://user:pass@localhost/db
YOUR_CUSTOM_SETTING=value
```

### Dependencies

Update `pyproject.toml` with your specific dependencies:

```toml
dependencies = [
    "fastmcp>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    # Add your dependencies here
    "your-required-library>=1.0.0",
]

# SSE transport support (optional)
[project.optional-dependencies]
sse = [
    "uvicorn>=0.24.0",
    "starlette>=0.32.0",
]
```

## Example Tools Included

### Math Tools
- `add(a, b)` - Add two numbers
- `subtract(a, b)` - Subtract two numbers
- `multiply(a, b)` - Multiply two numbers
- `divide(a, b)` - Divide two numbers
- `power(base, exponent)` - Raise to power
- `factorial(n)` - Calculate factorial

### Text Tools
- `text_length(text)` - Get text length
- `text_uppercase(text)` - Convert to uppercase
- `text_lowercase(text)` - Convert to lowercase
- `text_reverse(text)` - Reverse text
- `word_count(text)` - Count words
- `extract_words(text, min_length)` - Extract words
- `text_replace(text, old, new)` - Replace text

### Utility Tools
- `generate_uuid()` - Generate UUID4
- `current_timestamp()` - Get current timestamp
- `hash_text(text, algorithm)` - Hash text
- `validate_json(text)` - Validate JSON
- `format_json(text)` - Format JSON
- `encode_base64(text)` - Base64 encode
- `decode_base64(text)` - Base64 decode

## Example Resources Included

### System Resources
- `system://info` - System information
- `system://performance` - Performance metrics
- `system://config` - Server configuration

### Data Resources
- `data://store/{key}` - Get stored data by key
- `data://store` - List all stored data
- `data://statistics` - Data store statistics
- `data://sample/{format}` - Sample data (json/csv/xml)

## Example Prompts Included

### Assistant Prompts
- `helpful_assistant(task, style)` - General assistance
- `code_reviewer(code, language, focus)` - Code review
- `explain_concept(concept, audience, depth)` - Concept explanation

### Analysis Prompts
- `data_analyst(data_description, analysis_type)` - Data analysis
- `problem_solver(problem, approach)` - Problem solving
- `comparative_analysis(item_a, item_b, criteria)` - Comparison

## Testing Your Changes

```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector uv run python -m mcp_boilerplate.main

# Or if installed globally
mcp-inspector uv run python -m mcp_boilerplate.main
```

## Security & Best Practices

### Security Considerations

- **Input Validation**: Review and update validation in `utils/validation.py`
- **Sensitive Data**: Ensure no secrets are logged or exposed in error messages
- **Rate Limiting**: Add rate limiting for production deployments
- **Path Validation**: Validate file paths to prevent directory traversal
- **Environment Variables**: Never commit secrets to the repository

### Development Best Practices

1. **Follow the established patterns** for tools, resources, and prompts
2. **Add comprehensive error handling** for all new components
3. **Include input validation** for security
4. **Write tests** for new functionality
5. **Update documentation** when adding features
6. **Use type hints** for better code quality
7. **Test with MCP Inspector** before deploying

### Testing Your Changes

```bash
# Update tests to match your changes
make test

# Test with MCP Inspector
npx @modelcontextprotocol/inspector uv run python -m your_server_name.main

# Or if installed globally
mcp-inspector uv run python -m your_server_name.main
```

## Contributing

1. Fork this repository
2. Create your feature branch
3. Add your tools, resources, or prompts
4. Write tests for new functionality
5. Run quality checks: `make ci`
6. Submit a pull request

## Team

- Roberto Cerrone
- Edoardo Diana
- Alberto Minetti
- Vincent Van Loo
- Victor Bonilla
- Jesus Sebastian
- Jiaqi Yu

## License

MIT License - see LICENSE file for details.

## Automation Script

Create `scripts/rename_project.sh` for automated setup:

```bash
#!/bin/bash
# Usage: ./scripts/rename_project.sh new_name "New Description"

OLD_NAME="mcp_boilerplate"
NEW_NAME="$1"
NEW_DESC="$2"

if [ -z "$NEW_NAME" ]; then
    echo "Usage: $0 new_name \"New Description\""
    exit 1
fi

# Rename source directory
mv "src/${OLD_NAME}" "src/${NEW_NAME}"

# Update all Python files
find . -name "*.py" -exec sed -i "s/${OLD_NAME}/${NEW_NAME}/g" {} +

# Update pyproject.toml
sed -i "s/mcp-boilerplate/${NEW_NAME//_/-}/g" pyproject.toml
sed -i "s/mcp_boilerplate/${NEW_NAME}/g" pyproject.toml

if [ -n "$NEW_DESC" ]; then
    sed -i "s/A robust boilerplate template.*/${NEW_DESC}/g" pyproject.toml
fi

echo "Project renamed to ${NEW_NAME}"
echo "Don't forget to update README.md and other documentation!"
```

## Additional Resources

- 📖 [MCP Specification](https://modelcontextprotocol.io/)
- 🚀 [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
- 🖥️ [Claude Desktop Configuration](https://docs.anthropic.com/claude/docs/mcp)
- 🔍 [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/mcp-boilerplate/issues)
- 💬 [Discussions](https://github.com/yourusername/mcp-boilerplate/discussions)

---

**🚀 Start building your MCP server now!** This boilerplate gives you everything you need to create production-ready MCP servers quickly and efficiently.