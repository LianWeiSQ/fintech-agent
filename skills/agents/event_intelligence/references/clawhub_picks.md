# ClawHub Picks

- `get-tldr` (`installed`): stable URL condensation for background material
- `parallel-extract` (`selected`): body extraction before normalization and entity extraction
- `verify-claims` (`installed`): high-value claim validation
- `fact-check` (`selected`): direct structured verdict for a single claim

# Suggested Flow

1. use `parallel-extract` for clean body text
2. use `get-tldr` only for supporting context
3. run normalize and extract
4. use `verify-claims` or `fact-check` for confidence scoring

# Guardrails

- TLDR output never replaces the original article
- keep at least one validation result for critical claims
- mark low confidence explicitly when validation is missing
