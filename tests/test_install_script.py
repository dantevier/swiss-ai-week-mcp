"""install.ps1 against stand-in claude/codex commands, a temp .env and a temp opencode config."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "install.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 is tested on Windows")


@pytest.fixture
def sandbox(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for cli in ("claude", "codex"):
        # Records its arguments; `remove` succeeds silently like the real CLIs do for unknown names.
        (bin_dir / f"{cli}.cmd").write_text(
            f'@echo off\r\necho %* >> "{tmp_path / (cli + ".args")}"\r\necho registered by fake {cli}\r\n'
        )
    return tmp_path, bin_dir


def run(sandbox, *flags, env_extra=None):
    tmp_path, bin_dir = sandbox
    system = r"C:\Windows\System32"
    env = {"PATH": f"{bin_dir};{Path(sys.executable).parent};{system};{system}\\WindowsPowerShell\\v1.0",
           "PATHEXT": ".COM;.EXE;.BAT;.CMD", "SystemRoot": r"C:\Windows", "USERPROFILE": str(tmp_path),
           "TEMP": str(tmp_path), **(env_extra or {})}
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), "-NoSync", "-Yes",
         "-EnvFile", str(tmp_path / ".env"), "-OpencodeConfig", str(tmp_path / "opencode.json"), *flags],
        capture_output=True, text=True, env=env, timeout=120,
    )


def test_registers_everywhere_saves_keys_and_is_idempotent(sandbox):
    tmp_path, _ = sandbox
    (tmp_path / ".env").write_text("# note\nLOG_LEVEL=INFO\nOPENAI_API_KEY=old\n")
    (tmp_path / "opencode.json").write_text(json.dumps({"theme": "x", "mcp": {"other": {"type": "local"}}}))
    keys = {"CRAWLORA_API_KEY": "crawl-key-123456", "OPENAI_API_KEY": "sk-should-not-replace"}

    first = run(sandbox, env_extra=keys)
    assert first.returncode == 0, first.stdout + first.stderr
    second = run(sandbox, env_extra=keys)
    assert second.returncode == 0, second.stdout + second.stderr

    # Existing key kept, missing key appended, other lines untouched.
    assert (tmp_path / ".env").read_text().splitlines() == [
        "# note", "LOG_LEVEL=INFO", "OPENAI_API_KEY=old", "CRAWLORA_API_KEY=crawl-key-123456"]
    for cli, prefix in (("claude", "mcp add --scope user mcp-swiss-info -- uv run --directory"),
                        ("codex", "mcp add mcp-swiss-info -- uv run --directory")):
        calls = (tmp_path / f"{cli}.args").read_text().splitlines()
        assert any(call.strip().startswith(prefix) and call.strip().endswith("python -m mcp_boilerplate.main")
                   for call in calls), calls
        assert any(call.strip().startswith(f"mcp remove") for call in calls)  # rerun drops the old entry first
    config = json.loads((tmp_path / "opencode.json").read_text())
    assert config["theme"] == "x" and "other" in config["mcp"]
    assert config["mcp"]["mcp-swiss-info"]["command"][:3] == ["uv", "run", "--directory"]
    assert list(config["mcp"]) == ["other", "mcp-swiss-info"]  # no duplicate after two runs


def test_rejects_unsafe_key_and_reports_uneditable_opencode_config(sandbox):
    tmp_path, _ = sandbox
    (tmp_path / "opencode.json").write_text("{ // comments make this JSONC\n}")
    result = run(sandbox, env_extra={"OPENAI_API_KEY": "bad value"})
    assert result.returncode != 0 and not (tmp_path / ".env").exists()

    result = run(sandbox)
    assert result.returncode == 1
    assert "not plain JSON" in result.stdout and "Claude Code: registered" in result.stdout


def test_uninstall_removes_every_entry(sandbox):
    tmp_path, _ = sandbox
    (tmp_path / "opencode.json").write_text("{}")
    assert run(sandbox).returncode == 0
    result = run(sandbox, "-Uninstall")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((tmp_path / "opencode.json").read_text())["mcp"] == {}
    assert "mcp remove --scope user mcp-swiss-info" in (tmp_path / "claude.args").read_text()


def test_defaults_resolve_next_to_the_script(sandbox):
    """With no -EnvFile/-OpencodeConfig, .env goes beside the script and opencode's config under the home folder."""
    import shutil

    tmp_path, bin_dir = sandbox
    copy = tmp_path / "checkout"
    copy.mkdir()
    shutil.copy(SCRIPT, copy / "install.ps1")
    config = tmp_path / ".config" / "opencode" / "opencode.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}")
    system = r"C:\Windows\System32"
    env = {"PATH": rf"{bin_dir};{system};{system}\WindowsPowerShell\v1.0", "PATHEXT": ".COM;.EXE;.BAT;.CMD",
           "SystemRoot": r"C:\Windows", "USERPROFILE": str(tmp_path), "TEMP": str(tmp_path),
           "OPENAI_API_KEY": "sk-default-123456"}
    done = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(copy / "install.ps1"), "-NoSync", "-Yes"],
        capture_output=True, text=True, env=env, timeout=120, cwd=tmp_path,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert (copy / ".env").read_text() == "OPENAI_API_KEY=sk-default-123456\n"
    assert "mcp-swiss-info" in json.loads(config.read_text())["mcp"]


def test_interactive_prompts_take_typed_keys_and_choices(sandbox):
    """No -Yes: keys are typed at the prompts (Enter skips) and each harness is answered y/n."""
    tmp_path, bin_dir = sandbox
    (tmp_path / "opencode.json").write_text("{}")
    system = r"C:\Windows\System32"
    env = {"PATH": rf"{bin_dir};{system};{system}\WindowsPowerShell\v1.0", "PATHEXT": ".COM;.EXE;.BAT;.CMD",
           "SystemRoot": r"C:\Windows", "USERPROFILE": str(tmp_path), "TEMP": str(tmp_path)}
    typed = "crawl-typed-123456\n\ny\nn\ny\n"  # Crawlora key, skip OpenAI, Claude yes, Codex no, opencode yes
    done = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), "-NoSync",
         "-EnvFile", str(tmp_path / ".env"), "-OpencodeConfig", str(tmp_path / "opencode.json")],
        input=typed, capture_output=True, text=True, env=env, timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp_path / ".env").read_text() == "CRAWLORA_API_KEY=crawl-typed-123456\n"
    assert (tmp_path / "claude.args").exists() and not (tmp_path / "codex.args").exists()
    assert "mcp-swiss-info" in json.loads((tmp_path / "opencode.json").read_text())["mcp"]
    assert "OPENAI_API_KEY: skipped" in done.stdout


def test_prefers_the_real_launcher_over_npm_ps1_shims(sandbox):
    """npm installs codex.ps1 next to codex.cmd; the .ps1 is blocked by a restrictive execution policy."""
    tmp_path, bin_dir = sandbox
    for cli in ("claude", "codex"):
        (bin_dir / f"{cli}.ps1").write_text("Write-Output 'ps1 shim used'; exit 1")
    result = run(sandbox)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ps1 shim used" not in result.stdout + result.stderr
    assert (tmp_path / "claude.args").exists() and (tmp_path / "codex.args").exists()
