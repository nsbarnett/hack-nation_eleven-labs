"""Explainable scheduling and completeness metrics, with no network calls."""

from dataclasses import dataclass, field

from apprentice.domain import Knowledge, Observation


def question_score(action: Observation) -> int:
    return action.novelty + action.ambiguity + 2 * action.significance + (3 if action.guardrail else 0)


@dataclass
class QuestionPolicy:
    idle_seconds: float = 8
    stable_seconds: float = 3
    cooldown: float = 90
    budget_per_ten_minutes: int = 3
    delivered: list[float] = field(default_factory=list)

    def eligible(self, now: float, idle: float, stable: float, enabled: bool, occupied: bool) -> bool:
        recent = [t for t in self.delivered if now - t < 600]
        return bool(enabled and not occupied and idle >= self.idle_seconds
                    and stable >= self.stable_seconds
                    and len(recent) < self.budget_per_ten_minutes
                    and (not self.delivered or now - self.delivered[-1] >= self.cooldown))

    def choose(self, actions: list[Observation]) -> Observation | None:
        candidates = [a for a in actions if a.question and not a.asked and question_score(a) >= 6]
        return max(candidates, key=question_score) if candidates else None


def completeness(items: list[Knowledge]) -> int:
    """Coverage of populated fields, NOT a probability that the map is correct."""
    active = [i for i in items if i.status != "rejected"]
    if not active:
        return 0
    points = sum(sum(bool(getattr(i, key).strip()) for key in ("action", "reason", "rule", "guardrail"))
                 + bool(i.evidence_ids) + (i.status == "verified") for i in active)
    return round(100 * points / (6 * len(active)))
