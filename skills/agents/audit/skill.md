---
agent_id: audit
version: 1
role: Publish gate and evidence audit
selected_clawhub_skills:
  - verify-claims
  - fact-check
  - fact-checker
---

# ClawHub Overlay

`audit` decides whether a statement is safe to publish.

Recommended skills:

- `verify-claims`: cross-check with external fact-checking organizations
- `fact-check`: direct verdict for high-risk statements
- `fact-checker`: review markdown drafts for dates, numbers, names, and causal claims

Recommended order:

1. validate core claims with `verify-claims`
2. use `fact-check` for disputed statements
3. run `fact-checker` on the final draft before publish

Constraints:

- keep downgrade trace
- unverified is not the same as false
- unsupported strong claims do not enter the final brief
