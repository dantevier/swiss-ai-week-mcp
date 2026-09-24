"""Registry checks for API_SOURCES (docs/prd-company-info-refactor.md S3, T5)."""

import pytest

from mcp_boilerplate.config.settings import settings
from mcp_boilerplate.crawler import check_url
from mcp_boilerplate.sources import API_SOURCES
from mcp_boilerplate.zefix.sources import http


def test_every_api_source_host_is_allowed():
    allowed = http.allowed_hosts()
    for name, source in API_SOURCES.items():
        for host in source.hosts:
            assert host in allowed, f"{name} host {host!r} missing from allowed_hosts()"


def test_zefix_lindas_base_url_is_not_a_crawlable_source():
    with pytest.raises(ValueError):
        check_url("federal", API_SOURCES["zefix_lindas"].base_url)


@pytest.mark.parametrize(
    ("settings_field", "registry_key"),
    [
        ("lindas_endpoint", "zefix_lindas"),
        ("zefix_base_url", "zefix_web"),
        ("gazette_base_url", "gazette"),
    ],
)
def test_settings_defaults_match_registry_base_urls(settings_field, registry_key):
    assert getattr(settings, settings_field) == API_SOURCES[registry_key].base_url
