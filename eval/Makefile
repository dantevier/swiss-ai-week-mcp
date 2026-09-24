# MCP=fastmcp|typescript|remote selects the server, e.g. `make eval-run MCP=typescript`.
MCP ?= fastmcp

# Run from eval/ (or `make -C eval <target>`). Requires: pip install -r requirements.txt and env vars set.
.PHONY: eval-run eval-run-myai eval-grade eval-report

eval-run:        ## stage-1 models (Claude, GPT, Mistral)
	python run.py --stage 1 --mcp-sets $(MCP)

eval-run-myai:   ## stage-2 models (Swisscom myAI), run last
	python run.py --stage 2 --mcp-sets $(MCP)

eval-grade:
	python grade.py

eval-report:
	python report.py
