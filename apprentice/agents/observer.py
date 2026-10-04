"""Observer: interpret visible changes and suggest worthwhile uncertainties."""

from apprentice.context import context_for
from apprentice.domain import EventResult, Observation, Session
from apprentice.evidence import require_sources


class Observer:
    def __init__(self, gateway):
        self.gateway = gateway

    def run(self, session: Session, images):
        data = context_for(session)
        data["new_image_ids"] = [i for i, _ in images]
        data["known_case_ids"] = sorted({o.case_id for o in session.observations if o.case_id})
        result = self.gateway.request(EventResult, """Compare these chronological
screenshots. Return at most three NEW meaningful actions, excluding the recorder's
own UI and duplicates of recent observations. Empty actions is valid. Describe
only visible state changes, never imagined clicks or inferred reasons. Do not write questions.
Classify the event and copy visible case IDs, field names, before/after values exactly.
Use empty strings for unavailable values and false readability for blurry/missing values.
Set before_was_default only when the screen supports that the value was prefilled.
Report confidence in the visible event, not confidence in the expert's reasoning.
List fields_answered_on_screen only when the screen explicitly supplies that information.
Reuse known case IDs. Routine navigation and step completion are timing signals, not
evidence of a knowledge gap. Cite the actual supplied frames.""", data, images)
        allowed = {e["id"] for e in data["evidence"]} | set(data["new_image_ids"])
        return [Observation(**{**a.model_dump(), "evidence_ids": require_sources(a.evidence_ids, allowed)})
                for a in result.actions[:3]]
