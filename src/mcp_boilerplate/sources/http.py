"""Shared HTTP client with egress allow-list.

Vendored and adapted from malkreide/register-mcp, src/register_mcp/server.py
(_enforce_egress_allowlist, _make_client). MIT, Copyright (c) 2026 Hayal Oezkan.
"""

from __future__ import annotations

import logging

import httpx

from ..config.settings import settings

logger = logging.getLogger("mcp_boilerplate.sources.http")


class EgressDenied(httpx.RequestError):
    """Raised when a request targets a host outside settings.allowed_hosts."""


class SourceUnavailable(Exception):
    """An upstream source could not answer. Maps to the `source_unavailable` state.

    source:        "lindas" | "zefix" | "gazette"
    error_class:   short machine-readable class, e.g. "timeout", "http_503", "network", "egress_denied", "policy_robots"
    retry_after_s: seconds suggested by the upstream, if any
    """

    def __init__(self, source: str, error_class: str, message: str = "", retry_after_s: float | None = None):
        super().__init__(message or f"{source}: {error_class}")
        self.source = source
        self.error_class = error_class
        self.retry_after_s = retry_after_s


def allowed_hosts() -> frozenset[str]:
    return frozenset(h.strip().lower() for h in settings.allowed_hosts if h.strip())


async def _enforce_egress_allowlist(request: httpx.Request) -> None:
    """httpx event hook: reject requests to hosts outside the allow-list.

    Runs before send AND on each redirect hop, so an unexpected 3xx Location
    cannot send the request elsewhere.
    """
    host = (request.url.host or "").lower()
    hosts = allowed_hosts()
    if host not in hosts:
        logger.error("egress_denied host=%s url=%s allowed=%s", host, request.url, sorted(hosts))
        raise EgressDenied(f"Egress to host {host!r} is not in ALLOWED_HOSTS", request=request)


def make_client(timeout: float, *, accept: str = "application/json", auth: httpx.Auth | None = None) -> httpx.AsyncClient:
    """Create an async HTTP client with the project User-Agent and the egress guard.

    Callers use it as `async with make_client(5.0) as client:`.
    """
    return httpx.AsyncClient(
        timeout=timeout,
        headers={"Accept": accept, "User-Agent": settings.user_agent},
        follow_redirects=True,
        auth=auth,
        event_hooks={"request": [_enforce_egress_allowlist]},
    )


def classify_error(exc: Exception) -> tuple[str, float | None]:
    """Map an httpx exception to (error_class, retry_after_s)."""
    if isinstance(exc, EgressDenied):
        return "egress_denied", None
    if isinstance(exc, httpx.TimeoutException):
        return "timeout", None
    if isinstance(exc, httpx.HTTPStatusError):
        retry_after = None
        ra = exc.response.headers.get("Retry-After")
        if ra and ra.isdigit():
            retry_after = float(ra)
        return f"http_{exc.response.status_code}", retry_after
    if isinstance(exc, httpx.RequestError):
        return "network", None
    return type(exc).__name__.lower(), None
