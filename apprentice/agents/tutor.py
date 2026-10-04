"""Tutor: contextual explanations grounded exclusively in a confirmed map."""

from apprentice.domain import Session, TutorResult


class Tutor:
    def __init__(self, gateway):
        self.gateway = gateway

    def explain(self, session: Session, question: str) -> TutorResult:
        items = [k for k in session.knowledge if k.status == "verified"]
        if not session.confirmed or not items:
            return TutorResult(verdict="unknown", explanation="An expert must confirm the Work Map before teaching.", knowledge_ids=[])
        result = self.gateway.request(TutorResult, """Teach using ONLY the verified
knowledge supplied. Explain the expert's reasoning and reference knowledge IDs.
If a new case falls outside known boundaries, say unknown and suggest asking the
expert. Do not import generic company policy. This is advisory explanation; you
cannot authorize or execute actions in another application.""", {
            "question_or_case": question, "verified_knowledge": [k.model_dump() for k in items],
        })
        if not set(result.knowledge_ids).issubset({k.id for k in items}):
            raise ValueError("Tutor returned an unknown knowledge reference.")
        if result.verdict != "unknown" and not result.knowledge_ids:
            raise ValueError("Tutor guidance must cite the verified map.")
        return result

    def observe(self, session: Session, images) -> TutorResult:
        items = [k for k in session.knowledge if k.status == "verified"]
        if not session.confirmed:
            return TutorResult(verdict="unknown", explanation="The Work Map is not confirmed.", knowledge_ids=[])
        result = self.gateway.request(TutorResult, """Watch a trainee's latest screen
moments against the verified expert map. Warn only about a concrete visible
contradiction or missing guardrail supported by that map. Do not infer hidden
values or claim a save was prevented. If context is insufficient, return unknown.
For ok or unknown, keep the explanation short. Cite verified knowledge IDs only.
Never learn a new expert rule from the trainee's behavior.""", {
            "verified_knowledge": [k.model_dump() for k in items],
            "recent_guidance": [m.text for m in session.messages[-6:] if m.role == "assistant"],
        }, images)
        if not set(result.knowledge_ids).issubset({k.id for k in items}) or (result.verdict == "warn" and not result.knowledge_ids):
            raise ValueError("Trainee guidance must reference verified knowledge.")
        return result
