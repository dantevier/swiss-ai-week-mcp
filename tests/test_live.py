"""Live smoke tests against real upstream sources (PRD §9, S7).

Excluded by default (`addopts = "-m 'not live'"` in pyproject.toml). Run
manually before submission with `uv run pytest -m live -q`. These hit
lindas.admin.ch and amtsblattportal.ch over the network and are not part of
CI.
"""

from __future__ import annotations

import pytest

from mcp_boilerplate.tools.company_info import company_info
from mcp_boilerplate.zefix.sources.gazette import GazetteClient
from mcp_boilerplate.zefix.sources.lindas import LindasClient

UID = "CHE101654423"
UID_FORMATTED = "CHE-101.654.423"


@pytest.mark.live
@pytest.mark.asyncio
async def test_find_by_uid_live_returns_swisscom_ehraid():
    company = await LindasClient().find_by_uid(UID, budget_s=10.0)
    assert company is not None
    assert company.ehraid == 415941


@pytest.mark.live
@pytest.mark.asyncio
async def test_publications_for_uid_live_returns_hr_publication():
    pubs = await GazetteClient().publications_for_uid(
        UID, limit=5, budget_s=10.0, language="de", rubrics=["HR"]
    )
    assert len(pubs) >= 1
    assert all(p.rubric == "HR" for p in pubs)


@pytest.mark.live
@pytest.mark.asyncio
async def test_company_info_live_answers_for_known_uid():
    result = await company_info(uid=UID_FORMATTED)
    assert result["status"] == "answered"
