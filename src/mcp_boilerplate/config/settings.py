"""
Configuration settings for the MCP server.
"""

from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

from ..sources import API_SOURCES


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = ConfigDict(
        env_file=(Path(__file__).resolve().parents[3] / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server Configuration
    server_name: str = Field(default="mcp-swiss-info", description="Name of the MCP server")
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

    # Swiss company data sources (docs/prd-zefix-company-info.md §6)
    lindas_endpoint: str = Field(
        default=API_SOURCES["zefix_lindas"].base_url,
        description="SPARQL endpoint holding the Zefix graph. Primary source.",
    )
    zefix_base_url: str = Field(
        default=API_SOURCES["zefix_web"].base_url,
        description="Zefix REST base URL used for enrichment (status, SHAB date, excerpt link).",
    )
    zefix_username: str | None = Field(default=None, description="Basic-auth user for the documented ZefixPublicREST API")
    zefix_password: str | None = Field(default=None, description="Basic-auth password for the documented ZefixPublicREST API")
    gazette_base_url: str = Field(
        default=API_SOURCES["gazette"].base_url,
        description="Amtsblattportal (SHAB + cantonal gazettes) API base URL.",
    )
    respect_robots_txt: bool = Field(
        default=True,
        description="Respect robots.txt/ToS. When true, the undocumented Zefix web endpoint is not called.",
    )
    user_agent: str = Field(
        default="mcp-swiss-info/0.1.0 (+https://github.com/dantevier/swiss-ai-week-mcp)",
        description="User-Agent sent to every upstream source.",
    )
    lindas_timeout_s: float = Field(default=15.0, description="Budget for the LINDAS phase (both queries)")
    zefix_timeout_s: float = Field(default=5.0, description="Budget for the Zefix enrichment call")
    call_budget_s: float = Field(default=25.0, description="Wall-clock budget for one company_info call")
    reference_cache_ttl_s: int = Field(default=86400, description="TTL for legal forms, rubrics, dataset_modified")


# Global settings instance
settings = Settings()
