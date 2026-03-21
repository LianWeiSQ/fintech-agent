from __future__ import annotations

from collections import Counter, OrderedDict
from typing import Any

from .agents.registry import CORE_AGENT_DESCRIPTORS
from .config import AppConfig
from .models import MarketImpactAssessment, ResearchRunRequest, ResearchRunResult
from .pipeline import ResearchPipeline
from .utils import compact_whitespace

SCOPE_META: tuple[dict[str, str], ...] = (
    {"value": "equity", "label": "A股板块", "description": "指数、风格与政策受益方向"},
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
    {
        "id": "equities",
        "label": "A股",
        "domains": {"equities"},
        "focus": "围绕风险偏好、政策催化与风格切换。",
    },
    {
        "id": "commodities",
        "label": "商品",
        "domains": {"commodities"},
        "focus": "优先观察供需、库存与跨品种联动。",
    },
    {
        "id": "precious-metals",
        "label": "贵金属",
        "domains": {"precious_metals"},
        "focus": "重点盯住实际利率、美元和避险需求。",
    },
    {
        "id": "crude-oil",
        "label": "原油",
        "domains": {"energy"},
        "focus": "关注供给扰动、航运风险和库存变化。",
    },
    {
        "id": "macro",
        "label": "宏观",
        "domains": {"macro"},
        "focus": "统筹美元、利率与跨资产风险传导。",
    },
)

WORKFLOW_STEPS: tuple[tuple[str, str], ...] = tuple(
    (descriptor.agent_id, descriptor.display_name)
    for descriptor in CORE_AGENT_DESCRIPTORS
)


def _mode_label(mode: str) -> str:
    return {
        "full_report": "完整研报",
        "collect_only": "仅采集",
    }.get(mode, mode)


def _direction_label(direction: str) -> str:
    return {
        "bullish": "偏多",
        "bearish": "偏空",
        "neutral": "中性",
        "watch": "观察",
    }.get(direction, direction)


def _tone_for_direction(direction: str) -> str:
    return {
        "bullish": "positive",
        "bearish": "negative",
        "neutral": "neutral",
        "watch": "warning",
    }.get(direction, "neutral")


def _domain_label(domain: str) -> str:
    return {
        "equities": "A股",
        "commodities": "商品",
        "precious_metals": "贵金属",
        "energy": "原油",
        "macro": "宏观",
    }.get(domain, domain)


def _format_percent(value: float) -> int:
    return round(max(0.0, min(1.0, value)) * 100)


class DashboardService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.pipeline = ResearchPipeline(config)
        self._result_cache: OrderedDict[int, dict[str, Any]] = OrderedDict()

    def bootstrap_payload(self) -> dict[str, Any]:
        snapshot = self.pipeline.llm_client.snapshot()
        return {
            "title": "Fintech Agent 控盘台",
            "subtitle": "面向多资产研究流的可视化驾驶舱",
            "promptPlaceholder": "例如：请生成一份盘中简报，重点解释黄金、原油与A股之间的联动。",
            "quickPrompts": [
                "生成盘前多资产简报",
                "解释当前最强主线和最弱主线",
                "聚焦贵金属与原油风险传导",
            ],
            "modes": [
                {"value": "full_report", "label": "完整研报"},
                {"value": "collect_only", "label": "仅采集"},
            ],
            "defaults": {
                "mode": self.config.run_defaults.mode,
                "lookbackHours": self.config.run_defaults.lookback_hours,
            },
            "scopes": list(SCOPE_META),
            "sources": [
                {
                    "name": source.name,
                    "label": source.name,
                    "kind": source.kind,
                    "language": source.language,
                    "enabled": source.enabled,
                    "tags": list(source.tags),
                }
                for source in self.config.sources
                if source.enabled
            ],
            "workflow": [
                {"id": step_id, "label": label, "status": "idle", "detail": "等待运行"}
                for step_id, label in WORKFLOW_STEPS
            ],
            "model": {
                "available": self.pipeline.llm_client.available,
                "resolvedModel": snapshot.get("resolved_model") or "未配置",
                "provider": snapshot.get("provider") or "local",
            },
            "hero": {
                "score": 52,
                "label": "等待任务",
                "summary": "选择研究范围后即可启动一轮 Agent + 模型协同分析。",
            },
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
        context = self._build_chat_context(result, intent)
        self._remember_context(result.run_id, context)
        return {
            "meta": {
                "runId": result.run_id,
                "mode": result.mode,
                "modeLabel": _mode_label(result.mode),
                "triggeredAt": result.triggered_at,
                "window": {
                    "start": result.window.start,
                    "end": result.window.end,
                },
                "scopes": list(result.scopes),
                "sources": list(result.sources),
                "markdownPath": result.markdown_path,
                "pdfPath": result.pdf_path,
                "degradedReasons": list(result.degraded_reasons),
            },
            "hero": self._build_hero(result),
            "signalCards": self._build_signal_cards(result),
            "workflow": self._build_workflow(result, intent),
            "domainBoards": self._build_domain_boards(result),
            "timeline": self._build_timeline(result),
            "events": self._build_events(result),
            "watchlist": list(dict.fromkeys(result.integrated_view.watchlist))[:10],
            "reportSections": self._build_report_sections(result),
            "assistantOpening": {
                "mode": "model" if self.pipeline.llm_client.available else "fallback",
                "text": self._generate_opening(context),
            },
            "chatHandle": {
                "runId": result.run_id,
            },
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

        answer = self._generate_answer(question, context)
        return {
            "answer": answer,
            "mode": "model" if self.pipeline.llm_client.available else "fallback",
            "citations": context.get("citations", [])[:3],
            "nextPrompts": [
                "再拆一下最值得盯的风险变量",
                "把结论改写成盘前播报口径",
                "只看商品和贵金属会怎么交易",
            ],
        }

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = compact_whitespace(str(value))
        return text or None

    def _optional_int(self, value: Any) -> int | None:
        if value in {None, ""}:
            return None
        return int(value)

    def _normalize_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized = []
        for item in value:
            text = compact_whitespace(str(item))
            if text:
                normalized.append(text)
        return normalized

    def _build_hero(self, result: ResearchRunResult) -> dict[str, Any]:
        directions = Counter(item.direction for item in result.assessments)
        average_confidence = (
            sum(item.confidence for item in result.assessments) / len(result.assessments)
            if result.assessments
            else 0.5
        )
        score = round(
            max(
                10,
                min(
                    96,
                    50
                    + directions["bullish"] * 10
                    - directions["bearish"] * 9
                    + (average_confidence - 0.5) * 30
                    - len(result.degraded_reasons) * 4,
                ),
            )
        )
        if score >= 72:
            label = "顺势跟踪"
        elif score >= 58:
            label = "偏多观察"
        elif score >= 45:
            label = "震荡筛选"
        else:
            label = "防守优先"
        dominant_domain = "未形成主线"
        if result.assessments:
            dominant_domain = _domain_label(
                Counter(item.domain for item in result.assessments).most_common(1)[0][0]
            )
        summary = (
            f"{dominant_domain}主线占优，"
            f"{directions['bullish']} 条偏多、{directions['bearish']} 条偏空、"
            f"{directions['watch']} 条观察。"
        )
        return {
            "score": score,
            "label": label,
            "summary": summary,
            "confidence": _format_percent(average_confidence),
            "dominantDomain": dominant_domain,
        }

    def _build_signal_cards(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        directions = Counter(item.direction for item in result.assessments)
        hero = self._build_hero(result)
        average_credibility = (
            sum(item.score for item in result.credibility_scores) / len(result.credibility_scores)
            if result.credibility_scores
            else 0.0
        )
        dominant_domain = (
            _domain_label(Counter(item.domain for item in result.assessments).most_common(1)[0][0])
            if result.assessments
            else "未形成主线"
        )
        return [
            {
                "title": "多空领先指标",
                "value": f"{hero['score']}",
                "detail": hero["label"],
                "tone": "accent",
            },
            {
                "title": "证据强度",
                "value": f"{_format_percent(average_credibility)}%",
                "detail": f"{len(result.credibility_scores)} 个事件完成评分",
                "tone": "positive" if average_credibility >= 0.7 else "warning",
            },
            {
                "title": "主导资产",
                "value": dominant_domain,
                "detail": f"{len(result.assessments)} 条市场影响判断",
                "tone": "neutral",
            },
            {
                "title": "偏多/偏空",
                "value": f"{directions['bullish']} / {directions['bearish']}",
                "detail": "综合多空分布",
                "tone": "positive" if directions["bullish"] >= directions["bearish"] else "negative",
            },
            {
                "title": "观察清单",
                "value": f"{len(result.integrated_view.watchlist)} 项",
                "detail": "重点变量与事件跟踪",
                "tone": "warning",
            },
            {
                "title": "模型状态",
                "value": "已接入" if self.pipeline.llm_client.available else "规则回退",
                "detail": self.pipeline.llm_client.snapshot().get("resolved_model") or "未配置模型",
                "tone": "positive" if self.pipeline.llm_client.available else "neutral",
            },
        ]

    def _build_workflow(self, result: ResearchRunResult, intent: str) -> list[dict[str, Any]]:
        substage_lookup = {
            descriptor.agent_id: " -> ".join(descriptor.substages)
            for descriptor in CORE_AGENT_DESCRIPTORS
        }
        workflow = [
            {
                "id": "ingestion",
                "label": "Ingestion",
                "status": "completed",
                "detail": f"{len(result.raw_items)} raw items from {len(result.sources)} sources | {substage_lookup['ingestion']}",
            }
        ]
        collect_only = result.mode == "collect_only"
        workflow.append(
            {
                "id": "event_intelligence",
                "label": "Event Intelligence",
                "status": "idle" if collect_only else "completed",
                "detail": (
                    "Skipped after collect-only run"
                    if collect_only
                    else f"{len(result.events)} canonical events | {substage_lookup['event_intelligence']}"
                ),
            }
        )
        workflow.append(
            {
                "id": "market_reasoning",
                "label": "Market Reasoning",
                "status": "idle" if collect_only else "completed",
                "detail": (
                    "Skipped after collect-only run"
                    if collect_only
                    else f"{len(result.assessments)} assessments | {substage_lookup['market_reasoning']}"
                ),
            }
        )
        workflow.append(
            {
                "id": "audit",
                "label": "Audit",
                "status": "idle" if collect_only else "completed",
                "detail": (
                    "Skipped after collect-only run"
                    if collect_only
                    else f"{len(result.audit_notes)} audit notes | {substage_lookup['audit']}"
                ),
            }
        )
        workflow.append(
            {
                "id": "report",
                "label": "Report",
                "status": "idle" if collect_only else "completed",
                "detail": (
                    "No report generated in collect-only mode"
                    if collect_only
                    else f"{_mode_label(result.mode)} output ready | {substage_lookup['report']}"
                ),
            }
        )
        return workflow

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
                    "headline": summary_lines[0] if summary_lines else f"暂无明确{meta['label']}主线。",
                    "items": items
                    or [
                        {
                            "title": meta["label"],
                            "direction": "观察",
                            "tone": "neutral",
                            "confidence": 42,
                            "detail": f"当前暂无高置信度{meta['label']}信号，建议继续等待样本积累。",
                            "watch": meta["focus"],
                        }
                    ],
                }
            )
        return boards

    def _build_timeline(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        items = sorted(result.raw_items, key=lambda item: item.published_at, reverse=True)
        return [
            {
                "time": item.published_at,
                "source": item.source,
                "title": item.title,
                "summary": item.summary,
            }
            for item in items[:6]
        ]

    def _build_events(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        return [
            {
                "title": event.title,
                "summary": event.summary,
                "eventType": event.event_type,
                "bias": event.bias,
                "publishedAt": event.published_at,
                "evidence": [ref.source for ref in event.evidence_refs[:3]],
            }
            for event in result.events[:6]
        ]

    def _build_report_sections(self, result: ResearchRunResult) -> list[dict[str, Any]]:
        report = result.report
        if report is None:
            return [
                {
                    "title": "当前运行模式为仅采集",
                    "items": ["本轮未生成正式简报，请切换到完整研报模式。"],
                }
            ]
        return [
            {"title": "重点线索", "items": list(report.overnight_focus[:4])},
            {"title": "跨资产主线", "items": list(report.cross_asset_themes[:4])},
            {"title": "风险情景", "items": list(report.risk_scenarios[:4])},
        ]

    def _build_market_tape(self, result: ResearchRunResult) -> list[str]:
        tape = list(result.integrated_view.watchlist)
        tape.extend(item.title for item in result.events[:3])
        tape.extend(result.degraded_reasons)
        return list(dict.fromkeys(filter(None, tape)))[:10]

    def _build_chat_context(self, result: ResearchRunResult, intent: str) -> dict[str, Any]:
        domain_boards = self._build_domain_boards(result)
        return {
            "runId": result.run_id,
            "intent": intent,
            "mode": result.mode,
            "window": f"{result.window.start} -> {result.window.end}",
            "sources": list(result.sources),
            "scopes": list(result.scopes),
            "hero": self._build_hero(result),
            "topThemes": list(result.integrated_view.cross_asset_themes[:4]),
            "domainBoards": domain_boards,
            "watchlist": list(dict.fromkeys(result.integrated_view.watchlist))[:10],
            "riskScenarios": list(result.integrated_view.risk_scenarios[:4]),
            "events": self._build_events(result),
            "citations": [
                {
                    "title": event["title"],
                    "source": ", ".join(event["evidence"][:2]) or "样本源",
                }
                for event in self._build_events(result)[:3]
            ],
            "reportText": result.report.markdown_body if result.report else "",
            "degradedReasons": list(result.degraded_reasons),
        }

    def _remember_context(self, run_id: int, context: dict[str, Any]) -> None:
        self._result_cache[run_id] = context
        while len(self._result_cache) > 12:
            self._result_cache.popitem(last=False)

    def _generate_opening(self, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            prompt = self._opening_prompt(context)
            response = self.pipeline.llm_client.complete_text(
                self.pipeline.compose_agent_system_prompt(
                    "report",
                    "You are a Chinese trading desk research assistant. Answer only from the provided context and do not invent facts.",
                ),
                prompt,
            )
            if response:
                return response
        return self._fallback_opening(context)

    def _generate_answer(self, question: str, context: dict[str, Any]) -> str:
        if self.pipeline.llm_client.available:
            prompt = self._qa_prompt(question, context)
            response = self.pipeline.llm_client.complete_text(
                self.pipeline.compose_agent_system_prompt(
                    "market_reasoning",
                    "You are a Chinese trading desk research assistant. Lead with the conclusion, then the evidence, then the watch variables. Say clearly when the context is insufficient.",
                ),
                prompt,
            )
            if response:
                return response
        return self._fallback_answer(question, context)

    def _opening_prompt(self, context: dict[str, Any]) -> str:
        prompt_lines = [
            f"用户意图: {context.get('intent') or '生成默认研究摘要'}",
            f"运行模式: {context.get('mode')}",
            f"运行窗口: {context.get('window')}",
            f"主导判断: {context['hero']['dominantDomain']} / {context['hero']['label']}",
            "跨资产主线:",
        ]
        prompt_lines.extend(f"- {item}" for item in context.get("topThemes", [])[:3])
        prompt_lines.append("观察清单:")
        prompt_lines.extend(f"- {item}" for item in context.get("watchlist", [])[:4])
        prompt_lines.append("请用中文输出三行：1) 主线判断 2) 证据锚点 3) 交易台接下来盯什么。")
        return "\n".join(prompt_lines)

    def _qa_prompt(self, question: str, context: dict[str, Any]) -> str:
        prompt_lines = [
            f"问题: {question}",
            f"运行模式: {context.get('mode')}",
            f"运行窗口: {context.get('window')}",
            f"主导判断: {context['hero']['dominantDomain']} / {context['hero']['label']}",
            "跨资产主线:",
        ]
        prompt_lines.extend(f"- {item}" for item in context.get("topThemes", [])[:4])
        prompt_lines.append("分域视角:")
        for board in context.get("domainBoards", [])[:5]:
            prompt_lines.append(f"[{board['label']}] {board['headline']}")
            for item in board.get("items", [])[:2]:
                prompt_lines.append(
                    f"- {item['direction']} | 置信度 {item['confidence']} | {item['detail']}"
                )
        prompt_lines.append("事件证据:")
        for event in context.get("events", [])[:3]:
            prompt_lines.append(
                f"- {event['title']} | {event['summary']} | 证据: {', '.join(event['evidence'])}"
            )
        prompt_lines.append("风险与观察:")
        prompt_lines.extend(f"- {item}" for item in context.get("watchlist", [])[:5])
        prompt_lines.append("请只基于以上上下文作答。")
        return "\n".join(prompt_lines)

    def _fallback_opening(self, context: dict[str, Any]) -> str:
        theme = (context.get("topThemes") or ["暂无明确跨资产主线。"])[0]
        watch = (context.get("watchlist") or ["等待更多样本沉淀。"])[0]
        return (
            f"主线判断：{theme}\n"
            f"证据锚点：当前驾驶舱显示 {context['hero']['dominantDomain']} 为主导资产，"
            f"多空领先指标位于 {context['hero']['score']}。\n"
            f"下一步：先盯 {watch}，再结合右侧分域卡片决定是否继续追问模型。"
        )

    def _fallback_answer(self, question: str, context: dict[str, Any]) -> str:
        lowered = question.lower()
        if "风险" in question:
            risks = context.get("riskScenarios") or context.get("watchlist") or ["暂无新增风险情景。"]
            return (
                "结论：当前最需要盯的是风险变量而不是方向本身。\n"
                f"证据：{'；'.join(risks[:3])}\n"
                f"观察变量：{'、'.join(context.get('watchlist', [])[:4]) or '等待更多样本'}"
            )
        board_lookup = {board["id"]: board for board in context.get("domainBoards", [])}
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
        theme = (context.get("topThemes") or ["暂无明确跨资产主线。"])[0]
        event = (context.get("events") or [{"title": "暂无事件", "summary": "请先发起一轮研究。"}])[0]
        return (
            f"结论：{theme}\n"
            f"证据：当前最关键的事件是“{event['title']}”，其摘要为：{event['summary']}\n"
            f"观察变量：{'、'.join(context.get('watchlist', [])[:4]) or '等待更多样本'}"
        )

    def _board_answer(self, label: str, board: dict[str, Any]) -> str:
        item = board.get("items", [{}])[0]
        return (
            f"结论：{label}维持{item.get('direction', '观察')}思路。\n"
            f"证据：{board.get('headline')}\n"
            f"观察变量：{item.get('watch') or board.get('focus')}"
        )
