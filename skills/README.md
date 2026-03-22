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

## ClawHub Selection

This repo now keeps a curated 5-agent selection manifest in `skills/clawhub_selection.toml`.

- tracked, loader-ready overlays live under `skills/agents/<agent_id>/`
- raw third-party ClawHub installs live under `skills/<slug>/` and stay gitignored
- installed in this workspace already:
  - `rss-aggregator`
  - `get-tldr`
  - `verify-claims`

To install the rest of the selected packs with Python:

```bash
python scripts/install_clawhub_agent_skills.py
```

Install only one agent's pack set:

```bash
python scripts/install_clawhub_agent_skills.py --agent report
```

If ClawHub marks a pack as suspicious and you have reviewed it locally:

```bash
python scripts/install_clawhub_agent_skills.py --agent ingestion --force-suspicious
```

Force only one reviewed pack:

```bash
python scripts/install_clawhub_agent_skills.py --force-slug parallel-extract
```

If you hit ClawHub rate limits repeatedly, authenticate first and then retry with longer backoff:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\clawhub.ps1 login
powershell -ExecutionPolicy Bypass -File .\scripts\clawhub.ps1 whoami
python scripts/install_clawhub_agent_skills.py --retry 5 --sleep-seconds 20
```

## Notes

- overlays append prompt context; they do not execute code
- prefer reviewed, local, versioned packs over untrusted marketplace content
- some marketplace installs may rate-limit temporarily; use the Python installer to retry later
