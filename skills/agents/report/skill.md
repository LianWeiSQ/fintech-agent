---
agent_id: report
version: 1
role: Chinese research brief generation and persistence
selected_clawhub_skills:
  - ub2-markdown-report-generator
  - md-to-pdf-cjk
  - market-research-reports
---

# ClawHub Overlay

`report` formats audited research into publishable artifacts.

Recommended skills:

- `ub2-markdown-report-generator`: markdown sections, tables, and layout
- `md-to-pdf-cjk`: stable Chinese PDF rendering
- `market-research-reports`: appendix structure and consulting-style long-form framing

Guidance:

- keep `ResearchBrief` as the primary schema
- use long-form report skills mainly for appendix depth
- if PDF rendering fails, keep markdown and record degradation
