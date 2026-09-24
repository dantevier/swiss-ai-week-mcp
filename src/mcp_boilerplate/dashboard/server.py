"""Local dashboard server: routes, request guards and the background launcher."""

import asyncio
import hmac
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ..config import env
from ..config.settings import settings
from ..crawler import Crawler
from ..sources import SOURCES
from .status import get_status

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
# Written by benchmark/run_mcp.py; each run folder holds a summary.json made by benchmark/interpret.py.
BENCHMARK_RUNS = Path(os.environ.get("BENCHMARK_RUNS_DIR", HERE.parents[2] / "benchmark" / "runs"))
TABS = [("/", "Data sources", "main"), ("/benchmark", "Benchmark", "benchmark"), ("/architecture", "Architecture", "architecture")]

# One crawl at a time: they share the SQLite file and the paid API quotas.
_crawl_lock = asyncio.Lock()
LOCAL_HOSTS = ["127.0.0.1", "localhost"]
EXTRA_HOSTS = [h for h in os.environ.get("DASHBOARD_ALLOWED_HOSTS", "").split(",") if h]


def _authorized(request: Request) -> bool:
    """Only accept writes sent by this page's own script.

    A custom header cannot be sent cross-site without a CORS preflight, which this server never
    grants, so other websites open in the browser cannot trigger writes (CSRF).
    """
    token = request.headers.get("x-dashboard-token")
    if token is None:
        return False
    expected = os.environ.get("DASHBOARD_TOKEN")
    return True if not expected else hmac.compare_digest(token, expected)


async def status(request: Request) -> JSONResponse:
    data = get_status()
    data["can_refresh"] = bool(settings.crawlora_api_key and settings.openai_api_key)
    data["keys"] = {
        "CRAWLORA_API_KEY": env.describe(settings.crawlora_api_key),
        "OPENAI_API_KEY": env.describe(settings.openai_api_key),
        "ANTHROPIC_API_KEY": env.describe(settings.anthropic_api_key),
    }
    data["needs_token"] = bool(os.environ.get("DASHBOARD_TOKEN"))
    return JSONResponse(data)


async def save_settings(request: Request) -> JSONResponse:
    if not _authorized(request):
        return JSONResponse({"error": "Invalid dashboard token"}, status_code=401)
    try:
        body = await request.json()
        updates = {k: v.strip() for k, v in body.items() if isinstance(v, str) and v.strip()}
        if not updates:
            return JSONResponse({"error": "Enter at least one key"}, status_code=400)
        env.save_env(updates)
    except (ValueError, AttributeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    # Apply now so Refresh works without restarting the dashboard.
    for name, value in updates.items():
        os.environ[name] = value
        setattr(settings, name.lower(), value)
    return JSONResponse({"saved": sorted(updates)})


async def refresh(request: Request) -> JSONResponse:
    if not _authorized(request):
        return JSONResponse({"error": "Invalid dashboard token"}, status_code=401)
    if not (settings.crawlora_api_key and settings.openai_api_key):
        return JSONResponse(
            {"error": "CRAWLORA_API_KEY and OPENAI_API_KEY must be set"}, status_code=400
        )
    level = request.path_params["level"]
    source = request.path_params["source"]
    if level not in SOURCES or (source != "all" and source not in SOURCES[level]):
        return JSONResponse({"error": "Unknown approved source"}, status_code=404)
    if _crawl_lock.locked():
        return JSONResponse({"error": "Another refresh is already running"}, status_code=409)
    async with _crawl_lock:
        try:
            result = await Crawler().crawl(level, source)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse(result)


def latest_benchmark(runs: Path | None = None) -> dict | None:
    """The most recent run's summary, or None when no run has been made yet."""
    runs = runs or BENCHMARK_RUNS
    folders = sorted(p for p in runs.iterdir() if (p / "summary.json").is_file()) if runs.is_dir() else []
    if not folders:
        return None
    summary = json.loads((folders[-1] / "summary.json").read_text(encoding="utf-8"))
    summary["folder"] = str(folders[-1])
    summary["run_count"] = len(folders)
    return summary


async def benchmark(request: Request) -> JSONResponse:
    return JSONResponse({"run": latest_benchmark()})


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _page(title: str, href: str, label: str, icon: str, body: str, script: str) -> HTMLResponse:
    tabs = "".join(
        f'<a href="{path}"' + (' class="on" aria-current="page"' if key == script else "") + f">{text}</a>"
        for path, text, key in TABS
    )
    html = (
        _template("shell.html").replace("__TABS__", tabs)
        .replace("__TITLE__", title).replace("__HREF__", href).replace("__LABEL__", label)
        .replace("__ICON__", _template(icon)).replace("__BODY__", _template(body))
        .replace("__SCRIPT__", script)
    )
    return HTMLResponse(html)


async def index(request: Request) -> HTMLResponse:
    return _page("Data sources", "/settings", "Settings", "gear.svg", "main.html", "main")


async def benchmark_page(request: Request) -> HTMLResponse:
    return _page("Benchmark", "/settings", "Settings", "gear.svg", "benchmark.html", "benchmark")


async def architecture_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_template("architecture.html"))


async def settings_page(request: Request) -> HTMLResponse:
    return _page("Settings", "/", "Back to data sources", "home.svg", "settings.html", "settings")


app = Starlette(
    routes=[
        Route("/", index),
        Route("/benchmark", benchmark_page),
        Route("/architecture", architecture_page),
        Route("/settings", settings_page),
        Route("/api/status", status),
        Route("/api/benchmark", benchmark),
        Route("/api/settings", save_settings, methods=["POST"]),
        Route("/api/refresh/{level}/{source}", refresh, methods=["POST"]),
        Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
    ],
    # Rejects requests whose Host header is not local, which blocks DNS-rebinding attacks.
    middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS + EXTRA_HOSTS)],
)


def ensure_running() -> str:
    """Start the dashboard in the background if it is not already listening; return its URL."""
    port = int(os.environ.get("DASHBOARD_PORT", "8765"))
    url = f"http://127.0.0.1:{port}"

    def listening() -> bool:
        with socket.socket() as probe:
            probe.settimeout(0.3)
            return probe.connect_ex(("127.0.0.1", port)) == 0

    if not listening():
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            [sys.executable, "-m", "mcp_boilerplate.dashboard"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, start_new_session=sys.platform != "win32",
        )
        for _ in range(30):
            if listening():
                break
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Dashboard did not start on port {port}")
    return url


def main() -> None:
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost") and not os.environ.get("DASHBOARD_TOKEN"):
        raise SystemExit("Set DASHBOARD_TOKEN before binding the dashboard to a non-local host")
    uvicorn.run(app, host=host, port=int(os.environ.get("DASHBOARD_PORT", "8765")))
