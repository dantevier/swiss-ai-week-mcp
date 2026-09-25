"""Status overview and dashboard endpoints without network calls."""

from datetime import UTC, datetime, timedelta

from starlette.testclient import TestClient

from mcp_boilerplate.dashboard import server as dashboard
from mcp_boilerplate.dashboard.status import get_status
from mcp_boilerplate.knowledge import KnowledgeBase
from mcp_boilerplate.sources import SOURCES

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
    assert rows[("federal", "reference_interest_rate")]["state"] == "up_to_date"
    assert rows[("federal", "premium_regions_2026")]["state"] == "outdated"
    failed = rows[("federal", "health_insurance_premiums")]
    assert failed["state"] == "failed" and failed["error"] == "boom"
    assert rows[("federal", "reference_interest_rate_law")]["state"] == "never_crawled"
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
