"""Knowledge builder: propose an editable, evidence-backed Work Map and teach-back."""

from apprentice.context import context_for
from apprentice.domain import Knowledge, MapResult, Session
from apprentice.evidence import require_sources


class KnowledgeBuilder:
    def __init__(self, gateway):
        self.gateway = gateway

    def run(self, session: Session):
        data = context_for(session)
        result = self.gateway.request(MapResult, """Build at most 12 teachable Work Map
items from the supplied evidence. Preserve distinctions among action, decision,
reason, rule, exception, guardrail, escalation. Use 'Not established' for unknown
fields and flag needs_clarification. An expert statement is evidence but is not
automatically a verified general rule. Identify conflicting guidance as a gap.
Do not transform a single screen example into a universal rule. Produce a short
teach-back for the expert to confirm and list unresolved gaps.
Optionally produce a RuleCheck ONLY when explicit evidence supports the exact
condition and expected result. Never guess thresholds or operators. Values are
strings; numeric comparison is performed by the app. Derive field names from
explicit evidence in this workflow, never from a preset business domain. Leave
check null when fields or conditions are not established. A conditions list is an
AND, and the consequence is a single expected field comparison. Bind each item to the
supplied decision_ids it actually explains. Unresolved or disputed gaps must remain
needs_clarification; do not turn partial answers into universal verified rules.""", data)
        allowed = {e["id"] for e in data["evidence"]}
        if not result.items:
            raise ValueError("No supported knowledge was produced. Add an expert explanation and retry.")
        items = []
        for item in result.items:
            values = item.model_dump(exclude={"needs_clarification"})
            values["evidence_ids"] = require_sources(item.evidence_ids, allowed)
            if not set(item.decision_ids) <= {d.id for d in session.evaluation.decisions}:
                raise ValueError("Work Map referenced an unknown decision.")
            items.append(Knowledge(**values, status="needs_clarification" if item.needs_clarification else "inferred"))
        return items, result.teach_back, result.gaps
