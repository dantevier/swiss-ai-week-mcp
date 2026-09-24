"""The server builds the housing and driving licence databases when it starts."""

import asyncio
import json
import sqlite3
from contextlib import closing

import pytest
from fastmcp import Client

from src.mcp_boilerplate import local_databases
from src.mcp_boilerplate.config.settings import settings
from src.mcp_boilerplate.server import mcp


@pytest.fixture
def empty_paths(tmp_path, monkeypatch):
    housing, licence = tmp_path / "housing.sqlite3", tmp_path / "licence.sqlite3"
    monkeypatch.setattr(settings, "housing_db_path", str(housing))
    monkeypatch.setattr(settings, "driving_licence_db_path", str(licence))
    return housing, licence


def count(database, table: str) -> int:
    with closing(sqlite3.connect(database)) as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_server_start_builds_databases(empty_paths) -> None:
    housing, licence = empty_paths

    async def start_and_call() -> dict:
        async with Client(mcp) as client:
            result = await client.call_tool("swiss_reference_interest_rate", {"as_of": "2026-10-15"})
            return json.loads(result.content[0].text)

    assert asyncio.run(start_and_call())["status"] == "answered"
    assert count(housing, "housing_knowledge") == 65
    assert count(licence, "driving_licence_sources") == 27


def test_rebuild_is_idempotent(empty_paths) -> None:
    housing, licence = empty_paths
    local_databases.build_local_databases()
    local_databases.build_local_databases()
    assert count(housing, "housing_knowledge") == 65
    assert count(licence, "driving_licence_facts") == 216


def test_failed_import_does_not_stop_the_other(empty_paths, monkeypatch) -> None:
    housing, licence = empty_paths
    real = local_databases._import_rows

    def failing(script, database):
        if script == "import_housing":
            raise ValueError("broken seed")
        real(script, database)

    monkeypatch.setattr(local_databases, "_import_rows", failing)
    local_databases.build_local_databases()
    assert not housing.exists()
    assert count(licence, "driving_licence_sources") == 27
