# News Employee

News Employee is a Python-first, LangGraph-oriented multi-agent pipeline for:

- collecting bilingual macro and market-moving news
- normalizing and deduplicating events
- scoring source credibility and evidence quality
- mapping events to China and global macro assets
- generating a daily Chinese pre-market brief with strategy-oriented views
- storing the full research chain for replay and ex-post evaluation

The repository is bootstrapped to run out of the box with a local sample feed while
keeping live-source and model-routing interfaces pluggable.

## Highlights

- 9 explicit agents matching the product spec
- LangGraph-ready orchestration with a sequential fallback for local development
- LiteLLM wrapper with rule-based fallbacks when no model key is configured
- SQLite-backed audit trail for raw news, events, assessments, reports, and outcomes
- Markdown report generation and optional PDF rendering through ReportLab
- Historical replay and evaluation utilities for D0 / D1 / D5 review loops

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
news-employee init-db --config config/example.toml
news-employee run-daily --config config/example.toml
```

The default config uses `examples/sample_news.json` so the pipeline can be exercised
without network access or API keys.

## Live data and models

- Add RSS or file sources in `config/example.toml`.
- Set `NEWS_EMPLOYEE_CONFIG` to point LangGraph CLI at a custom config.
- Configure a LiteLLM-compatible model in `[model_route]` and set the matching API key
  in your environment if you want LLM translation or summarization.

## LangGraph local app

```bash
langgraph dev --no-browser
```

The graph entrypoint is declared in `langgraph.json`.

## Project layout

- `config/example.toml`: runnable configuration
- `examples/`: sample news and evaluation fixtures
- `spec.md`: product and implementation specification
- `src/news_employee/`: pipeline package
- `tests/`: unit tests focused on normalization, audit gates, and end-to-end output

