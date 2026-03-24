# Fitech Agent

Fitech Agent is a Python-first, LangGraph-oriented multi-agent pipeline for:

- collecting authority-first bilingual macro and market-moving news
- normalizing and deduplicating events
- scoring source credibility and evidence quality
- mapping events to China and global macro assets
- generating an on-demand Chinese research brief with strategy-oriented views
- storing the full research chain for replay and ex-post evaluation

The repository now ships with a precious-metals-focused source pack for live runs and
an offline demo config for local smoke tests, while keeping source adapters and model
routing interfaces pluggable.

## Overview

- Chinese project overview: `docs/project-overview.md`
- Chinese run guide: `docs/run-guide.md`

## Highlights

- 5 core agents with layered `steps/`, `runtime.py`, `prompts.py`, and per-agent `skill.md`
- LangGraph-ready orchestration with a 5-node top-level graph and a sequential fallback
- LiteLLM wrapper with shared routing plus per-agent override hooks
- SQLite-backed audit trail with both `agent_id` and `substage` traceability
- Markdown report generation and optional PDF rendering through ReportLab
- Historical replay and evaluation utilities for D0 / D1 / D5 review loops

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
python -m fitech_agent init-db --config config/example.toml
python -m fitech_agent run --config config/example.toml
python -m fitech_agent run --config config/example.toml --mode collect-only
```

`config/example.toml` is the committed authority-first source pack for gold / silver
research. If you want an offline sample run, use `config/demo.toml`, which points to
`examples/sample_news.json`.

## Manual runs

- `python -m fitech_agent run` executes the full research flow with config-driven defaults.
- Use `--mode collect-only` to collect and audit sources without generating Markdown or PDF.
- Override the window with `--triggered-at`, `--lookback-hours`, or explicit
  `--window-start` / `--window-end`.
- Narrow a run with repeated `--scope` and `--source` filters.
- `python -m fitech_agent run-daily` remains as a deprecated compatibility alias for
  `python -m fitech_agent run --mode full-report`.

## Core agents

- `ingestion`: source allowlist, collection, raw dedupe, raw evidence storage
- `event_intelligence`: normalization, extraction, translation/summarization, credibility
- `market_reasoning`: asset mapping, scope filtering, domain analysis, strategy integration
- `audit`: publishability gate, downgrade trace, degraded reason merge
- `report`: brief composition, markdown/pdf rendering, report persistence

Each core agent lives under `src/fitech_agent/agents/<agent_id>/` and carries its own
`skill.md`, `prompts.py`, `runtime.py`, `steps/`, and support files under
`references/`, `checklists/`, `templates/`, and `examples/`.

## Skill overlays and ClawHub

- Built-in agent skills load from `src/fitech_agent/agents/<agent_id>/skill.md`
- External overlay packs load from `skills/agents/<agent_id>/` and `skills/<pack>/agents/<agent_id>/`
- The workspace includes a local ClawHub wrapper at `scripts/clawhub.ps1`
- Local install command:

```bash
npm.cmd install --prefix .tools/clawhub clawhub@0.8.0
```

- Verify the CLI:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\clawhub.ps1 --help
```

- ClawHub's default install directory is already compatible with this project's overlay loader
- Review external skills before using them in research runs; overlays change prompts and heuristics

## Live data and models

- Adjust the authority-first source pack in `config/example.toml`.
- Use `config/demo.toml` when you want a fully local sample-file run.
- Set `FITECH_AGENT_CONFIG` to point LangGraph CLI at a custom config.
- Keep provider credentials only in ignored local files or shell environment variables.
- If you need model routing, put it in a local override such as `config/local.toml`,
  which is ignored by Git.
- The default product-facing source hierarchy is:
  `L1 官方锚点`, `L2 权威媒体`, `L3 精选 X`.
- The default precious-metals source pack centers on:
  `Fed`, `PBOC`, `NBS`, `CME`, `Reuters`, and curated `X` accounts such as
  `ReutersMarkets`, `BloombergMarkets`, `Nick Timiraos`, and `Javier Blas`.

## LangGraph local app

```bash
langgraph dev --no-browser
```

The graph entrypoint is declared in `langgraph.json`.

## Project layout

- `config/example.toml`: committed, credential-free example configuration
- `examples/`: sample news and evaluation fixtures
- `spec.md`: product and implementation specification
- `src/fitech_agent/`: pipeline package
- `tests/`: unit tests focused on normalization, audit gates, and end-to-end output
