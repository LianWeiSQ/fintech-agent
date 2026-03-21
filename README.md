# Fitech Agent

Fitech Agent is a Python-first, LangGraph-oriented multi-agent pipeline for:

- collecting bilingual macro and market-moving news
- normalizing and deduplicating events
- scoring source credibility and evidence quality
- mapping events to China and global macro assets
- generating an on-demand Chinese research brief with strategy-oriented views
- storing the full research chain for replay and ex-post evaluation

The repository is bootstrapped to run out of the box with a local sample feed while
keeping live-source and model-routing interfaces pluggable.

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

The default config uses `examples/sample_news.json` so the pipeline can be exercised
without network access or provider credentials.

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
`skill.md`, `prompts.py`, `runtime.py`, and `steps/` directory.

## Live data and models

- Add RSS or file sources in `config/example.toml`.
- Set `FITECH_AGENT_CONFIG` to point LangGraph CLI at a custom config.
- Keep provider credentials only in ignored local files or shell environment variables.
- If you need model routing, put it in a local override such as `config/local.toml`,
  which is ignored by Git.
- The built-in trust policy recognizes these V1 trusted sources:
  `Reuters`, `Bloomberg`, `???`, `?????`, `??????`,
  `?????`, `?????`, `OPEC`, `Fed`, `CME`.

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
