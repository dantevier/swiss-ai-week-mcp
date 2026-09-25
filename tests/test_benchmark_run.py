"""Benchmark runner helpers, the run interpretation and the dashboard's Benchmark tab."""

import json
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))

import interpret  # noqa: E402
import run_mcp  # noqa: E402

from mcp_swiss_info.dashboard import server as dashboard  # noqa: E402


def question(qid, behavior="answer", must=r"30 (Tage|days)", must_not=r"60 Tage"):
    return {
        "id": qid, "question": f"Question {qid}?", "topic_area": "3", "topic": "law", "expected_behavior": behavior,
        "must_include": [{"fact": "30 days", "pattern": must}] if must else [],
        "must_not_include": [{"reason": "wrong deadline", "pattern": must_not}],
    }


def write_run(folder: Path, rows, answers, traces, mcp=True):
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps({"model": "test-model", "mcp": mcp}), encoding="utf-8")
    lines = lambda items: "".join(json.dumps(i) + "\n" for i in items)  # noqa: E731
    (folder / "questions.jsonl").write_text(lines(rows), encoding="utf-8")
    results = []
    for row in rows:
        problems = [] if answers[row["id"]].startswith("PASS") else ["missing: 30 days"]
        results.append({"id": row["id"], "passed": not problems, "problems": problems, "answer": answers[row["id"]]})
    (folder / "results.jsonl").write_text(lines(results), encoding="utf-8")
    (folder / "traces.jsonl").write_text(lines({"id": k, "trace": v} for k, v in traces.items()), encoding="utf-8")


def test_split_model_infers_the_provider():
    assert run_mcp.split_model("gpt-5") == ("openai", "gpt-5")
    assert run_mcp.split_model("o4-mini") == ("openai", "o4-mini")
    assert run_mcp.split_model("claude-opus-5") == ("anthropic", "claude-opus-5")
    assert run_mcp.split_model("ollama:qwen3") == ("ollama", "qwen3")
    with pytest.raises(SystemExit):
        run_mcp.split_model("qwen3")


def test_default_model_follows_the_available_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY or OPENAI_API_KEY"):
        run_mcp.default_model()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert run_mcp.default_model() == "gpt-5"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert run_mcp.default_model() == "claude-opus-5"


def test_env_file_fills_missing_keys_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nOPENAI_API_KEY=from-file\nOTHER_KEY=file\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OTHER_KEY", "from-env")
    run_mcp.load_env_file(env)
    assert run_mcp.os.environ["OPENAI_API_KEY"] == "from-file"
    assert run_mcp.os.environ["OTHER_KEY"] == "from-env"


def test_model_prompt_includes_server_instructions_only_with_mcp():
    mcp = run_mcp.McpTools(None, [], "Use specific tools before search_knowledge.")
    assert "Use specific tools before search_knowledge." in run_mcp.system_prompt(mcp)
    assert run_mcp.system_prompt(None) == run_mcp.SYSTEM_PROMPT


def test_interpretation_explains_each_failure(tmp_path):
    rows = [question("ok"), question("error"), question("wrong"), question("ask", behavior="ask_back", must=None),
            question("notool"), question("missed"), question("declined"), question("gap")]
    search = {"tool": "search_knowledge", "error": False}
    answers = {"ok": "PASS 30 Tage", "error": "", "wrong": "Sie haben 60 Tage.", "ask": "Die Gebühr ist 10 Franken.",
               "notool": "Keine Ahnung.", "missed": "Bald.", "declined": "Dazu habe ich keine offizielle Quelle.",
               "gap": "Das hängt ab."}
    traces = {
        "ok": [], "error": [{"error": "RateLimitError: slow down"}], "wrong": [], "ask": [], "notool": [],
        "missed": [dict(search, result="Anfechtung innerhalb von 30 Tagen")],
        "declined": [dict(search, result='{"results":[]}')],
        "gap": [{"tool": "swiss_geo_search", "error": True, "result": "Missing required argument"}],
    }
    write_run(tmp_path / "run", rows, answers, traces)
    s = interpret.summarize(tmp_path / "run")
    causes = {q["id"]: q["cause"] for q in s["questions"]}
    assert causes == {"ok": None, "error": "api_error", "wrong": "wrong_claim", "ask": "guessed",
                      "notool": "no_tools", "missed": "found_not_used", "declined": "declined", "gap": "not_in_mcp"}
    tools = {t["tool"]: t for t in s["tools"]}
    assert tools["search_knowledge"]["empty"] == 1 and tools["swiss_geo_search"]["errors"] == 1
    text = interpret.render(s)
    assert "1/8 passed" in text and "Close coverage gaps (2 items)" in text and "swiss_geo_search calls failed" in text


def test_generic_patterns_do_not_count_as_evidence(tmp_path):
    # "\b19\b" (a day of the month) matches almost any long tool output, so it proves nothing.
    rows = [question("day", must=r"\b19\b"), question("both", must=r"30 (Tage|days)")]
    rows[1]["must_include"].append({"fact": "canton", "pattern": r"Kanton Bern"})
    search = {"tool": "search_knowledge", "error": False}
    traces = {"day": [dict(search, result="Rentrée scolaire 19 août")],
              "both": [dict(search, result="innert 30 Tagen")]}  # only one of the two missing facts
    write_run(tmp_path / "run", rows, {"day": "Weiss nicht.", "both": "Weiss nicht."}, traces)
    s = interpret.summarize(tmp_path / "run")
    assert [(q["cause"], q["evidence"]) for q in s["questions"]] == [("not_in_mcp", []), ("not_in_mcp", [])]


def test_baseline_runs_are_not_blamed_on_the_mcp(tmp_path):
    write_run(tmp_path / "run", [question("gap")], {"gap": "Das hängt ab."}, {"gap": []}, mcp=False)
    s = interpret.summarize(tmp_path / "run")
    assert s["questions"][0]["cause"] == "incomplete"
    assert any("baseline" in step for step in s["next_steps"])


def test_dashboard_serves_the_latest_run(tmp_path, monkeypatch):
    client = TestClient(dashboard.app, base_url="http://127.0.0.1")
    monkeypatch.setattr(dashboard, "BENCHMARK_RUNS", tmp_path / "runs")
    assert client.get("/api/benchmark").json() == {"run": None}

    for name in ("20260101-000000-a-mcp", "20260202-000000-b-mcp"):
        write_run(tmp_path / "runs" / name, [question("ok")], {"ok": "PASS 30 Tage"}, {"ok": []})
        interpret.interpret(tmp_path / "runs" / name)
    (tmp_path / "runs" / "20260303-000000-unfinished").mkdir()  # no summary.json yet

    run = client.get("/api/benchmark").json()["run"]
    assert run["run"] == "20260202-000000-b-mcp" and run["run_count"] == 2 and run["passed"] == 1

    page = client.get("/benchmark").text
    assert 'href="/benchmark" class="on"' in page and "/static/benchmark.js" in page
    assert 'href="/" class="on"' in client.get("/").text


def test_settings_page_saves_the_anthropic_key(tmp_path, monkeypatch):
    from mcp_swiss_info.config import env

    path = tmp_path / ".env"
    monkeypatch.setattr(env, "ENV_PATH", path)
    monkeypatch.setattr(dashboard.settings, "anthropic_api_key", None)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # restored on teardown after the endpoint sets it
    client = TestClient(dashboard.app, base_url="http://127.0.0.1", headers={"x-dashboard-token": ""})
    assert not client.get("/api/status").json()["keys"]["ANTHROPIC_API_KEY"]["set"]
    assert client.post("/api/settings", json={"ANTHROPIC_API_KEY": "sk-ant-test-9876"}).status_code == 200
    assert "ANTHROPIC_API_KEY=sk-ant-test-9876" in path.read_text()
    status = client.get("/api/status")
    assert status.json()["keys"]["ANTHROPIC_API_KEY"] == {"set": True, "hint": "...9876"}
    assert "sk-ant-test" not in status.text
    assert 'name="ANTHROPIC_API_KEY"' in client.get("/settings").text
