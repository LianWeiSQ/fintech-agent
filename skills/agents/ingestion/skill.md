---
agent_id: ingestion
version: 1
role: Manual-triggered collection orchestration
selected_clawhub_skills:
  - rss-aggregator
  - parallel-extract
  - deep-search
---

# ClawHub Overlay

This overlay gives `ingestion` three external capability groups:

- `rss-aggregator`: batch RSS collection, raw dedupe, source merging
- `parallel-extract`: clean body extraction for web pages, PDFs, and JS-heavy sites
- `deep-search`: fresh link discovery outside the default source universe

Recommended order:

1. Use `deep-search` to discover the newest or most primary source links
2. Use `rss-aggregator` for stable source lists and bulk collection
3. Use `parallel-extract` when a specific page needs full-body extraction

Constraints:

- keep `source_url`, `published_at`, and `fetched_at`
- do not summarize opinions in collection stage
- record `degraded_reason` whenever an external skill fails
