# Fitech Agent

Fitech Agent is a Python-first, LangGraph-oriented multi-agent pipeline for:

- collecting authority-first bilingual macro and market-moving news
- normalizing and deduplicating events
- scoring source credibility and evidence quality
- mapping events to China and global macro assets
- generating an on-demand Chinese research brief with strategy-oriented views
- storing the full research chain for replay and ex-post evaluation

<<<<<<< HEAD
The repository now ships with a precious-metals-focused source pack for live runs and
an offline demo config for local smoke tests, while keeping source adapters and model
routing interfaces pluggable.
=======
The repository keeps a single committed runtime config while leaving source and
model-routing interfaces pluggable.
>>>>>>> fe3abdd5de099e4701cdcc969ee1f8ed28ba2c43

## Overview

- Chinese project overview: `docs/project-overview.md`
- Chinese run guide: `docs/run-guide.md`

## Highlights

- 5 core agents with layered `steps/`, `runtime.py`, `prompts.py`, and per-agent `skill.md`
- LangGraph-ready orchestration with a 5-node top-level graph and a sequential fallback
- Unified LLM routing with explicit backend selection and per-agent override hooks
- SQLite-backed audit trail with both `agent_id` and `substage` traceability
- Markdown report generation and optional PDF rendering through ReportLab
- Historical replay and evaluation utilities for D0 / D1 / D5 review loops

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
python -m fitech_agent init-db
python -m fitech_agent run
python -m fitech_agent run --mode collect-only
```

<<<<<<< HEAD
`config/example.toml` is the committed authority-first source pack for gold / silver
research. If you want an offline sample run, use `config/demo.toml`, which points to
`examples/sample_news.json`.
=======
The default configuration lives at `config/config.toml`.
>>>>>>> fe3abdd5de099e4701cdcc969ee1f8ed28ba2c43

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

<<<<<<< HEAD
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
=======
- The project now keeps a single committed runtime config at `config/config.toml`.
- Keep provider credentials only in ignored local files or shell environment variables.
- The unified model interface lives under `[model_route]` with these main fields:
  `provider`, `backend`, `model`, `base_url`, `api_key_env`, `reasoning_effort`.
- `backend` currently supports:
  `auto`, `openai_responses`, `litellm`
- Future model backends should plug into this same `[model_route]` contract rather than
  introducing more `demo` / `example` / `local` config variants.
- To call a third-party OpenAI-compatible Responses gateway from the agent backend:

```toml
[model_route]
provider = "custom"
backend = "openai_responses"
model = "gpt-5.4"
base_url = "https://codex-api.packycode.com/v1"
reasoning_effort = "xhigh"
max_output_tokens = 900
api_key_env = "OPENAI_API_KEY"
```

- Quick connectivity smoke test:

```bash
uv run python scripts/test_codex_connection.py --expect MODEL_OK
```

- If you later switch to another provider or gateway, keep using the same
  `[model_route]` fields and change only `provider` / `backend` / `model` /
  `base_url` / `api_key_env`.
- The built-in trust policy recognizes these V1 trusted sources:
  `Reuters`, `Bloomberg`, `???`, `?????`, `??????`,
  `?????`, `?????`, `OPEC`, `Fed`, `CME`.
>>>>>>> fe3abdd5de099e4701cdcc969ee1f8ed28ba2c43

## LangGraph local app

```bash
langgraph dev --no-browser
```

The graph entrypoint is declared in `langgraph.json`.

## Project layout

- `config/config.toml`: single committed runtime configuration
- `examples/`: sample news and evaluation fixtures
- `spec.md`: product and implementation specification
- `src/fitech_agent/`: pipeline package
- `tests/`: unit tests focused on normalization, audit gates, and end-to-end output
