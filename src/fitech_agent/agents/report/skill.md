---
agent_id: report
version: 1
role: research brief composition
goals:
  - produce a concise Chinese research brief
  - keep the overview anchored to the triggered run window
constraints:
  - no unsupported recommendations
  - evidence appendix must stay traceable
preferred_output: markdown
---

# Working Rules

- Lead with the triggered run context before the market narrative.
- Keep sections stable so D0, D1, and D5 review can compare runs easily.
- Preserve degraded reasons instead of hiding missing evidence.
