"""Semantic extraction proposes evidence-backed field assessments, never verification."""
from apprentice.domain import AssessmentResult
from apprentice.evaluation import apply_assessment, expert_sources, pending_sources, refresh


class Assessor:
    def __init__(self, gateway):
        self.gateway = gateway

    def run(self, session):
        """Return an assessed snapshot. The service applies it only at the same generation."""
        snapshot = session.model_copy(deep=True)
        refresh(snapshot)
        pending = pending_sources(snapshot)
        if not pending:
            return snapshot.evaluation
        result = self.gateway.request(AssessmentResult, """Assess expert explanations against the supplied decisions and gaps.
Use existing decision IDs only. Bind answers to their gap_id decision, never the latest screen.
For each field actually addressed, return a claim, exact verbatim quote(s) from expert text,
confidence in your assessment (not probability the business rule is true), and a brief rationale.
Outcomes: sufficient = explicit and adequate for that field; partial = missing conditions;
uncertain = the expert does not know; contradictory = conflicts with prior guidance and the
conditions do not resolve it; out_of_scope = irrelevant to that decision; not_applicable = the
expert explicitly says this field does not apply (still needs expert review).
"I don't know", acknowledgements, silence, and vague answers never establish knowledge.
Qualified statements such as "usually above 5000" leave the exact boundary and exception open.
Never use a case identifier as a monetary threshold. Preserve currency, units and scope.
Compare new statements with prior assessments and verified knowledge; flag unresolved conflicts.
Propose gaps only where evidence makes them applicable: reason, rule, scope, threshold, operator,
exception, guardrail, escalation, contradiction, cue. Do not manufacture a fixed quota of gaps.
When an expert describes changing, reversing, holding, or choosing an action without explaining why,
propose a reason gap for that text decision, citing the note. Describe it as a reported action,
not an independently observed screen event. Routine navigation alone needs no reason gap.
One explained example is not a universal rule. Model-inferred Work Map prose is not expert evidence.
Assess all pending evidence; unrelated notes may use their own text decision. No question wording,
verification, or action authorization is requested.""", {
            "decisions": [d.model_dump() for d in snapshot.evaluation.decisions],
            "gaps": [g.model_dump() for g in snapshot.evaluation.gaps],
            "pending_evidence_ids": [e.id for e in pending],
            "expert_evidence": [e.model_dump(exclude={"image"}) for e in expert_sources(snapshot).values() if e.text],
            "prior_assessments": [a.model_dump() for a in snapshot.evaluation.assessments],
            "knowledge": [k.model_dump() for k in snapshot.knowledge if k.status != "rejected"],
        })
        apply_assessment(snapshot, result, [e.id for e in pending])
        return snapshot.evaluation
