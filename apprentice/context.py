"""Select bounded, evidence-linked context for AI roles; never include credentials."""

from apprentice.domain import Session
from apprentice.evaluation import expert_sources


def context_for(session: Session, limit: int = 80) -> dict:
    # Preserve expert explanations and references before filling with screen
    # observations. Image bytes are attached separately, at most four per call.
    retained = list(expert_sources(session).values())
    important = [e for e in retained if e.kind != "screen"][-limit:]
    screens = [e for e in retained if e.kind == "screen"][-max(0, limit - len(important)):] if len(important) < limit else []
    return {
        "task": session.title, "context": session.context,
        "evidence": [e.model_dump(exclude={"image"}) for e in important + screens],
        "observations": [o.model_dump() for o in session.observations[-40:]],
        "knowledge": [k.model_dump() for k in session.knowledge if k.status != "rejected"][-40:],
        "decisions": [d.model_dump() for d in session.evaluation.decisions],
        "knowledge_gaps": [g.model_dump() for g in session.evaluation.gaps],
    }
