# STATUS — Swiss Grounding MCP

Current repository snapshot, checked on 24 September 2026. This file describes the
Python repository in this workspace. Other BaseKnowledge documents describe a separate
Node/TypeScript rehearsal and research plan; their reported data, tests, and coverage
are not present in this repository.

## Current stack and verified behavior

- Python 3.11+ project using FastMCP, Pydantic, and `uv` (`pyproject.toml`).
- `src/mcp_swiss_info/server.py` creates a FastMCP server named `mcp-swiss-info`.
  `src/mcp_swiss_info/main.py` starts it over stdio by default and also exposes an
  SSE option.
- The server imports and registers 20 example tools, 5 example resources, and 6
  example prompts. A direct FastMCP call to `add(2, 3)` returned `5.0` on
  24 September 2026.
- The repository has a README, `.env.example`, `Makefile`, and `uv.lock`. The README
  and package metadata still describe a generic MCP boilerplate.
- The user has also run the MCP server locally with Codex. This is a user-reported
  client check; the direct tool call above was the check performed for this snapshot.

## What is not implemented here

- No Swiss grounding tools, Swiss public-sector source data, jurisdiction resolver,
  coverage manifest, citation passages, or source refresh process are in this repo.
- None of the four topic tools or the catch-all described in `CONTRACT.md` exists in
  the Python server. The 71 coverage rows and 31 end-to-end cases reported in the
  rehearsal notes belong to a different project.
- The README does not yet declare real topic/geographic coverage, source limitations,
  or the challenge's configurable robots.txt/terms-of-use behavior.
- This repo has no verified answers for the Swisscom sample questions yet.

## Test status

`uv run --no-sync pytest -q` fails during collection: `tests/conftest.py` imports
`MCPServer` and `create_server`, which `src/mcp_swiss_info/server.py` does not define.
Other existing tests also target old `register_*_tools` functions. These tests do not
validate the current FastMCP server. No passing automated suite is claimed.

## Next work

1. Choose a small, explicit topic and geographic scope, then record it in the README.
2. Replace the example MCP surface with Swiss grounding tools that return an answer,
   the responsible authority, a supporting passage, a source URL, and relevant dates;
   ask for missing context or decline honestly when needed.
3. Replace the stale tests with one runnable MCP check for each implemented behavior.
4. Document local setup, credentials (if any), source refresh, and the robots.txt/
   terms-of-use setting and default before submission.
