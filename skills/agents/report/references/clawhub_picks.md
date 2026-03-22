# ClawHub Picks

- `ub2-markdown-report-generator` (`selected`): structured markdown report composition
- `md-to-pdf-cjk` (`selected`): Chinese-safe markdown-to-PDF output
- `market-research-reports` (`selected`): appendix and framework support

# Suggested Flow

1. generate markdown from `ResearchBrief`
2. borrow layout patterns for sections and tables
3. render PDF only when needed

# Guardrails

- do not add new facts during rendering
- keep markdown if PDF export fails
- use long-form structure for appendix, not for the core brief
