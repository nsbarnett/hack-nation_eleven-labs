"""Select bounded, evidence-linked context for AI roles; never include credentials."""

from apprentice.domain import Session


def context_for(session: Session, limit: int = 80) -> dict:
    # Preserve expert explanations and references before filling with screen
    # observations. Image bytes are attached separately, at most four per call.
    important = [e for e in session.evidence if e.kind != "screen" and not e.kind.startswith("trainee")][-limit:]
    screens = [e for e in session.evidence if e.kind == "screen"][-max(0, limit - len(important)):] if len(important) < limit else []
    return {
        "task": session.title, "context": session.context,
        "evidence": [e.model_dump(exclude={"image"}) for e in important + screens],
        "observations": [o.model_dump() for o in session.observations[-40:]],
        "knowledge": [k.model_dump() for k in session.knowledge if k.status != "rejected"][-40:],
    }
