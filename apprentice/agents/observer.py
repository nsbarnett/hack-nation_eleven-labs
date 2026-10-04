"""Observer: interpret visible changes and suggest worthwhile uncertainties."""

from apprentice.context import context_for
from apprentice.domain import Observation, ObservationResult, Session
from apprentice.evidence import require_sources


class Observer:
    def __init__(self, gateway):
        self.gateway = gateway

    def run(self, session: Session, images):
        data = context_for(session)
        data["new_image_ids"] = [i for i, _ in images]
        result = self.gateway.request(ObservationResult, """Compare these chronological
screenshots. Return at most three NEW meaningful actions, excluding the recorder's
own UI and duplicates of recent observations. Empty actions is valid. Describe
visible state changes, not imagined clicks. Ask about intent only when useful:
overrides, exceptions, thresholds, missing prerequisites or consequential choices.
Use 0..3 scores for novelty, ambiguity, and significance. Questions should be one
sentence and reference visible evidence. No question is better than a generic one.""", data, images)
        allowed = {e["id"] for e in data["evidence"]} | set(data["new_image_ids"])
        return [Observation(**{**a.model_dump(), "evidence_ids": require_sources(a.evidence_ids, allowed)})
                for a in result.actions[:3]]
