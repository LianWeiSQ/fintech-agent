from __future__ import annotations

from ...models import AuditBundle, MarketReasoningBundle
from ..base import AgentRuntimeContext, BaseResearchAgent
from ..registry import get_agent_descriptor
from .runtime import AuditRuntime
from .steps.downgrade_trace import build_downgrade_trace
from .steps.publishability import EvidenceAuditAgent


class AuditAgent(BaseResearchAgent[MarketReasoningBundle, AuditBundle]):
    descriptor = get_agent_descriptor("audit")

    def execute(
        self,
        context: AgentRuntimeContext,
        payload: MarketReasoningBundle,
    ) -> AuditBundle:
        _runtime = AuditRuntime(self.descriptor, context.skill)
        auditor = EvidenceAuditAgent(context.config.audit)
        assessments, audit_notes = auditor.run(
            payload.assessments,
            payload.intelligence.credibility_scores,
        )
        context.storage.record_stage(
            context.run_id,
            stage="audit",
            agent_id="audit",
            substage="audit_publishability",
            entity_type="market_impact_assessment",
            payloads=assessments,
            entity_ids=[assessment.id for assessment in assessments],
        )
        context.storage.record_stage(
            context.run_id,
            stage="audit",
            agent_id="audit",
            substage="downgrade_trace",
            entity_type="audit_note",
            payloads=build_downgrade_trace(audit_notes),
            entity_ids=[str(index) for index, _ in enumerate(audit_notes)],
        )
        degraded_reasons = list(dict.fromkeys(payload.intelligence.collected.degraded_reasons + audit_notes))
        context.storage.record_stage(
            context.run_id,
            stage="audit",
            agent_id="audit",
            substage="degraded_reason_merge",
            entity_type="degraded_reason",
            payloads=[{"reason": reason} for reason in degraded_reasons],
            entity_ids=degraded_reasons,
        )
        return AuditBundle(
            reasoning=payload,
            assessments=assessments,
            audit_notes=audit_notes,
            degraded_reasons=degraded_reasons,
        )
