# External Skill Packs

This workspace can load extra per-agent skills from `./skills`.

Supported layouts:

```text
skills/
  agents/
    market_reasoning/
      skill.md
      references/*.md
      checklists/*.md
      templates/*.md
      examples/*.md
```

or a ClawHub-style installed pack:

```text
skills/
  my-pack/
    agents/
      event_intelligence/
        skill.md
        references/*.md
```

Load order:

1. built-in `src/fitech_agent/agents/<agent_id>/skill.md`
2. direct workspace overlays under `skills/agents/<agent_id>/`
3. installed pack overlays under `skills/<pack>/agents/<agent_id>/`

Notes:

- overlays append prompt context; they do not execute code
- prefer reviewed, local, versioned packs over untrusted marketplace content
- the default ClawHub install directory is already compatible with this loader
