from __future__ import annotations

import html
from pathlib import Path

from .models import ResearchBrief
from .utils import ensure_directory


def render_markdown(report: ResearchBrief) -> str:
    lines = [f"# 全球新闻研究简报 - {report.triggered_at}", "", "## 本次触发概览"]
    lines.extend(f"- {item}" for item in report.overview)
    lines.extend(["", "## 重点线索"])
    lines.extend(f"- {item}" for item in report.overnight_focus)
    lines.extend(["", "## 核心事件"])
    lines.extend(f"- {item}" for item in report.core_events)
    lines.extend(["", "## 跨资产主线"])
    lines.extend(f"- {item}" for item in report.cross_asset_themes)
    lines.extend(["", "## A股与重点板块"])
    lines.extend(f"- {item}" for item in report.equity_view)
    lines.extend(["", "## 商品期货"])
    lines.extend(f"- {item}" for item in report.commodities_view)
    lines.extend(["", "## 贵金属"])
    lines.extend(f"- {item}" for item in report.precious_metals_view)
    lines.extend(["", "## 原油与能源"])
    lines.extend(f"- {item}" for item in report.crude_oil_view)
    lines.extend(["", "## 风险情景"])
    lines.extend(f"- {item}" for item in report.risk_scenarios)
    lines.extend(["", "## 观察清单"])
    lines.extend(f"- {item}" for item in report.watchlist)
    lines.extend(["", "## 证据附录"])
    lines.extend(f"- {item}" for item in report.evidence_appendix)
    if report.degraded_reasons:
        lines.extend(["", "## 降级说明"])
        lines.extend(f"- {item}" for item in report.degraded_reasons)
    return "\n".join(lines).strip() + "\n"


def render_pdf(markdown_text: str, output_path: Path) -> str | None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        return None

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    heading = ParagraphStyle(name="Heading", fontName="STSong-Light", fontSize=15, leading=20)
    body = ParagraphStyle(name="Body", fontName="STSong-Light", fontSize=10.5, leading=15)
    story = []
    for line in markdown_text.splitlines():
        escaped = html.escape(line)
        if not escaped:
            story.append(Spacer(1, 8))
            continue
        if escaped.startswith("# "):
            story.append(Paragraph(escaped[2:], heading))
        elif escaped.startswith("## "):
            story.append(Paragraph(escaped[3:], heading))
        elif escaped.startswith("- "):
            story.append(Paragraph(f"* {escaped[2:]}", body))
        else:
            story.append(Paragraph(escaped, body))
    doc.build(story)
    return str(output_path)


def save_report_artifacts(
    report: ResearchBrief,
    report_dir: str,
) -> tuple[str, str | None, list[str]]:
    bucket = report.triggered_at[:10].replace("-", "")
    output_dir = ensure_directory(Path(report_dir) / bucket)
    markdown_path = output_dir / f"research_run_{report.run_id}.md"
    pdf_path = output_dir / f"research_run_{report.run_id}.pdf"
    markdown_path.write_text(report.markdown_body, encoding="utf-8")
    rendered_pdf = render_pdf(report.markdown_body, pdf_path)
    warnings = []
    if rendered_pdf is None:
        warnings.append("pdf_renderer_unavailable:install_reportlab")
    return str(markdown_path), rendered_pdf, warnings
