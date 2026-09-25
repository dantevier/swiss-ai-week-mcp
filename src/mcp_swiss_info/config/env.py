"""Read and update API keys in the repository's .env file."""

import os
import re
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
KEYS = {
    "CRAWLORA_API_KEY": "Crawlora key (fetches the official pages)",
    "OPENAI_API_KEY": "OpenAI key (semantic search embeddings, benchmark runs)",
    "ANTHROPIC_API_KEY": "Anthropic key (benchmark runs with Claude)",
}
_SAFE_VALUE = re.compile(r"[^\s\"'#\\]+")


def read_env(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_PATH
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not line.lstrip().startswith("#"):
                values[key.strip()] = value.strip()
    return values


def save_env(updates: dict[str, str], path: Path | None = None) -> None:
    """Set the given keys, keeping every other line of the file as it is."""
    path = path or ENV_PATH
    for key, value in updates.items():
        if key not in KEYS:
            raise ValueError(f"Unknown setting: {key}")
        if not _SAFE_VALUE.fullmatch(value):
            raise ValueError(f"{key} must not contain spaces, quotes, # or backslashes")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(updates)
    for i, line in enumerate(lines):
        name = line.partition("=")[0].strip()
        if name in pending and not line.lstrip().startswith("#"):
            lines[i] = f"{name}={pending.pop(name)}"
    lines += [f"{key}={value}" for key, value in pending.items()]
    temp = path.with_name(path.name + ".tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temp, path)


def describe(value: str | None) -> dict:
    """Report whether a key is set without exposing more than its last four characters."""
    return {"set": bool(value), "hint": f"...{value[-4:]}" if value and len(value) >= 12 else None}
