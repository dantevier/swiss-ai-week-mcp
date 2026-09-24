"""
Configuration settings for the MCP server.
"""

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server Configuration
    server_name: str = Field(default="mcp-boilerplate", description="Name of the MCP server")
    server_version: str = Field(default="0.1.0", description="Version of the server")

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    log_file: str | None = Field(default=None, description="Log file path")

    # Security Configuration
    max_request_size: int = Field(default=1024 * 1024, description="Maximum request size in bytes")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")

    # Feature Flags
    enable_debug: bool = Field(default=False, description="Enable debug mode")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    # External Service Configuration
    api_base_url: str | None = Field(default=None, description="Base URL for external APIs")
    api_key: str | None = Field(default=None, description="API key for external services")
    crawlora_api_key: str | None = Field(default=None, description="Crawlora API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI embeddings API key")
    knowledge_db_path: str | None = Field(default=None, description="Writable SQLite knowledge base path")




# Global settings instance
settings = Settings()
