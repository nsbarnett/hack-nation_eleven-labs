"""Interviewer: close knowledge gaps during the debrief, one question at a time."""

from apprentice.context import context_for
from apprentice.domain import QuestionResult, Session
from apprentice.evidence import require_sources
from apprentice.evaluation import question_for


class Interviewer:
    def __init__(self, gateway):
        self.gateway = gateway

    def debrief(self, session: Session, gap=None) -> QuestionResult:
        data = context_for(session)
        data["conversation"] = [m.model_dump() for m in session.messages[-12:]]
        if gap:
            data["target_gap"] = gap.model_dump()
        result = self.gateway.request(QuestionResult, """Ask ONE unanswered question
about the most important remaining gap: reason, exact boundary, exception,
guardrail, or escalation. Avoid repeating answered questions. Acknowledge existing
answers. Use an empty question when no useful gap remains; do not manufacture a
gap. Reference the evidence that motivated your question. When target_gap is supplied,
ask ONLY about its missing field and decision. Do not switch to a different gap,
assume unconfirmed intent, suggest an answer, or bundle several questions.""", data)
        if result.question:
            result.evidence_ids = require_sources(result.evidence_ids, {e["id"] for e in data["evidence"]})
        if gap:
            allowed = set(gap.evidence_ids + gap.supporting_evidence_ids)
            if (not result.question or result.question.count("?") != 1 or len(result.question) > 500
                    or not set(result.evidence_ids) <= allowed):
                return QuestionResult(question=question_for(session, gap), evidence_ids=gap.evidence_ids)
        return result
