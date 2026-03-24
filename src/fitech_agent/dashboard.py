from __future__ import annotations

from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

from .agents.registry import CORE_AGENT_DESCRIPTORS
from .config import AppConfig, SourceDefinition
from .models import RawNewsItem, ResearchRunRequest, ResearchRunResult
from .pipeline import ResearchPipeline
from .source_catalog import resolve_source_class
from .utils import compact_whitespace, parse_iso_datetime

SCOPE_META = (
    {"value": "equity", "label": "A股", "description": "指数、风格与政策受益方向"},
    {"value": "commodities", "label": "商品", "description": "工业品、农产品与供需主线"},
    {"value": "precious_metals", "label": "贵金属", "description": "黄金白银与避险链条"},
    {"value": "crude_oil", "label": "原油", "description": "原油、航运与能源扰动"},
    {"value": "usd", "label": "美元", "description": "美元指数与流动性定价"},
    {"value": "ust", "label": "美债", "description": "利率曲线与期限溢价"},
    {"value": "risk_sentiment", "label": "风险情绪", "description": "跨资产情绪切换"},
    {"value": "cn_policy", "label": "中国政策", "description": "政策脉冲与信用传导"},
    {"value": "global_macro", "label": "全球宏观", "description": "海外事件与全球再定价"},
)
BOARD_META = (
    {"id": "equities", "label": "A股", "domains": {"equities"}, "focus": "关注风险偏好与风格切换"},
    {"id": "commodities", "label": "商品", "domains": {"commodities"}, "focus": "关注供需与库存变化"},
    {"id": "precious-metals", "label": "贵金属", "domains": {"precious_metals"}, "focus": "关注实际利率、美元与避险"},
    {"id": "crude-oil", "label": "原油", "domains": {"energy"}, "focus": "关注供给扰动与库存"},
    {"id": "macro", "label": "宏观", "domains": {"macro"}, "focus": "关注美元、利率与风险传导"},
)
LEVEL_ORDER = ("L1", "L2", "L3")
LEVEL_META = {
    "L1": {"label": "L1 官方锚点", "description": "央行、交易所与统计发布，是黄金/白银主线的一手锚点"},
    "L2": {"label": "L2 权威媒体", "description": "权威财经媒体与通讯社，用于补充确认和背景解释"},
    "L3": {"label": "L3 精选 X", "description": "精选机构与记者账号，只做补充提示，不作为主证据锚点"},
}
SOURCE_CLASS_ORDER = ("official", "media", "x_selected")
SOURCE_CLASS_META = {
    "official": {"label": "官方锚点", "description": "官网、央行、交易所和统计发布"},
    "media": {"label": "权威媒体", "description": "Reuters 等权威媒体与通讯社"},
    "x_selected": {"label": "精选 X", "description": "精选机构与记者账号，作为补充提示层"},
}
WORKFLOW_STEPS = tuple((item.agent_id, item.display_name) for item in CORE_AGENT_DESCRIPTORS)


def _mode_label(mode: str) -> str:
    return {"full_report": "完整研报", "collect_only": "仅采集"}.get(mode, mode)


def _direction_label(direction: str) -> str:
    return {"bullish": "偏多", "bearish": "偏空", "neutral": "中性", "watch": "观察"}.get(direction, direction)


def _tone_for_direction(direction: str) -> str:
    return {"bullish": "positive", "bearish": "negative", "neutral": "neutral", "watch": "warning"}.get(direction, "neutral")


def _domain_label(domain: str) -> str:
    return {"equities": "A股", "commodities": "商品", "precious_metals": "贵金属", "energy": "原油", "macro": "宏观"}.get(domain, domain)


def _format_percent(value: float) -> int:
    return round(max(0.0, min(1.0, value)) * 100)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _level_rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER)


def _level_for_source_class(source_class: str) -> str:
    return {"official": "L1", "media": "L2", "x_selected": "L3"}.get(source_class, "L3")


def _normalize_level(level: str, source_class: str) -> str:
    if source_class == "x_selected":
        return "L3"
    return level if level in LEVEL_ORDER else _level_for_source_class(source_class)


def _is_same_or_newer(candidate: str, current: str) -> bool:
    if not current:
        return True
    candidate_dt = parse_iso_datetime(candidate)
    current_dt = parse_iso_datetime(current)
    if candidate_dt is None:
        return False
    if current_dt is None:
        return True
    return candidate_dt >= current_dt


class DashboardService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.pipeline = ResearchPipeline(config)
        self.source_lookup = {source.name: source for source in config.sources if source.enabled}
        self.source_catalog = self._build_source_catalog()
        self._result_cache: OrderedDict[int, dict[str, Any]] = OrderedDict()

    def bootstrap_payload(self) -> dict[str, Any]:
        snapshot = self.pipeline.llm_client.snapshot()
        return {
            "title": "Fintech Agent 研究工作台",
            "subtitle": "贵金属优先的本地研究工作台：围绕黄金、白银、利率、美元与权威来源分层展开分析。",
            "promptPlaceholder": "例如：给我一份黄金/白银盘前简报，并解释利率、美元和 COMEX 主线。",
            "quickPrompts": ["生成一份黄金/白银盘前简报", "解释美元利率如何影响黄金主线", "聚焦 Fed、PBOC、CME 与 Reuters 的贵金属信号"],
            "modes": [{"value": "full_report", "label": "完整研报"}, {"value": "collect_only", "label": "仅采集"}],
            "defaults": {"mode": self.config.run_defaults.mode, "lookbackHours": self.config.run_defaults.lookback_hours},
            "scopes": list(SCOPE_META),
            "sources": [entry for entry in (self._source_entry_from_definition(source) for source in self._sorted_sources(self.source_lookup.values())) if entry is not None],
            "sourceCatalog": self.source_catalog,
            "sourceMix": self._build_bootstrap_source_mix(),
            "workflow": [{"id": step_id, "label": label, "status": "idle", "detail": "等待运行"} for step_id, label in WORKFLOW_STEPS],
            "model": {"available": self.pipeline.llm_client.available, "resolvedModel": snapshot.get("resolved_model") or "未接入模型", "provider": snapshot.get("provider") or "local"},
            "hero": {"score": 52, "label": "等待任务", "summary": "运行后展示综合判断、L1-L3 权威来源分层和贵金属主线。"},
        }

    def run_research(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = payload or {}
        intent = compact_whitespace(str(body.get("prompt", "")))
        request = ResearchRunRequest(
            mode=self._optional_text(body.get("mode")),
            triggered_at=self._optional_text(body.get("triggeredAt")),
            lookback_hours=self._optional_int(body.get("lookbackHours")),
            window_start=self._optional_text(body.get("windowStart")),
            window_end=self._optional_text(body.get("windowEnd")),
            scopes=self._normalize_list(body.get("scopes")),
            sources=self._normalize_list(body.get("sources")),
        )
        result = self.pipeline.run(request)
        source_mix = self._build_source_mix(result)
        context = self._build_chat_context(result, intent, source_mix)
        self._remember_context(result.run_id, context)
        return {
            "meta": {"runId": result.run_id, "mode": result.mode, "modeLabel": _mode_label(result.mode), "triggeredAt": result.triggered_at, "window": {"start": result.window.start, "end": result.window.end}, "scopes": list(result.scopes), "sources": list(result.sources), "markdownPath": result.markdown_path, "pdfPath": result.pdf_path, "degradedReasons": list(result.degraded_reasons)},
            "hero": self._build_hero(result),
            "signalCards": self._build_signal_cards(result),
            "workflow": self._build_workflow(result),
            "domainBoards": self._build_domain_boards(result),
            "timeline": self._build_timeline(result),
            "events": self._build_events(result),
            "auditNotes": list(result.audit_notes),
            "watchlist": list(dict.fromkeys(result.integrated_view.watchlist))[:10],
            "reportSections": self._build_report_sections(result),
            "sourceCatalog": self.source_catalog,
            "sourceMix": source_mix,
            "assistantOpening": {"mode": "model" if self.pipeline.llm_client.available else "fallback", "text": self._generate_opening(context)},
            "chatHandle": {"runId": result.run_id},
            "marketTape": self._build_market_tape(result),
        }

    def answer_question(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = payload or {}
        question = compact_whitespace(str(body.get("question", "")))
        if not question:
            raise ValueError("question is required")
        requested_mode = compact_whitespace(str(body.get("mode", ""))).lower()
        run_id = body.get("runId")
        if not requested_mode:
            requested_mode = "run_context" if run_id is not None or isinstance(body.get("context"), dict) else "general"
        if requested_mode not in {"run_context", "general"}:
            raise ValueError("unsupported chat mode")
        if requested_mode == "general":
            context = self._build_general_context()
            return {"answer": self._generate_general_answer(question, context), "mode": "model" if self.pipeline.llm_client.available else "fallback", "chatMode": "general", "citations": context.get("citations", [])[:3], "nextPrompts": ["这个系统现在能做什么", "黄金/白银消息源怎么分层", "怎么开始一轮贵金属研究分析"]}
        context: dict[str, Any] | None = None
        if isinstance(run_id, int):
            context = self._result_cache.get(run_id)
        elif isinstance(run_id, str) and run_id.isdigit():
            context = self._result_cache.get(int(run_id))
        if context is None and isinstance(body.get("context"), dict):
            context = body["context"]
        if context is None:
            raise ValueError("run context was not found, please start a run first")
        return {"answer": self._generate_answer(question, context), "mode": "model" if self.pipeline.llm_client.available else "fallback", "chatMode": "run_context", "citations": context.get("citations", [])[:3], "nextPrompts": ["再拆一下黄金最值得盯的风险变量", "把结论改写成贵金属盘前播报口径", "只看黄金和白银应该继续盯什么"]}

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = compact_whitespace(str(value))
        return text or None

    def _optional_int(self, value: Any) -> int | None:
        return None if value in {None, ""} else int(value)

    def _normalize_list(self, value: Any) -> list[str]:
        return [text for text in (compact_whitespace(str(item)) for item in value or []) if text] if isinstance(value, list) else []

    def _sorted_sources(self, sources: Any) -> list[SourceDefinition]:
        return sorted(list(sources), key=lambda source: (-source.priority, -source.trust_score, source.name.lower()))

    def _source_class_from_definition(self, source: SourceDefinition) -> str | None:
        return resolve_source_class(
            source.name,
            source.tier,
            endpoint=source.endpoint,
            tags=list(source.tags),
        )

    def _source_class_from_item(self, item: RawNewsItem, source: SourceDefinition | None) -> str | None:
        if source is not None:
            return self._source_class_from_definition(source)
        return resolve_source_class(
            item.source,
            item.source_tier,
            endpoint=item.url,
            tags=list(item.tags),
        )

    def _level_meta(self, level: str) -> dict[str, str]:
        normalized_level = level if level in LEVEL_META else "L3"
        return LEVEL_META[normalized_level]

    def _source_entry_from_definition(
        self,
        source: SourceDefinition,
        *,
        item_count: int = 0,
        latest_title: str = "",
        latest_seen: str = "",
        authors: list[str] | None = None,
        active: bool = False,
    ) -> dict[str, Any] | None:
        source_class = self._source_class_from_definition(source)
        if source_class is None:
            return None
        confidence_level = _normalize_level(source.confidence_level, source_class)
        level_meta = self._level_meta(confidence_level)
        class_meta = SOURCE_CLASS_META[source_class]
        return {
            "name": source.name,
            "label": source.name,
            "kind": source.kind,
            "language": source.language,
            "enabled": source.enabled,
            "tags": list(source.tags),
            "tier": source.tier,
            "confidenceLevel": confidence_level,
            "confidenceLabel": level_meta["label"],
            "trustScore": _format_percent(source.trust_score),
            "sourceClass": source_class,
            "sourceClassLabel": class_meta["label"],
            "sourceClassDescription": class_meta["description"],
            "credibilityNote": f"{level_meta['label']} / {class_meta['label']}",
            "itemCount": item_count,
            "latestTitle": latest_title,
            "latestSeen": latest_seen,
            "authors": authors or [],
            "active": active,
        }

    def _sort_source_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            entries,
            key=lambda entry: (
                _level_rank(str(entry.get("confidenceLevel", "L3"))),
                -int(entry.get("itemCount", 0) or 0),
                -int(entry.get("trustScore", 0) or 0),
                str(entry.get("latestSeen", "")),
                str(entry.get("name", "")),
            ),
        )

    def _build_source_catalog(self) -> dict[str, Any]:
        level_buckets = {level: [] for level in LEVEL_ORDER}
        class_buckets = {source_class: [] for source_class in SOURCE_CLASS_ORDER}
        supported_entries: list[dict[str, Any]] = []
        for source in self._sorted_sources(self.source_lookup.values()):
            entry = self._source_entry_from_definition(source)
            if entry is None:
                continue
            supported_entries.append(entry)
            level_buckets[entry["confidenceLevel"]].append(entry)
            class_buckets[entry["sourceClass"]].append(entry)
        levels = [
            {
                "level": level,
                "label": LEVEL_META[level]["label"],
                "description": LEVEL_META[level]["description"],
                "sourceCount": len(level_buckets[level]),
                "sources": self._sort_source_entries(level_buckets[level]),
            }
            for level in LEVEL_ORDER
        ]
        classes = [
            {
                "sourceClass": source_class,
                "label": SOURCE_CLASS_META[source_class]["label"],
                "description": SOURCE_CLASS_META[source_class]["description"],
                "entryCount": len(class_buckets[source_class]),
                "itemCount": 0,
                "sourceCount": len(class_buckets[source_class]),
                "configuredSourceCount": len(class_buckets[source_class]),
                "entries": self._sort_source_entries(class_buckets[source_class]),
                "mode": "configured",
            }
            for source_class in SOURCE_CLASS_ORDER
        ]
        return {"totalSources": len(supported_entries), "levels": levels, "classes": classes}

    def _build_bootstrap_source_mix(self) -> dict[str, Any]:
        total_sources = max(1, self.source_catalog["totalSources"])
        levels: list[dict[str, Any]] = []
        top_sources: list[dict[str, Any]] = []
        for level_entry in self.source_catalog["levels"]:
            levels.append(
                {
                    "level": level_entry["level"],
                    "label": level_entry["label"],
                    "description": level_entry["description"],
                    "itemCount": 0,
                    "sourceCount": level_entry["sourceCount"],
                    "configuredSourceCount": level_entry["sourceCount"],
                    "sharePct": round(level_entry["sourceCount"] / total_sources * 100),
                    "sources": list(level_entry["sources"]),
                    "mode": "configured",
                }
            )
            top_sources.extend(level_entry["sources"])
        classes = []
        for class_entry in self.source_catalog["classes"]:
            classes.append(
                {
                    "sourceClass": class_entry["sourceClass"],
                    "label": class_entry["label"],
                    "description": class_entry["description"],
                    "itemCount": 0,
                    "sourceCount": class_entry["sourceCount"],
                    "configuredSourceCount": class_entry["configuredSourceCount"],
                    "entries": list(class_entry["entries"]),
                    "mode": "configured",
                }
            )
        top_sources = self._sort_source_entries(top_sources)
        return {
            "mode": "configured",
            "totalItems": 0,
            "distinctSources": self.source_catalog["totalSources"],
            "levels": levels,
            "topSources": top_sources[:12],
            "classes": classes,
        }

    def _build_source_mix(self, result: ResearchRunResult) -> dict[str, Any]:
        selected_sources = [self.source_lookup[name] for name in result.sources if name in self.source_lookup] or list(self.source_lookup.values())
        visible_selected_sources: list[tuple[SourceDefinition, dict[str, Any]]] = []
        selected_by_level = {level: [] for level in LEVEL_ORDER}
        selected_by_class = {source_class: [] for source_class in SOURCE_CLASS_ORDER}
        for source in self._sorted_sources(selected_sources):
            entry = self._source_entry_from_definition(source)
            if entry is None:
                continue
            visible_selected_sources.append((source, entry))
            selected_by_level[entry["confidenceLevel"]].append(source)
            selected_by_class[entry["sourceClass"]].append(source)
        level_item_counts = {level: 0 for level in LEVEL_ORDER}
        level_source_sets = {level: set() for level in LEVEL_ORDER}
        class_item_counts = {source_class: 0 for source_class in SOURCE_CLASS_ORDER}
        class_source_sets = {source_class: set() for source_class in SOURCE_CLASS_ORDER}
        source_records: dict[str, dict[str, Any]] = {}
        for item in result.raw_items:
            source = self.source_lookup.get(item.source)
            source_class = self._source_class_from_item(item, source)
            if source_class is None:
                continue
            level = _normalize_level(
                str(item.metadata.get("source_confidence_level") or (source.confidence_level if source else "")),
                source_class,
            )
            level_meta = self._level_meta(level)
            class_meta = SOURCE_CLASS_META[source_class]
            trust_score = _format_percent(_safe_float(item.metadata.get("source_trust_score"), source.trust_score if source else 0.0))
            author = compact_whitespace(str(item.metadata.get("entry_author", "")))
            seeded_record = self._source_entry_from_definition(source, active=True) if source is not None else None
            record = source_records.setdefault(
                item.source,
                seeded_record
                if seeded_record is not None
                else {
                    "name": item.source,
                    "label": item.source,
                    "kind": item.source_type,
                    "language": item.language,
                    "enabled": True,
                    "tags": list(item.tags),
                    "tier": item.source_tier,
                    "confidenceLevel": level,
                    "confidenceLabel": level_meta["label"],
                    "trustScore": trust_score,
                    "sourceClass": source_class,
                    "sourceClassLabel": class_meta["label"],
                    "sourceClassDescription": class_meta["description"],
                    "credibilityNote": f"{level_meta['label']} / {class_meta['label']}",
                    "itemCount": 0,
                    "latestTitle": "",
                    "latestSeen": "",
                    "authors": [],
                    "active": True,
                },
            )
            record["confidenceLevel"] = level
            record["confidenceLabel"] = level_meta["label"]
            record["sourceClass"] = source_class
            record["sourceClassLabel"] = class_meta["label"]
            record["sourceClassDescription"] = class_meta["description"]
            record["credibilityNote"] = f"{level_meta['label']} / {class_meta['label']}"
            record["itemCount"] = int(record.get("itemCount", 0)) + 1
            if _is_same_or_newer(item.published_at, str(record.get("latestSeen", ""))):
                record["latestSeen"] = item.published_at
                record["latestTitle"] = item.title
            if author and author not in record["authors"]:
                record["authors"].append(author)
            level_item_counts[level] += 1
            level_source_sets[level].add(item.source)
            class_item_counts[source_class] += 1
            class_source_sets[source_class].add(item.source)
        levels = []
        for level in LEVEL_ORDER:
            active_entries = self._sort_source_entries([source_records[name] for name in level_source_sets[level]])
            configured_entries = [entry for source, entry in visible_selected_sources if entry["confidenceLevel"] == level]
            source_entries = active_entries or self._sort_source_entries(configured_entries)
            levels.append(
                {
                    "level": level,
                    "label": LEVEL_META[level]["label"],
                    "description": LEVEL_META[level]["description"],
                    "itemCount": level_item_counts[level],
                    "sourceCount": len(source_entries),
                    "configuredSourceCount": len(selected_by_level[level]),
                    "sharePct": round((level_item_counts[level] / max(1, sum(class_item_counts.values()))) * 100) if sum(class_item_counts.values()) else round((len(source_entries) / max(1, len(visible_selected_sources))) * 100),
                    "sources": source_entries,
                    "mode": "active" if level_item_counts[level] else "configured",
                }
            )
        classes = []
        for source_class in SOURCE_CLASS_ORDER:
            active_entries = self._sort_source_entries([source_records[name] for name in class_source_sets[source_class]])
            configured_entries = [entry for source, entry in visible_selected_sources if entry["sourceClass"] == source_class]
            class_entries = active_entries or self._sort_source_entries(configured_entries)
            classes.append(
                {
                    "sourceClass": source_class,
                    "label": SOURCE_CLASS_META[source_class]["label"],
                    "description": SOURCE_CLASS_META[source_class]["description"],
                    "itemCount": class_item_counts[source_class],
                    "sourceCount": len(class_entries),
                    "configuredSourceCount": len(selected_by_class[source_class]),
                    "entries": class_entries[:8],
                    "mode": "active" if class_item_counts[source_class] else "configured",
                }
            )
        top_sources = self._sort_source_entries(list(source_records.values()))[:12] or self._build_bootstrap_source_mix()["topSources"]
        return {
            "mode": "active",
            "totalItems": sum(class_item_counts.values()),
            "distinctSources": len(source_records) if source_records else len(visible_selected_sources),
            "levels": levels,
            "topSources": top_sources,
            "classes": classes,
        }

    def _build_hero(self, result: ResearchRunResult) -> dict[str, Any]:
        directions = Counter(item.direction for item in result.assessments)
        average_confidence = sum(item.confidence for item in result.assessments) / len(result.assessments) if result.assessments else 0.5
        score = round(max(10, min(96, 50 + directions["bullish"] * 10 - directions["bearish"] * 9 + (average_confidence - 0.5) * 30 - len(result.degraded_reasons) * 4)))
        label = "顺势跟踪" if score >= 72 else "偏多观察" if score >= 58 else "震荡筛选" if score >= 45 else "防守优先"
        dominant_domain = _domain_label(Counter(item.domain for item in result.assessments).most_common(1)[0][0]) if result.assessments else "尚未形成主线"
        summary = f"{dominant_domain}主线占优，{directions['bullish']} 条偏多，{directions['bearish']} 条偏空，{directions['watch']} 条观察。"
        return {"score": score, "label": label, "summary": summary, "confidence": _format_percent(average_confidence), "dominantDomain": dominant_domain}

    def _build_signal_cards(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        directions = Counter(item.direction for item in result.assessments)
        hero = self._build_hero(result)
        average_credibility = sum(item.score for item in result.credibility_scores) / len(result.credibility_scores) if result.credibility_scores else 0.0
        dominant_domain = _domain_label(Counter(item.domain for item in result.assessments).most_common(1)[0][0]) if result.assessments else "尚未形成主线"
        return [{"title": "综合领先分", "value": f"{hero['score']}", "detail": hero["label"], "tone": "accent"}, {"title": "证据强度", "value": f"{_format_percent(average_credibility)}%", "detail": f"{len(result.credibility_scores)} 个事件完成可信度评估", "tone": "positive" if average_credibility >= 0.7 else "warning"}, {"title": "主导资产", "value": dominant_domain, "detail": f"{len(result.assessments)} 条市场影响判断", "tone": "neutral"}, {"title": "偏多 / 偏空", "value": f"{directions['bullish']} / {directions['bearish']}", "detail": "综合多空分布", "tone": "positive" if directions["bullish"] >= directions["bearish"] else "negative"}, {"title": "观察清单", "value": f"{len(result.integrated_view.watchlist)} 项", "detail": "重点变量与后续事件", "tone": "warning"}, {"title": "模型状态", "value": "已接入" if self.pipeline.llm_client.available else "规则回退", "detail": self.pipeline.llm_client.snapshot().get("resolved_model") or "未配置模型", "tone": "positive" if self.pipeline.llm_client.available else "neutral"}]

    def _build_workflow(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        substages = {descriptor.agent_id: " -> ".join(descriptor.substages) for descriptor in CORE_AGENT_DESCRIPTORS}
        collect_only = result.mode == "collect_only"
        return [{"id": "ingestion", "label": "Ingestion", "status": "completed", "detail": f"{len(result.raw_items)} raw items from {len(result.sources)} sources | {substages['ingestion']}"}, {"id": "event_intelligence", "label": "Event Intelligence", "status": "idle" if collect_only else "completed", "detail": "Skipped after collect-only run" if collect_only else f"{len(result.events)} canonical events | {substages['event_intelligence']}"}, {"id": "market_reasoning", "label": "Market Reasoning", "status": "idle" if collect_only else "completed", "detail": "Skipped after collect-only run" if collect_only else f"{len(result.assessments)} assessments | {substages['market_reasoning']}"}, {"id": "audit", "label": "Audit", "status": "idle" if collect_only else "completed", "detail": "Skipped after collect-only run" if collect_only else f"{len(result.audit_notes)} audit notes | {substages['audit']}"}, {"id": "report", "label": "Report", "status": "idle" if collect_only else "completed", "detail": "No report generated in collect-only mode" if collect_only else f"{_mode_label(result.mode)} output ready | {substages['report']}"}]

    def _build_domain_boards(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        boards = []
        for meta in BOARD_META:
            related = [item for item in result.assessments if item.domain in meta["domains"]]
            summary_lines = list(result.integrated_view.equity_view) if meta["id"] == "equities" else list(result.integrated_view.commodities_view) if meta["id"] == "commodities" else list(result.integrated_view.precious_metals_view) if meta["id"] == "precious-metals" else list(result.integrated_view.crude_oil_view) if meta["id"] == "crude-oil" else list(result.integrated_view.cross_asset_themes)
            items = [{"title": _domain_label(item.domain), "direction": _direction_label(item.direction), "tone": _tone_for_direction(item.direction), "confidence": _format_percent(item.confidence), "detail": item.strategy_view, "watch": " / ".join(item.watchlist[:3]) or "等待更多证据"} for item in related[:3]]
            boards.append({"id": meta["id"], "label": meta["label"], "focus": meta["focus"], "headline": summary_lines[0] if summary_lines else f"当前尚未形成明确的 {meta['label']} 主线。", "items": items or [{"title": meta["label"], "direction": "观察", "tone": "neutral", "confidence": 42, "detail": f"当前暂无高置信度的 {meta['label']} 信号，建议继续等待样本积累。", "watch": meta["focus"]}]})
        return boards

    def _build_timeline(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        return [{"time": item.published_at, "source": item.source, "title": item.title, "summary": item.summary} for item in sorted(result.raw_items, key=lambda item: item.published_at, reverse=True)[:8]]

    def _build_events(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        return [{"title": event.title, "summary": event.summary, "eventType": event.event_type, "bias": event.bias, "publishedAt": event.published_at, "evidence": [ref.source for ref in event.evidence_refs[:3]]} for event in result.events[:8]]

    def _build_report_sections(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        if result.report is None:
            return [{"title": "当前运行模式为仅采集", "items": ["本轮未生成正式简报，请切换到完整研报模式。"]}]
        return [{"title": "重点线索", "items": list(result.report.overnight_focus[:4])}, {"title": "跨资产主线", "items": list(result.report.cross_asset_themes[:4])}, {"title": "风险情景", "items": list(result.report.risk_scenarios[:4])}]

    def _build_market_tape(self, result: ResearchRunResult) -> list[str]:
        tape = list(result.integrated_view.watchlist)
        tape.extend(item.title for item in result.events[:3])
        tape.extend(result.degraded_reasons)
        return list(dict.fromkeys(filter(None, tape)))[:10]

    def _build_chat_context(self, result: ResearchRunResult, intent: str, source_mix: dict[str, Any]) -> dict[str, Any]:
        events = self._build_events(result)
        return {
            "runId": result.run_id,
            "intent": intent,
            "mode": result.mode,
            "window": f"{result.window.start} -> {result.window.end}",
            "sources": list(result.sources),
            "scopes": list(result.scopes),
            "hero": self._build_hero(result),
            "topThemes": list(result.integrated_view.cross_asset_themes[:4]),
            "domainBoards": self._build_domain_boards(result),
            "watchlist": list(dict.fromkeys(result.integrated_view.watchlist))[:10],
            "riskScenarios": list(result.integrated_view.risk_scenarios[:4]),
            "events": events,
            "sourceMixSummary": [f"{item['label']}: {item['itemCount']} 条 / {item['sourceCount']} 个来源" for item in source_mix.get("levels", [])],
            "sourceHighlights": [f"{group['label']}: {entry['name']} ({entry.get('itemCount', 0)}条)" for group in source_mix.get("classes", []) for entry in group.get("entries", [])[:2]],
            "citations": [{"title": event["title"], "source": ", ".join(event["evidence"][:2]) or "样本源"} for event in events[:3]],
            "reportText": result.report.markdown_body if result.report else "",
            "degradedReasons": list(result.degraded_reasons),
        }

    def _build_general_context(self) -> dict[str, Any]:
        level_lines = [f"{level['level']}: {level['sourceCount']} 个来源" for level in self.source_catalog.get("levels", [])]
        class_lines = [f"{item['label']}: {item['sourceCount']} 个来源" for item in self.source_catalog.get("classes", [])]
        return {
            "title": "Fintech Agent 研究工作台",
            "commands": ["init-db", "run", "run-daily", "evaluate", "serve"],
            "modes": ["full_report", "collect_only"],
            "scopes": [item["value"] for item in SCOPE_META],
            "sourceLevels": level_lines,
            "sourceClasses": class_lines,
            "totalSources": self.source_catalog.get("totalSources", 0),
            "capabilities": [
                "围绕黄金和白银主线手动发起研究运行",
                "按时间窗、scope、source 收缩分析范围",
                "按 L1/L2/L3 权威来源分层组织证据",
                "输出中文研究简报并保存审计链路",
                "对已完成运行继续追问，或做系统能力咨询",
            ],
            "citations": [
                {"title": "CLI commands", "source": "init-db, run, run-daily, evaluate, serve"},
                {"title": "消息源分层", "source": "; ".join(level_lines[:4])},
                {"title": "来源类别", "source": "; ".join(class_lines[:3])},
            ],
        }

    def _remember_context(self, run_id: int, context: dict[str, Any]) -> None:
        self._result_cache[run_id] = context
        while len(self._result_cache) > 12:
            self._result_cache.popitem(last=False)

    def resolve_report_file(self, raw_path: str) -> tuple[Path, str]:
        if not raw_path:
            raise ValueError("report path is required")
        candidate = Path(raw_path)
        candidate = (Path.cwd() / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        allowed_root = Path(self.config.report_dir)
        allowed_root = (Path.cwd() / allowed_root).resolve() if not allowed_root.is_absolute() else allowed_root.resolve()
        if not candidate.is_file():
            raise ValueError("report file not found")
        allowed = candidate == allowed_root or candidate.is_relative_to(allowed_root)
        if not allowed:
            raise ValueError("report file is outside report directory")
        content_type = "application/pdf" if candidate.suffix.lower() == ".pdf" else "text/markdown; charset=utf-8" if candidate.suffix.lower() in {".md", ".markdown"} else "application/octet-stream"
        return candidate, content_type

    def _generate_opening(self, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            response = self.pipeline.llm_client.complete_text(self.pipeline.compose_agent_system_prompt("report", "You are a Chinese trading desk research assistant. Answer only from the provided context and do not invent facts."), self._opening_prompt(context))
            if response:
                return response
        return self._fallback_opening(context)

    def _generate_answer(self, question: str, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            response = self.pipeline.llm_client.complete_text(self.pipeline.compose_agent_system_prompt("market_reasoning", "You are a Chinese trading desk research assistant. Lead with the conclusion, then the evidence, then the watch variables. Say clearly when the context is insufficient."), self._qa_prompt(question, context))
            if response:
                return response
        return self._fallback_answer(question, context)

    def _generate_general_answer(self, question: str, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            response = self.pipeline.llm_client.complete_text(self.pipeline.compose_agent_system_prompt("report", "You are a Chinese product assistant for a local research workstation. Answer only from the provided system capabilities and configuration summary. Do not claim access to live market data."), self._general_prompt(question, context))
            if response:
                return response
        return self._fallback_general_answer(question, context)

    def _opening_prompt(self, context: dict[str, Any]) -> str:
        lines = [f"用户意图: {context.get('intent') or '生成默认研究摘要'}", f"运行模式: {context.get('mode')}", f"运行窗口: {context.get('window')}", f"主导判断: {context['hero']['dominantDomain']} / {context['hero']['label']}", "L1-L3 权威来源分层:"]
        lines.extend(f"- {item}" for item in context.get("sourceMixSummary", [])[:4])
        lines.append("跨资产主线:")
        lines.extend(f"- {item}" for item in context.get("topThemes", [])[:3])
        lines.append("来源类别补充:")
        lines.extend(f"- {item}" for item in context.get("sourceHighlights", [])[:4])
        lines.append("观察清单:")
        lines.extend(f"- {item}" for item in context.get("watchlist", [])[:4])
        lines.append("请用中文输出三行：1) 主线判断 2) 证据锚点 3) 接下来要盯什么。")
        return "\n".join(lines)

    def _qa_prompt(self, question: str, context: dict[str, Any]) -> str:
        lines = [f"问题: {question}", f"运行模式: {context.get('mode')}", f"运行窗口: {context.get('window')}", f"主导判断: {context['hero']['dominantDomain']} / {context['hero']['label']}", "L1-L3 权威来源分层:"]
        lines.extend(f"- {item}" for item in context.get("sourceMixSummary", [])[:4])
        lines.append("跨资产主线:")
        lines.extend(f"- {item}" for item in context.get("topThemes", [])[:4])
        lines.append("分领域视角:")
        for board in context.get("domainBoards", [])[:5]:
            lines.append(f"[{board['label']}] {board['headline']}")
            for item in board.get("items", [])[:2]:
                lines.append(f"- {item['direction']} | 置信度 {item['confidence']} | {item['detail']}")
        lines.append("事件证据:")
        for event in context.get("events", [])[:3]:
            lines.append(f"- {event['title']} | {event['summary']} | 证据: {', '.join(event['evidence'])}")
        lines.append("来源类别补充:")
        lines.extend(f"- {item}" for item in context.get("sourceHighlights", [])[:4])
        lines.append("风险与观察:")
        lines.extend(f"- {item}" for item in context.get("watchlist", [])[:5])
        lines.append("请只基于以上上下文作答。")
        return "\n".join(lines)

    def _fallback_opening(self, context: dict[str, Any]) -> str:
        theme = (context.get("topThemes") or ["当前尚未形成明确的跨资产主线。"])[0]
        watch = (context.get("watchlist") or ["继续等待更多样本沉淀。"])[0]
        source_mix = "；".join(context.get("sourceMixSummary", [])[:2]) or "暂无来源分层摘要"
        return f"主线判断：{theme}\n证据锚点：当前主导方向是 {context['hero']['dominantDomain']}，综合领先分数 {context['hero']['score']}，来源分层摘要为 {source_mix}。\n下一步：先盯住 {watch}，再结合权威来源分层决定是否继续追问。"

    def _fallback_answer(self, question: str, context: dict[str, Any]) -> str:
        lowered = question.lower()
        if "风险" in question:
            risks = context.get("riskScenarios") or context.get("watchlist") or ["暂无新增风险情景。"]
            watchlist = "；".join(context.get("watchlist", [])[:4]) or "继续等待更多样本"
            return f"结论：当前最需要盯的是风险变量，而不是单一方向。\n证据：{'；'.join(risks[:3])}\n观察变量：{watchlist}"
        board_lookup = {board['id']: board for board in context.get("domainBoards", [])}
        if "黄金" in question or "贵金属" in question:
            board = board_lookup.get("precious-metals")
            if board:
                return self._board_answer("贵金属", board)
        if "原油" in question or "能源" in question:
            board = board_lookup.get("crude-oil")
            if board:
                return self._board_answer("原油", board)
        if "a股" in lowered or "股" in question:
            board = board_lookup.get("equities")
            if board:
                return self._board_answer("A股", board)
        if "商品" in question or "期货" in question:
            board = board_lookup.get("commodities")
            if board:
                return self._board_answer("商品", board)
        event = (context.get("events") or [{"title": "暂无事件", "summary": "请先发起一轮研究。"}])[0]
        theme = (context.get("topThemes") or ["当前尚未形成明确的跨资产主线。"])[0]
        watchlist = "；".join(context.get("watchlist", [])[:4]) or "继续等待更多样本"
        return f"结论：{theme}\n证据：当前最关键的事件是“{event['title']}”，摘要为：{event['summary']}\n观察变量：{watchlist}"

    def _board_answer(self, label: str, board: dict[str, Any]) -> str:
        item = board.get("items", [{}])[0]
        return f"结论：{label}维持{item.get('direction', '观察')}思路。\n证据：{board.get('headline')}\n观察变量：{item.get('watch') or board.get('focus')}"

    def _general_prompt(self, question: str, context: dict[str, Any]) -> str:
        lines = [f"问题: {question}", f"系统: {context['title']}", f"支持命令: {', '.join(context.get('commands', []))}", f"运行模式: {', '.join(context.get('modes', []))}", f"支持 scope: {', '.join(context.get('scopes', []))}", f"总消息源数: {context.get('totalSources', 0)}", "能力概览:"]
        lines.extend(f"- {item}" for item in context.get("capabilities", []))
        lines.append("来源分层:")
        lines.extend(f"- {item}" for item in context.get("sourceLevels", []))
        lines.append("来源类别:")
        lines.extend(f"- {item}" for item in context.get("sourceClasses", []))
        lines.append("请只基于这些能力和配置作答，不要声称有实时行情或联网能力。")
        return "\n".join(lines)

    def _fallback_general_answer(self, question: str, context: dict[str, Any]) -> str:
        lowered = question.lower()
        if any(keyword in question for keyword in ("功能", "能做什么", "模块")):
            return f"当前系统具备这些能力：{'；'.join(context.get('capabilities', []))}。常用入口包括 {', '.join(context.get('commands', []))}。"
        if any(keyword in question for keyword in ("消息源", "来源", "source")):
            return f"当前共配置 {context.get('totalSources', 0)} 个消息源。来源按分层管理：{'；'.join(context.get('sourceLevels', []))}。来源类别包括 {'；'.join(context.get('sourceClasses', []))}。"
        if any(keyword in lowered for keyword in ("怎么用", "如何", "开始", "使用")):
            return "建议这样开始：先用 init-db 初始化数据库，再用 run 发起研究，需要看本地界面时用 serve，做事后评估时用 evaluate。"
        return f"{context['title']} 目前是一个本地研究工作台。它支持 {', '.join(context.get('modes', []))} 两种运行模式，可覆盖 {len(context.get('scopes', []))} 个研究 scope，也支持对已完成运行继续追问。"
