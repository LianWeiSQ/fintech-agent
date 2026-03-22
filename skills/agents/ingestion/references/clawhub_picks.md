# ClawHub Picks

- `rss-aggregator` (`installed`): best fit for `select_sources -> collect -> dedupe_raw`
- `parallel-extract` (`selected`): best fit for single-page and PDF extraction
- `deep-search` (`selected`): best fit for discover-then-collect workflows

# Activation Notes

- known source list + batch run: prefer `rss-aggregator`
- known URL + complex page: prefer `parallel-extract`
- unknown source set: run `deep-search` first

# Guardrails

- collection does not rewrite facts
- keep source failure context
- keep dedupe trace instead of silently dropping duplicates
