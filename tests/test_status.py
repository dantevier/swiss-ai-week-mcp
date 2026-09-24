"""Status overview and dashboard endpoints without network calls."""

from datetime import UTC, datetime, timedelta

from starlette.testclient import TestClient

from mcp_boilerplate import dashboard
from mcp_boilerplate.knowledge import KnowledgeBase
from mcp_boilerplate.sources import SOURCES
from mcp_boilerplate.status import get_status

NOW = datetime(2026, 9, 24, tzinfo=UTC)


def _save(kb, level, source, crawled_at):
    entry = SOURCES[level][source]
    kb.save(
        {"authority_level": level, "source": source, "authority": entry.authority,
         "url": entry.url, "crawled_at": crawled_at.isoformat(), "markdown": "x", "metadata": {}},
        ["x"], [[1.0]],
    )


def test_states(tmp_path):
    kb = KnowledgeBase(tmp_path / "kb.sqlite3")
    _save(kb, "federal", "reference_interest_rate", NOW - timedelta(days=2))
    _save(kb, "federal", "premium_regions_2026", NOW - timedelta(days=90))
    _save(kb, "federal", "health_insurance_premiums", NOW - timedelta(days=5))
    kb.failed("federal", "health_insurance_premiums", "boom")
    rows = {(r["level"], r["source"]): r for r in get_status(kb, NOW)["sources"]}
    assert rows[("federal", "reference_interest_rate")]["state"] == "fresh"
    assert rows[("federal", "premium_regions_2026")]["state"] == "stale"
    failed = rows[("federal", "health_insurance_premiums")]
    assert failed["state"] == "failed" and failed["error"] == "boom"
    assert rows[("federal", "reference_interest_rate_law")]["state"] == "missing"
    assert len(rows) >= sum(len(v) for v in SOURCES.values())


def test_refresh_endpoint_guards(monkeypatch):
    client = TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""})
    monkeypatch.setattr(dashboard.settings, "crawlora_api_key", None)
    assert client.post("/api/refresh/federal/all").status_code == 400
    monkeypatch.setattr(dashboard.settings, "crawlora_api_key", "k")
    monkeypatch.setattr(dashboard.settings, "openai_api_key", "k")
    assert client.post("/api/refresh/federal/nope").status_code == 404
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret")
    assert client.post("/api/refresh/federal/all").status_code == 401


def test_refresh_endpoint_runs_crawler(monkeypatch):
    calls = []

    class FakeCrawler:
        async def crawl(self, level, source):
            calls.append((level, source))
            return {"source": source}

    monkeypatch.setattr(dashboard, "Crawler", FakeCrawler)
    monkeypatch.setattr(dashboard.settings, "crawlora_api_key", "k")
    monkeypatch.setattr(dashboard.settings, "openai_api_key", "k")
    response = TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""}).post("/api/refresh/federal/reference_interest_rate")
    assert response.status_code == 200 and calls == [("federal", "reference_interest_rate")]



def test_opencode_install_merges_config(tmp_path, monkeypatch):
    import json

    from mcp_boilerplate import install

    config = tmp_path / "opencode.json"
    config.write_text(json.dumps({"theme": "x", "mcp": {"other": {"type": "local"}}}))
    monkeypatch.setattr(install, "OPENCODE_CONFIG", config)
    install.install("opencode")
    saved = json.loads(config.read_text())
    assert saved["theme"] == "x" and "other" in saved["mcp"]
    assert saved["mcp"][install.NAME]["command"][:3] == ["uv", "run", "--directory"]
    config.write_text("{ // jsonc\n}")
    try:
        install.install("opencode")
    except RuntimeError as exc:
        assert "merge this in by hand" in str(exc)
    else:
        raise AssertionError("expected failure on non-JSON config")


async def test_open_dashboard_tool_registered():
    from mcp_boilerplate.server import mcp
    from mcp_boilerplate.tools import source_tools  # noqa: F401

    names = {tool.name for tool in await mcp.list_tools()}
    assert {"open_dashboard", "source_status"} <= names


def test_cli_install_uses_resolved_path_and_reports_failure(monkeypatch):
    import subprocess

    import pytest

    from mcp_boilerplate import install

    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(install.shutil, "which", lambda name: rf"C:\npm\{name}.cmd")
    monkeypatch.setattr(install.subprocess, "run", fake_run)
    assert install.install("codex") == "ok"
    assert calls[0][0] == r"C:\npm\codex.cmd" and calls[0][1:3] == ["mcp", "add"]

    monkeypatch.setattr(install.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        install.install("claude")
