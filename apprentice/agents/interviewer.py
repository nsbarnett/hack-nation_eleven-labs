"""Interviewer: close knowledge gaps during the debrief, one question at a time."""

from apprentice.context import context_for
from apprentice.domain import QuestionResult, Session
from apprentice.evidence import require_sources


class Interviewer:
    def __init__(self, gateway):
        self.gateway = gateway

    def debrief(self, session: Session) -> QuestionResult:
        data = context_for(session)
        data["conversation"] = [m.model_dump() for m in session.messages[-12:]]
        result = self.gateway.request(QuestionResult, """Ask ONE unanswered question
about the most important remaining gap: reason, exact boundary, exception,
guardrail, or escalation. Avoid repeating answered questions. Acknowledge existing
answers. Use an empty question when no useful gap remains; do not manufacture a
gap. Reference the evidence that motivated your question.""", data)
        if result.question:
            result.evidence_ids = require_sources(result.evidence_ids, {e["id"] for e in data["evidence"]})
        return result
