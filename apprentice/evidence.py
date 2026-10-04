"""Provenance validation and cascading exclusion, independent of any AI model."""

from apprentice.domain import Session


def require_sources(ids: list[str], allowed: set[str]) -> list[str]:
    """Reject hallucinated or empty references instead of quietly accepting them."""
    unique = list(dict.fromkeys(ids))
    if not unique or not set(unique).issubset(allowed):
        raise ValueError("The AI returned missing or unknown evidence references. Please retry.")
    return unique


def forget(session: Session, evidence_id: str) -> set[str]:
    """Exclude a source and its dependent answers, claims, and conversation excerpts.

Media removal is the controller's responsibility. Incrementing revision makes
all worker responses based on the earlier snapshot ineligible for persistence.
"""
    removed = {evidence_id}
    while True:
        dependent = {e.id for e in session.evidence if set(e.related_ids) & removed}
        if dependent.issubset(removed):
            break
        removed |= dependent
    session.evidence = [e for e in session.evidence if e.id not in removed]
    # Observations may have used the excluded context indirectly. Clear all
    # generated observations rather than trusting the model's direct citations.
    session.observations = []
    session.messages = [m for m in session.messages if not set(m.evidence_ids) & removed]
    # A map and teach-back can combine information across all sources. Invalidate
    # the complete derived map, then let the user rebuild from retained evidence.
    session.knowledge = []
    session.messages = [m for m in session.messages if m.role != "assistant"]
    session.confirmed = False
    session.revision += 1
    return removed
