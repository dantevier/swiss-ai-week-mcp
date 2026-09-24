"""One-command setup: install dependencies, save API keys, register the MCP in your harnesses.

    uv run python scripts/setup.py            # interactive
    uv run python scripts/setup.py --yes      # no prompts; keys come from the environment
"""

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp_boilerplate import install  # noqa: E402
from mcp_boilerplate.config.env import KEYS, read_env, save_env  # noqa: E402


def save_keys(assume_yes: bool) -> None:
    current = read_env()
    updates = {}
    for key, label in KEYS.items():
        if current.get(key):
            print(f"  {key}: already set in .env")
            continue
        value = os.environ.get(key, "")
        if not value and not assume_yes:
            value = getpass.getpass(f"  {label} [Enter to skip]: ").strip()
        if value:
            updates[key] = value
        else:
            print(f"  {key}: skipped (search falls back to keywords; refresh is disabled)")
    if updates:
        save_env(updates)
        print(f"  saved {', '.join(updates)} to .env (git-ignored)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="never prompt; register in every harness found")
    args = parser.parse_args()

    print("1/3 Installing dependencies")
    subprocess.run(["uv", "sync", "--all-extras"], cwd=ROOT, check=True)

    print("2/3 API keys")
    save_keys(args.yes)

    print("3/3 Registering the MCP server")
    found = install.available()
    if not found:
        print("  No claude, codex or opencode CLI found on PATH.")
        print(f"  Run manually, e.g.: claude mcp add --scope user {install.NAME} -- {' '.join(install.LAUNCH)}")
        return 0
    failures = 0
    for client in found:
        label = install.CLIENTS[client]
        if not args.yes and input(f"  Register in {label}? [Y/n] ").strip().lower() in ("n", "no"):
            continue
        try:
            print(f"  {label}: {install.install(client)}")
        except Exception as exc:
            failures += 1
            print(f"  {label}: FAILED - {exc}")
    print("\nDone. Restart your harness, then ask: \"How fresh is your data?\"")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
