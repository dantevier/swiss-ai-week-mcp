"""API key storage and the dashboard settings endpoint."""

import pytest
from starlette.testclient import TestClient

from mcp_boilerplate.dashboard import server as dashboard
from mcp_boilerplate.config import env


def test_save_preserves_other_lines_and_validates(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# note\nLOG_LEVEL=INFO\nOPENAI_API_KEY=old\n")
    env.save_env({"OPENAI_API_KEY": "new-key", "CRAWLORA_API_KEY": "abc"}, path)
    assert path.read_text() == "# note\nLOG_LEVEL=INFO\nOPENAI_API_KEY=new-key\nCRAWLORA_API_KEY=abc\n"
    for bad in ("a b", "x\nOPENAI_API_KEY=y", 'q"q'):
        with pytest.raises(ValueError):
            env.save_env({"OPENAI_API_KEY": bad}, path)
    with pytest.raises(ValueError):
        env.save_env({"PATH": "x"}, path)
    assert env.describe("sk-abcdefghijkl") == {"set": True, "hint": "...ijkl"}
    assert env.describe(None) == {"set": False, "hint": None}


def test_settings_endpoint(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(env, "ENV_PATH", path)
    monkeypatch.setattr(dashboard.settings, "crawlora_api_key", None)
    monkeypatch.setattr(dashboard.settings, "openai_api_key", None)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "")  # restored on teardown after the endpoint sets it
    monkeypatch.setenv("CRAWLORA_API_KEY", "")
    client = TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""})
    assert client.post("/api/settings", json={}).status_code == 400
    assert client.post("/api/settings", json={"OPENAI_API_KEY": "bad value"}).status_code == 400
    assert not client.get("/api/status").json()["can_refresh"]
    ok = client.post(
        "/api/settings",
        json={"CRAWLORA_API_KEY": "crawl-key-123456", "OPENAI_API_KEY": "sk-openai-123456"},
    )
    assert ok.status_code == 200
    assert "CRAWLORA_API_KEY=crawl-key-123456" in path.read_text()
    status = client.get("/api/status")
    assert status.json()["can_refresh"]
    assert status.json()["keys"]["OPENAI_API_KEY"]["hint"] == "...3456"
    assert "sk-openai" not in status.text
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret")
    assert client.post("/api/settings", json={"OPENAI_API_KEY": "x"}).status_code == 401


def test_settings_lives_on_its_own_page():
    client = TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""})
    main, settings = client.get("/").text, client.get("/settings").text
    assert 'href="/settings"' in main and 'name="OPENAI_API_KEY"' not in main
    assert 'name="OPENAI_API_KEY"' in settings and 'name="CRAWLORA_API_KEY"' in settings
    assert 'href="/"' in settings


def test_settings_page_explains_where_to_get_keys():
    page = TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""}).get("/settings").text
    assert "https://crawlora.net" in page and "https://platform.openai.com/api-keys" in page
    assert page.count('class="help"') == 2 and 'aria-expanded="false"' in page


def test_dashboard_blocks_cross_site_writes_and_foreign_hosts(monkeypatch):
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.setattr(dashboard.settings, "crawlora_api_key", "k")
    monkeypatch.setattr(dashboard.settings, "openai_api_key", "k")
    # A page on another site can send a simple POST, but not the custom header this page sends.
    plain = TestClient(dashboard.app, base_url="http://127.0.0.1")
    assert plain.post("/api/settings", json={"OPENAI_API_KEY": "sk-evil-123456"}).status_code == 401
    assert plain.post("/api/refresh/federal/all").status_code == 401
    assert plain.post("/api/settings", content="not json", headers={"x-dashboard-token": ""}).status_code == 400
    # DNS rebinding: an attacker's hostname pointing at 127.0.0.1 is refused outright.
    rebound = TestClient(dashboard.app, base_url="http://evil.example")
    assert rebound.get("/api/status").status_code == 400
    assert plain.get("/api/status").status_code == 200


def test_only_one_refresh_runs_at_a_time(monkeypatch):
    monkeypatch.setattr(dashboard.settings, "crawlora_api_key", "k")
    monkeypatch.setattr(dashboard.settings, "openai_api_key", "k")
    import asyncio

    async def run():
        async with dashboard._crawl_lock:
            return TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""}).post(
                "/api/refresh/federal/reference_interest_rate"
            ).status_code

    assert asyncio.run(run()) == 409
