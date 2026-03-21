from __future__ import annotations

from pathlib import Path

from .base import AgentSkillSpec

RESOURCE_CATEGORIES = ("references", "checklists", "templates", "examples")


def _coerce_scalar(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str, list[str]]:
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}, text.strip(), []

    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip(), []

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return {}, text.strip(), ["frontmatter_unclosed"]

    metadata: dict[str, object] = {}
    warnings: list[str] = []
    current_list_key: str | None = None
    for raw_line in lines[1:closing_index]:
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if current_list_key is None:
                warnings.append("frontmatter_orphan_list_item")
                continue
            items = metadata.setdefault(current_list_key, [])
            if isinstance(items, list):
                items.append(line.lstrip()[2:].strip())
            else:
                warnings.append(f"frontmatter_invalid_list:{current_list_key}")
            continue
        if ":" not in line:
            warnings.append(f"frontmatter_invalid_line:{line.strip()}")
            current_list_key = None
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            warnings.append("frontmatter_missing_key")
            current_list_key = None
            continue
        if value:
            metadata[key] = _coerce_scalar(value)
            current_list_key = None
        else:
            metadata[key] = []
            current_list_key = key

    body = "\n".join(lines[closing_index + 1 :]).strip()
    return metadata, body, warnings


def _find_skill_file(directory: Path) -> Path | None:
    for name in ("skill.md", "SKILL.md"):
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def _collect_resources(directory: Path) -> dict[str, list[dict[str, str]]]:
    resources: dict[str, list[dict[str, str]]] = {}
    for category in RESOURCE_CATEGORIES:
        category_dir = directory / category
        if not category_dir.exists() or not category_dir.is_dir():
            continue
        entries: list[dict[str, str]] = []
        for path in sorted(category_dir.glob("*.md")):
            entries.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "content": path.read_text(encoding="utf-8").strip(),
                }
            )
        if entries:
            resources[category] = entries
    return resources


def _merge_resources(
    base: dict[str, list[dict[str, str]]],
    incoming: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    merged = {key: list(value) for key, value in base.items()}
    for category, items in incoming.items():
        merged.setdefault(category, []).extend(items)
    return merged


class AgentSkillLoader:
    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def _candidate_overlay_dirs(
        self,
        agent_id: str,
        extra_roots: list[str] | None = None,
    ) -> list[Path]:
        roots = [Path(root) for root in (extra_roots or [])]
        resolved_roots: list[Path] = []
        for root in roots:
            if not root.is_absolute():
                root = self.workspace_root / root
            resolved_roots.append(root)

        candidates: list[Path] = []
        for root in resolved_roots:
            direct = root / agent_id
            if direct.exists():
                candidates.append(direct)
            direct_agents = root / "agents" / agent_id
            if direct_agents.exists():
                candidates.append(direct_agents)
            if root.exists():
                for child in sorted(item for item in root.iterdir() if item.is_dir()):
                    nested = child / "agents" / agent_id
                    if nested.exists():
                        candidates.append(nested)
                    nested_direct = child / agent_id
                    if nested_direct.exists():
                        candidates.append(nested_direct)
        return candidates

    def load(
        self,
        agent_id: str,
        path: str | Path,
        extra_roots: list[str] | None = None,
    ) -> AgentSkillSpec:
        base_dir = Path(path).parent
        source_paths: list[Path] = []
        warnings: list[str] = []
        metadata: dict[str, object] = {}
        resources: dict[str, list[dict[str, str]]] = {}
        bodies: list[str] = []

        builtin_skill_path = _find_skill_file(base_dir)
        if builtin_skill_path is not None:
            raw_text = builtin_skill_path.read_text(encoding="utf-8")
            parsed_metadata, body, parsed_warnings = _parse_frontmatter(raw_text)
            metadata.update(parsed_metadata)
            if body:
                bodies.append(body)
            warnings.extend(parsed_warnings)
            source_paths.append(builtin_skill_path)
            resources = _merge_resources(resources, _collect_resources(base_dir))
        else:
            warnings.append("skill_missing")

        for overlay_dir in self._candidate_overlay_dirs(agent_id, extra_roots):
            skill_path = _find_skill_file(overlay_dir)
            if skill_path is not None:
                raw_text = skill_path.read_text(encoding="utf-8")
                overlay_metadata, body, parsed_warnings = _parse_frontmatter(raw_text)
                if body:
                    pack_name = overlay_dir.parent.name if overlay_dir.parent != self.workspace_root else overlay_dir.name
                    bodies.append(f"[Overlay:{pack_name}]\n{body}")
                warnings.extend(parsed_warnings)
                metadata.update({key: value for key, value in overlay_metadata.items() if key not in metadata})
                source_paths.append(skill_path)
            resources = _merge_resources(resources, _collect_resources(overlay_dir))

        primary_path = source_paths[0] if source_paths else Path(path)
        return AgentSkillSpec(
            agent_id=agent_id,
            path=primary_path,
            exists=bool(source_paths),
            metadata=metadata,
            body="\n\n".join(part for part in bodies if part).strip(),
            source_paths=source_paths,
            resources=resources,
            warnings=warnings,
        )
