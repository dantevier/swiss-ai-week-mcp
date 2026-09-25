"""`company_info` registration on the MCP server (docs/prd-company-info-refactor.md T4).

Follows `test_public_data_tools_are_registered`. The end-to-end call goes
through the MCP tool wrapper (`fastmcp.Client(mcp)`), so the real
`CompanyLookup()` and real source clients run; respx answers their HTTP
requests from the recorded fixtures in tests/fixtures/.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import respx
from fastmcp import Client

import mcp_swiss_info.tools  # noqa: F401 - registers every tool module on `mcp`
from mcp_swiss_info.config.settings import settings
from mcp_swiss_info.server import mcp

FIXTURES = Path(__file__).parent / "fixtures"
PARAMETERS = {"question", "name", "uid", "canton", "language", "include_publications", "max_publications"}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_company_info_is_registered() -> None:
    assert asyncio.run(mcp.get_tool("company_info")) is not None


def test_company_info_input_schema_lists_the_seven_parameters() -> None:
    tool = asyncio.run(mcp.get_tool("company_info"))
    assert set(tool.parameters["properties"]) == PARAMETERS


async def test_company_info_call_through_the_tool_wrapper_is_answered() -> None:
    uid_hit = _fixture("lindas_uid_hit.json")
    dataset_modified = _fixture("lindas_dataset_modified.json")

    def _lindas(request: httpx.Request) -> httpx.Response:
        query = parse_qs(request.content.decode())["query"][0]
        payload = dataset_modified if "dateModified" in query else uid_hit
        return httpx.Response(200, json=payload)

    with respx.mock(assert_all_called=False) as mocked:
        mocked.post(settings.lindas_endpoint).mock(side_effect=_lindas)
        mocked.get(f"{settings.gazette_base_url}/publications").respond(200, json=_fixture("gazette_search.json"))
        mocked.get(f"{settings.gazette_base_url}/rubrics").respond(200, json=_fixture("gazette_rubrics.json"))
        async with Client(mcp) as client:
            result = await client.call_tool("company_info", {"uid": "CHE-101.654.423"})

    envelope = result.structured_content
    assert envelope["status"] == "answered"
    assert envelope["company"]["uid"] == "CHE-101.654.423"
