"""Register this server in coding harnesses (Claude Code, Codex, opencode)."""

import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NAME = "mcp-swiss-info"
# --directory makes the server work from any project; the server then finds REPO/.env for API keys.
LAUNCH = ["uv", "run", "--directory", str(REPO), "python", "-m", "mcp_boilerplate.main"]
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"

CLIENTS = {"claude": "Claude Code", "codex": "Codex", "opencode": "opencode"}

_CLI = {
    "claude": ["claude", "mcp", "add", "--scope", "user", NAME, "--", *LAUNCH],
    "codex": ["codex", "mcp", "add", NAME, "--", *LAUNCH],
}


def available() -> list[str]:
    return [client for client in CLIENTS if shutil.which(client)]


def _opencode_entry() -> dict:
    return {"type": "local", "command": LAUNCH, "enabled": True}


def opencode_snippet() -> str:
    return json.dumps({"mcp": {NAME: _opencode_entry()}}, indent=2)


def install(client: str) -> str:
    """Register the server for one client and return a one-line result."""
    if client == "opencode":
        return _install_opencode()
    if client not in _CLI:
        raise ValueError(f"Unknown client: {client}")
    # Resolve the full path: on Windows, npm-installed CLIs are .cmd shims that a bare name cannot launch.
    executable = shutil.which(client)
    if executable is None:
        raise RuntimeError(f"`{client}` was not found on PATH")
    done = subprocess.run([executable, *_CLI[client][1:]], capture_output=True, text=True, timeout=60)
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0:
        raise RuntimeError(output or f"`{client}` exited with {done.returncode}")
    return output or "registered"


def _install_opencode() -> str:
    config = {}
    if OPENCODE_CONFIG.exists():
        try:
            config = json.loads(OPENCODE_CONFIG.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise RuntimeError(
                f"{OPENCODE_CONFIG} is not plain JSON; merge this in by hand:\n{opencode_snippet()}"
            ) from exc
    config.setdefault("$schema", "https://opencode.ai/config.json")
    config.setdefault("mcp", {})[NAME] = _opencode_entry()
    OPENCODE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    OPENCODE_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return f"updated {OPENCODE_CONFIG}"
