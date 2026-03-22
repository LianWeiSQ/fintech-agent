from __future__ import annotations

from collections import Counter, OrderedDict
from typing import Any

from .agents.registry import CORE_AGENT_DESCRIPTORS
from .config import AppConfig, SourceDefinition
from .models import RawNewsItem, ResearchRunRequest, ResearchRunResult
from .pipeline import ResearchPipeline
from .utils import compact_whitespace, parse_iso_datetime

SCOPE_META: tuple[dict[str, str], ...] = (
    {"value": "equity", "label": "A股", "description": "指数、风格与政策受益方向"},
    {"value": "commodities", "label": "商品期货", "description": "黑色、化工与农产品主线"},
    {"value": "precious_metals", "label": "贵金属", "description": "黄金白银与避险链条"},
    {"value": "crude_oil", "label": "原油能源", "description": "原油、航运与供给扰动"},
    {"value": "usd", "label": "美元", "description": "美元指数与流动性定价"},
    {"value": "ust", "label": "美债", "description": "利率曲线与期限溢价"},
    {"value": "risk_sentiment", "label": "风险偏好", "description": "跨资产情绪切换"},
    {"value": "cn_policy", "label": "中国政策", "description": "政策脉冲与信用传导"},
    {"value": "global_macro", "label": "全球宏观", "description": "海外事件与全球再定价"},
)

BOARD_META: tuple[dict[str, Any], ...] = (
    {"id": "equities", "label": "A股", "domains": {"equities"}, "focus": "盯风险偏好、政策催化与风格切换。"},
    {"id": "commodities", "label": "商品", "domains": {"commodities"}, "focus": "盯供需、库存与跨品种联动。"},
    {"id": "precious-metals", "label": "贵金属", "domains": {"precious_metals"}, "focus": "盯实际利率、美元和避险需求。"},
    {"id": "crude-oil", "label": "原油", "domains": {"energy"}, "focus": "盯供给扰动、航运风险和库存变化。"},
    {"id": "macro", "label": "宏观", "domains": {"macro"}, "focus": "盯美元、利率与跨资产风险传导。"},
)

LEVEL_ORDER: tuple[str, ...] = ("L1", "L2", "L3", "L4")
LEVEL_META: dict[str, dict[str, str]] = {
    "L1": {"label": "L1 官方与监管", "description": "央行、交易所、统计局等一手锚点。"},
    "L2": {"label": "L2 顶级通讯社", "description": "Reuters、Bloomberg 等全球基准线。"},
    "L3": {"label": "L3 专业财经媒体", "description": "WSJ、Caixin 等专业加工层。"},
    "L4": {"label": "L4 社区与情绪场", "description": "X、Reddit 等情绪与线索补充层。"},
}
CHANNEL_META: dict[str, dict[str, str]] = {
    "x": {"label": "X", "description": "高信号账号与记者流"},
    "reddit": {"label": "Reddit", "description": "高质量社区帖子与作者"},
    "rss": {"label": "RSS", "description": "站点 RSS / 官方 feed"},
    "file": {"label": "File", "description": "本地样本或离线输入"},
}
WORKFLOW_STEPS: tuple[tuple[str, str], ...] = tuple(
    (descriptor.agent_id, descriptor.display_name) for descriptor in CORE_AGENT_DESCRIPTORS
)


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
            "title": "Fintech Agent 控制台",
            "subtitle": "面向多资产研究流的可视化研究驾驶舱。",
            "promptPlaceholder": "例如：请生成一份盘前简报，重点解释黄金、原油与 A 股之间的联动。",
            "quickPrompts": ["生成盘前多资产简报", "解释当前最强主线和最弱主线", "聚焦贵金属与原油的风险传导"],
            "modes": [{"value": "full_report", "label": "完整研报"}, {"value": "collect_only", "label": "仅采集"}],
            "defaults": {"mode": self.config.run_defaults.mode, "lookbackHours": self.config.run_defaults.lookback_hours},
            "scopes": list(SCOPE_META),
            "sources": [self._source_entry_from_definition(source) for source in self._sorted_sources(self.source_lookup.values())],
            "sourceCatalog": self.source_catalog,
            "sourceMix": self._build_bootstrap_source_mix(),
            "workflow": [{"id": step_id, "label": label, "status": "idle", "detail": "等待运行"} for step_id, label in WORKFLOW_STEPS],
            "model": {
                "available": self.pipeline.llm_client.available,
                "resolvedModel": snapshot.get("resolved_model") or "未配置模型",
                "provider": snapshot.get("provider") or "local",
            },
            "hero": {"score": 52, "label": "等待任务", "summary": "运行后直接展示 L1-L4 source mix、热点来源和 X / Reddit 高信号账号。"},
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
            "meta": {
                "runId": result.run_id,
                "mode": result.mode,
                "modeLabel": _mode_label(result.mode),
                "triggeredAt": result.triggered_at,
                "window": {"start": result.window.start, "end": result.window.end},
                "scopes": list(result.scopes),
                "sources": list(result.sources),
                "markdownPath": result.markdown_path,
                "pdfPath": result.pdf_path,
                "degradedReasons": list(result.degraded_reasons),
            },
            "hero": self._build_hero(result),
            "signalCards": self._build_signal_cards(result),
            "workflow": self._build_workflow(result),
            "domainBoards": self._build_domain_boards(result),
            "timeline": self._build_timeline(result),
            "events": self._build_events(result),
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
        run_id = body.get("runId")
        context: dict[str, Any] | None = None
        if isinstance(run_id, int):
            context = self._result_cache.get(run_id)
        elif isinstance(run_id, str) and run_id.isdigit():
            context = self._result_cache.get(int(run_id))
        if context is None and isinstance(body.get("context"), dict):
            context = body["context"]
        if context is None:
            raise ValueError("run context was not found, please start a run first")
        return {
            "answer": self._generate_answer(question, context),
            "mode": "model" if self.pipeline.llm_client.available else "fallback",
            "citations": context.get("citations", [])[:3],
            "nextPrompts": ["再拆一下最值得盯的风险变量", "把结论改写成盘前播报口径", "只看商品和贵金属应该怎么交易"],
        }

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = compact_whitespace(str(value))
        return text or None

    def _optional_int(self, value: Any) -> int | None:
        return None if value in {None, ""} else int(value)

    def _normalize_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for text in (compact_whitespace(str(item)) for item in value) if text]

    def _sorted_sources(self, sources: Any) -> list[SourceDefinition]:
        return sorted(list(sources), key=lambda source: (-source.priority, -source.trust_score, source.name.lower()))

    def _source_channel_from_definition(self, source: SourceDefinition) -> str:
        endpoint = source.endpoint.lower()
        tags = {tag.lower() for tag in source.tags}
        if "reddit" in endpoint or "reddit" in tags:
            return "reddit"
        if "twitter" in endpoint or "x.com" in endpoint or "x" in tags:
            return "x"
        if source.kind == "file":
            return "file"
        return "rss"

    def _source_channel_from_item(self, item: RawNewsItem, source: SourceDefinition | None) -> str:
        if source is not None:
            return self._source_channel_from_definition(source)
        tags = {tag.lower() for tag in item.tags}
        if "reddit" in tags or "reddit.com" in (item.url or "").lower():
            return "reddit"
        if "x" in tags or "twitter" in (item.url or "").lower() or "x.com" in (item.url or "").lower():
            return "x"
        if item.source_type == "file":
            return "file"
        return "rss"

    def _source_entry_from_definition(self, source: SourceDefinition, *, item_count: int = 0, latest_title: str = "", latest_seen: str = "", authors: list[str] | None = None, active: bool = False) -> dict[str, Any]:
        channel = self._source_channel_from_definition(source)
        return {
            "name": source.name,
            "label": source.name,
            "kind": source.kind,
            "language": source.language,
            "enabled": source.enabled,
            "tags": list(source.tags),
            "tier": source.tier,
            "confidenceLevel": source.confidence_level,
            "confidenceLabel": LEVEL_META.get(source.confidence_level, LEVEL_META["L4"])["label"],
            "trustScore": _format_percent(source.trust_score),
            "channel": channel,
            "channelLabel": CHANNEL_META[channel]["label"],
            "itemCount": item_count,
            "latestTitle": latest_title,
            "latestSeen": latest_seen,
            "authors": authors or [],
            "active": active,
        }

    def _build_source_catalog(self) -> dict[str, Any]:
        level_buckets = {level: [] for level in LEVEL_ORDER}
        channel_buckets = {"x": [], "reddit": []}
        for source in self._sorted_sources(self.source_lookup.values()):
            entry = self._source_entry_from_definition(source)
            level_buckets[source.confidence_level].append(entry)
            if entry["channel"] in channel_buckets:
                channel_buckets[entry["channel"]].append(entry)
        levels = [
            {
                "level": level,
                "label": LEVEL_META[level]["label"],
                "description": LEVEL_META[level]["description"],
                "sourceCount": len(level_buckets[level]),
                "sources": level_buckets[level],
            }
            for level in LEVEL_ORDER
        ]
        channels = [
            {
                "channel": channel,
                "label": f"{CHANNEL_META[channel]['label']} 监控名单",
                "description": CHANNEL_META[channel]["description"],
                "entryCount": len(channel_buckets[channel]),
                "entries": channel_buckets[channel],
                "posts": [],
                "mode": "configured",
            }
            for channel in ("x", "reddit")
        ]
        return {"totalSources": len(self.source_lookup), "levels": levels, "channels": channels}

    def _build_bootstrap_source_mix(self) -> dict[str, Any]:
        total_sources = max(1, self.source_catalog["totalSources"])
        levels = []
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
        top_sources.sort(key=lambda entry: (_level_rank(str(entry.get("confidenceLevel", "L4"))), -int(entry.get("trustScore", 0) or 0), str(entry.get("name", ""))))
        return {
            "mode": "configured",
            "totalItems": 0,
            "distinctSources": self.source_catalog["totalSources"],
            "levels": levels,
            "topSources": top_sources[:12],
            "channels": self.source_catalog["channels"],
        }

    def _build_source_mix(self, result: ResearchRunResult) -> dict[str, Any]:
        selected_sources = [self.source_lookup[name] for name in result.sources if name in self.source_lookup] or list(self.source_lookup.values())
        selected_by_level = {level: [] for level in LEVEL_ORDER}
        for source in self._sorted_sources(selected_sources):
            selected_by_level[source.confidence_level].append(source)

        level_item_counts = {level: 0 for level in LEVEL_ORDER}
        level_source_sets = {level: set() for level in LEVEL_ORDER}
        source_records: dict[str, dict[str, Any]] = {}
        social_entities: dict[str, dict[str, dict[str, Any]]] = {"x": {}, "reddit": {}}
        social_posts: dict[str, list[dict[str, Any]]] = {"x": [], "reddit": []}

        for item in result.raw_items:
            source = self.source_lookup.get(item.source)
            level = str(item.metadata.get("source_confidence_level") or (source.confidence_level if source else "L4"))
            level = level if level in LEVEL_META else "L4"
            channel = self._source_channel_from_item(item, source)
            trust_score = _format_percent(_safe_float(item.metadata.get("source_trust_score"), source.trust_score if source else 0.0))
            author = compact_whitespace(str(item.metadata.get("entry_author", "")))
            record = source_records.setdefault(
                item.source,
                self._source_entry_from_definition(source, active=True) if source is not None else {
                    "name": item.source,
                    "label": item.source,
                    "kind": item.source_type,
                    "language": item.language,
                    "enabled": True,
                    "tags": list(item.tags),
                    "tier": item.source_tier,
                    "confidenceLevel": level,
                    "confidenceLabel": LEVEL_META[level]["label"],
                    "trustScore": trust_score,
                    "channel": channel,
                    "channelLabel": CHANNEL_META[channel]["label"],
                    "itemCount": 0,
                    "latestTitle": "",
                    "latestSeen": "",
                    "authors": [],
                    "active": True,
                },
            )
            record["itemCount"] = int(record.get("itemCount", 0)) + 1
            if _is_same_or_newer(item.published_at, str(record.get("latestSeen", ""))):
                record["latestSeen"] = item.published_at
                record["latestTitle"] = item.title
            if author and author not in record["authors"]:
                record["authors"].append(author)

            level_item_counts[level] += 1
            level_source_sets[level].add(item.source)

            if channel in {"x", "reddit"}:
                entity_name = author or item.source
                entity_record = social_entities[channel].setdefault(
                    entity_name,
                    {
                        "name": entity_name,
                        "handle": entity_name,
                        "level": level,
                        "levelLabel": LEVEL_META[level]["label"],
                        "trustScore": trust_score,
                        "itemCount": 0,
                        "sources": [],
                        "latestTitle": "",
                        "latestSeen": "",
                    },
                )
                entity_record["itemCount"] += 1
                if item.source not in entity_record["sources"]:
                    entity_record["sources"].append(item.source)
                if _is_same_or_newer(item.published_at, str(entity_record["latestSeen"])):
                    entity_record["latestSeen"] = item.published_at
                    entity_record["latestTitle"] = item.title
                if _level_rank(level) < _level_rank(str(entity_record["level"])):
                    entity_record["level"] = level
                    entity_record["levelLabel"] = LEVEL_META[level]["label"]
                entity_record["trustScore"] = max(int(entity_record["trustScore"]), trust_score)
                social_posts[channel].append(
                    {
                        "title": item.title,
                        "source": item.source,
                        "author": entity_name,
                        "level": level,
                        "levelLabel": LEVEL_META[level]["label"],
                        "trustScore": trust_score,
                        "publishedAt": item.published_at,
                        "url": item.url,
                    }
                )

        levels = []
        for level in LEVEL_ORDER:
            active_entries = sorted(
                [source_records[name] for name in level_source_sets[level]],
                key=lambda entry: (-int(entry.get("itemCount", 0)), -int(entry.get("trustScore", 0)), str(entry.get("latestSeen", "")), str(entry.get("name", ""))),
            )
            source_entries = active_entries or [self._source_entry_from_definition(source) for source in selected_by_level[level]]
            levels.append(
                {
                    "level": level,
                    "label": LEVEL_META[level]["label"],
                    "description": LEVEL_META[level]["description"],
                    "itemCount": level_item_counts[level],
                    "sourceCount": len(source_entries),
                    "configuredSourceCount": len(selected_by_level[level]),
                    "sharePct": round((level_item_counts[level] / len(result.raw_items)) * 100) if result.raw_items else round((len(source_entries) / max(1, len(selected_sources))) * 100),
                    "sources": source_entries,
                    "mode": "active" if level_item_counts[level] else "configured",
                }
            )

        channels = []
        for channel in ("x", "reddit"):
            entries = sorted(
                social_entities[channel].values(),
                key=lambda entry: (-int(entry.get("itemCount", 0)), _level_rank(str(entry.get("level", "L4"))), -int(entry.get("trustScore", 0)), str(entry.get("latestSeen", ""))),
            )
            posts = sorted(
                social_posts[channel],
                key=lambda entry: (_level_rank(str(entry.get("level", "L4"))), -int(entry.get("trustScore", 0)), str(entry.get("publishedAt", ""))),
            )
            if not entries and not posts:
                configured = next((item for item in self.source_catalog["channels"] if item["channel"] == channel), None)
                channels.append(
                    {
                        "channel": channel,
                        "label": f"{CHANNEL_META[channel]['label']} 热点",
                        "description": CHANNEL_META[channel]["description"],
                        "entryCount": 0,
                        "entries": configured["entries"] if configured else [],
                        "posts": [],
                        "mode": "configured",
                    }
                )
            else:
                channels.append(
                    {
                        "channel": channel,
                        "label": f"{CHANNEL_META[channel]['label']} 热点",
                        "description": CHANNEL_META[channel]["description"],
                        "entryCount": len(entries),
                        "entries": entries[:8],
                        "posts": posts[:8],
                        "mode": "active",
                    }
                )

        return {
            "mode": "active",
            "totalItems": len(result.raw_items),
            "distinctSources": len(source_records) if source_records else len(selected_sources),
            "levels": levels,
            "topSources": sorted(source_records.values(), key=lambda entry: (-int(entry.get("itemCount", 0)), _level_rank(str(entry.get("confidenceLevel", "L4"))), -int(entry.get("trustScore", 0))))[:12] or self._build_bootstrap_source_mix()["topSources"],
            "channels": channels,
        }

    def _build_hero(self, result: ResearchRunResult) -> dict[str, Any]:
        directions = Counter(item.direction for item in result.assessments)
        average_confidence = sum(item.confidence for item in result.assessments) / len(result.assessments) if result.assessments else 0.5
        score = round(max(10, min(96, 50 + directions["bullish"] * 10 - directions["bearish"] * 9 + (average_confidence - 0.5) * 30 - len(result.degraded_reasons) * 4)))
        if score >= 72:
            label = "顺势跟踪"
        elif score >= 58:
            label = "偏多观察"
        elif score >= 45:
            label = "震荡筛选"
        else:
            label = "防守优先"
        dominant_domain = _domain_label(Counter(item.domain for item in result.assessments).most_common(1)[0][0]) if result.assessments else "未形成主线"
        summary = f"{dominant_domain}主线占优，{directions['bullish']} 条偏多，{directions['bearish']} 条偏空，{directions['watch']} 条观察。"
        return {"score": score, "label": label, "summary": summary, "confidence": _format_percent(average_confidence), "dominantDomain": dominant_domain}

    def _build_signal_cards(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        directions = Counter(item.direction for item in result.assessments)
        hero = self._build_hero(result)
        average_credibility = sum(item.score for item in result.credibility_scores) / len(result.credibility_scores) if result.credibility_scores else 0.0
        dominant_domain = _domain_label(Counter(item.domain for item in result.assessments).most_common(1)[0][0]) if result.assessments else "未形成主线"
        return [
            {"title": "多空领先指标", "value": f"{hero['score']}", "detail": hero["label"], "tone": "accent"},
            {"title": "证据强度", "value": f"{_format_percent(average_credibility)}%", "detail": f"{len(result.credibility_scores)} 个事件完成评分", "tone": "positive" if average_credibility >= 0.7 else "warning"},
            {"title": "主导资产", "value": dominant_domain, "detail": f"{len(result.assessments)} 条市场影响判断", "tone": "neutral"},
            {"title": "偏多 / 偏空", "value": f"{directions['bullish']} / {directions['bearish']}", "detail": "综合多空分布", "tone": "positive" if directions["bullish"] >= directions["bearish"] else "negative"},
            {"title": "观察清单", "value": f"{len(result.integrated_view.watchlist)} 项", "detail": "重点变量与事件跟踪", "tone": "warning"},
            {"title": "模型状态", "value": "已接入" if self.pipeline.llm_client.available else "规则回退", "detail": self.pipeline.llm_client.snapshot().get("resolved_model") or "未配置模型", "tone": "positive" if self.pipeline.llm_client.available else "neutral"},
        ]

    def _build_workflow(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        substage_lookup = {descriptor.agent_id: " -> ".join(descriptor.substages) for descriptor in CORE_AGENT_DESCRIPTORS}
        collect_only = result.mode == "collect_only"
        return [
            {"id": "ingestion", "label": "Ingestion", "status": "completed", "detail": f"{len(result.raw_items)} raw items from {len(result.sources)} sources | {substage_lookup['ingestion']}"},
            {"id": "event_intelligence", "label": "Event Intelligence", "status": "idle" if collect_only else "completed", "detail": "Skipped after collect-only run" if collect_only else f"{len(result.events)} canonical events | {substage_lookup['event_intelligence']}"},
            {"id": "market_reasoning", "label": "Market Reasoning", "status": "idle" if collect_only else "completed", "detail": "Skipped after collect-only run" if collect_only else f"{len(result.assessments)} assessments | {substage_lookup['market_reasoning']}"},
            {"id": "audit", "label": "Audit", "status": "idle" if collect_only else "completed", "detail": "Skipped after collect-only run" if collect_only else f"{len(result.audit_notes)} audit notes | {substage_lookup['audit']}"},
            {"id": "report", "label": "Report", "status": "idle" if collect_only else "completed", "detail": "No report generated in collect-only mode" if collect_only else f"{_mode_label(result.mode)} output ready | {substage_lookup['report']}"},
        ]

    def _build_domain_boards(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        boards: list[dict[str, Any]] = []
        for meta in BOARD_META:
            related = [item for item in result.assessments if item.domain in meta["domains"]]
            if meta["id"] == "equities":
                summary_lines = list(result.integrated_view.equity_view)
            elif meta["id"] == "commodities":
                summary_lines = list(result.integrated_view.commodities_view)
            elif meta["id"] == "precious-metals":
                summary_lines = list(result.integrated_view.precious_metals_view)
            elif meta["id"] == "crude-oil":
                summary_lines = list(result.integrated_view.crude_oil_view)
            else:
                summary_lines = list(result.integrated_view.cross_asset_themes)
            items = [
                {
                    "title": _domain_label(item.domain),
                    "direction": _direction_label(item.direction),
                    "tone": _tone_for_direction(item.direction),
                    "confidence": _format_percent(item.confidence),
                    "detail": item.strategy_view,
                    "watch": " / ".join(item.watchlist[:3]) or "等待更多证据",
                }
                for item in related[:3]
            ]
            boards.append(
                {
                    "id": meta["id"],
                    "label": meta["label"],
                    "focus": meta["focus"],
                    "headline": summary_lines[0] if summary_lines else f"暂未形成明确{meta['label']}主线。",
                    "items": items or [{"title": meta["label"], "direction": "观察", "tone": "neutral", "confidence": 42, "detail": f"当前暂无高置信度的{meta['label']}信号，建议继续等待样本积累。", "watch": meta["focus"]}],
                }
            )
        return boards

    def _build_timeline(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        return [{"time": item.published_at, "source": item.source, "title": item.title, "summary": item.summary} for item in sorted(result.raw_items, key=lambda item: item.published_at, reverse=True)[:6]]

    def _build_events(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        return [{"title": event.title, "summary": event.summary, "eventType": event.event_type, "bias": event.bias, "publishedAt": event.published_at, "evidence": [ref.source for ref in event.evidence_refs[:3]]} for event in result.events[:6]]

    def _build_report_sections(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        if result.report is None:
            return [{"title": "当前运行模式为仅采集", "items": ["本轮未生成正式简报，请切换到完整研报模式。"]}]
        return [
            {"title": "重点线索", "items": list(result.report.overnight_focus[:4])},
            {"title": "跨资产主线", "items": list(result.report.cross_asset_themes[:4])},
            {"title": "风险情景", "items": list(result.report.risk_scenarios[:4])},
        ]

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
            "sourceMixSummary": [f"{item['label']}：{item['itemCount']} 条 / {item['sourceCount']} 个源" for item in source_mix.get("levels", [])],
            "socialHotspots": [f"{channel['label']}：{entry['name']} ({entry.get('itemCount', 0)}条)" for channel in source_mix.get("channels", []) for entry in channel.get("entries", [])[:2]],
            "citations": [{"title": event["title"], "source": ", ".join(event["evidence"][:2]) or "样本源"} for event in events[:3]],
            "reportText": result.report.markdown_body if result.report else "",
            "degradedReasons": list(result.degraded_reasons),
        }

    def _remember_context(self, run_id: int, context: dict[str, Any]) -> None:
        self._result_cache[run_id] = context
        while len(self._result_cache) > 12:
            self._result_cache.popitem(last=False)

    def _generate_opening(self, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            response = self.pipeline.llm_client.complete_text(
                self.pipeline.compose_agent_system_prompt("report", "You are a Chinese trading desk research assistant. Answer only from the provided context and do not invent facts."),
                self._opening_prompt(context),
            )
            if response:
                return response
        return self._fallback_opening(context)

    def _generate_answer(self, question: str, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            response = self.pipeline.llm_client.complete_text(
                self.pipeline.compose_agent_system_prompt("market_reasoning", "You are a Chinese trading desk research assistant. Lead with the conclusion, then the evidence, then the watch variables. Say clearly when the context is insufficient."),
                self._qa_prompt(question, context),
            )
            if response:
                return response
        return self._fallback_answer(question, context)

    def _opening_prompt(self, context: dict[str, Any]) -> str:
        lines = [
            f"用户意图: {context.get('intent') or '生成默认研究摘要'}",
            f"运行模式: {context.get('mode')}",
            f"运行窗口: {context.get('window')}",
            f"主导判断: {context['hero']['dominantDomain']} / {context['hero']['label']}",
            "L1-L4 来源分层:",
        ]
        lines.extend(f"- {item}" for item in context.get("sourceMixSummary", [])[:4])
        lines.append("跨资产主线:")
        lines.extend(f"- {item}" for item in context.get("topThemes", [])[:3])
        lines.append("X / Reddit 热点:")
        lines.extend(f"- {item}" for item in context.get("socialHotspots", [])[:4])
        lines.append("观察清单:")
        lines.extend(f"- {item}" for item in context.get("watchlist", [])[:4])
        lines.append("请用中文输出三行：1) 主线判断 2) 证据锚点 3) 交易台接下来盯什么。")
        return "\n".join(lines)

    def _qa_prompt(self, question: str, context: dict[str, Any]) -> str:
        lines = [
            f"问题: {question}",
            f"运行模式: {context.get('mode')}",
            f"运行窗口: {context.get('window')}",
            f"主导判断: {context['hero']['dominantDomain']} / {context['hero']['label']}",
            "L1-L4 来源分层:",
        ]
        lines.extend(f"- {item}" for item in context.get("sourceMixSummary", [])[:4])
        lines.append("跨资产主线:")
        lines.extend(f"- {item}" for item in context.get("topThemes", [])[:4])
        lines.append("分域视角:")
        for board in context.get("domainBoards", [])[:5]:
            lines.append(f"[{board['label']}] {board['headline']}")
            for item in board.get("items", [])[:2]:
                lines.append(f"- {item['direction']} | 置信度 {item['confidence']} | {item['detail']}")
        lines.append("事件证据:")
        for event in context.get("events", [])[:3]:
            lines.append(f"- {event['title']} | {event['summary']} | 证据: {', '.join(event['evidence'])}")
        lines.append("X / Reddit 热点:")
        lines.extend(f"- {item}" for item in context.get("socialHotspots", [])[:4])
        lines.append("风险与观察:")
        lines.extend(f"- {item}" for item in context.get("watchlist", [])[:5])
        lines.append("请只基于以上上下文作答。")
        return "\n".join(lines)

    def _fallback_opening(self, context: dict[str, Any]) -> str:
        theme = (context.get("topThemes") or ["暂未形成明确跨资产主线。"])[0]
        watch = (context.get("watchlist") or ["等待更多样本沉淀。"])[0]
        source_mix = "；".join(context.get("sourceMixSummary", [])[:2]) or "暂无来源分层摘要"
        return (
            f"主线判断：{theme}\n"
            f"证据锚点：当前驾驶舱显示 {context['hero']['dominantDomain']} 为主导资产，多空领先指标位于 {context['hero']['score']}，来源分层为 {source_mix}。\n"
            f"下一步：先盯 {watch}，再结合右侧的 L1-L4 source mix 与 X / Reddit 热点决定是否继续追问模型。"
        )

    def _fallback_answer(self, question: str, context: dict[str, Any]) -> str:
        lowered = question.lower()
        if "风险" in question:
            risks = context.get("riskScenarios") or context.get("watchlist") or ["暂无新增风险情景。"]
            return f"结论：当前最需要盯的是风险变量，而不是方向本身。\n证据：{'；'.join(risks[:3])}\n观察变量：{'；'.join(context.get('watchlist', [])[:4]) or '等待更多样本'}"
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
        theme = (context.get("topThemes") or ["暂未形成明确跨资产主线。"])[0]
        return f"结论：{theme}\n证据：当前最关键的事件是“{event['title']}”，其摘要为：{event['summary']}\n观察变量：{'；'.join(context.get('watchlist', [])[:4]) or '等待更多样本'}"

    def _board_answer(self, label: str, board: dict[str, Any]) -> str:
        item = board.get("items", [{}])[0]
        return f"结论：{label}维持{item.get('direction', '观察')}思路。\n证据：{board.get('headline')}\n观察变量：{item.get('watch') or board.get('focus')}"
