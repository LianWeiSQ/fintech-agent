---
agent_id: event_intelligence
version: 1
role: Event understanding and credibility extraction
selected_clawhub_skills:
  - get-tldr
  - parallel-extract
  - verify-claims
  - fact-check
---

# ClawHub Overlay

`event_intelligence` turns raw news into structured events, claims, entities, dates, and numbers.

Recommended skills:

- `parallel-extract`: clean the source article before extraction
- `get-tldr`: condense low-risk background links
- `verify-claims`: validate key numbers, policy wording, and macro claims
- `fact-check`: use when a direct verdict is needed

Constraints:

- preserve dates, numbers, entities, and source trace
- distinguish unverified from disproven
- summaries support extraction but do not replace evidence
