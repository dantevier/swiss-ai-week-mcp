"""The dashboard's shared browser helpers (time-ago text and status badges), run under Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

COMMON_JS = Path(__file__).resolve().parents[1] / "src" / "mcp_swiss_info" / "dashboard" / "static" / "common.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def evaluate(expression: str):
    script = (
        "const sessionStorage={getItem:()=>null,setItem(){}};let prompt=()=>'';\n"
        + COMMON_JS.read_text(encoding="utf-8")
        + f"\nconsole.log(JSON.stringify({expression}));"
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_ago_reads_naturally_at_every_scale():
    def ago(delta_ms):
        return evaluate(f"ago(new Date(Date.now()-{delta_ms}).toISOString())")

    minute, hour, day = 60_000, 3_600_000, 86_400_000
    assert ago(10_000) == "just now"
    assert ago(5 * minute) == "5 min ago"
    assert ago(4 * hour) == "4 h ago"
    assert ago(1 * day) == "1 day ago"
    assert ago(45 * day) == "45 days ago"
    assert ago(120 * day) == "4 months ago"


def test_badges_say_how_recent_the_data_is():
    def badge(state, delta_ms):
        last = "null" if delta_ms is None else f"new Date(Date.now()-{delta_ms}).toISOString()"
        return evaluate(f"badge({{state:'{state}',last_refresh:{last}}})")

    hour, day = 3_600_000, 86_400_000
    assert ">Updated - 4 h ago<" in badge("up_to_date", 4 * hour)
    assert ">Outdated - 45 days ago<" in badge("outdated", 45 * day)
    # The age is that of the saved copy, not of the failed attempt.
    assert ">Refresh failed - saved copy 2 days old<" in badge("failed", 2 * day)
    assert ">Never crawled<" in badge("never_crawled", None)
    assert 'class="pill up_to_date"' in badge("up_to_date", hour)
