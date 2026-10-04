"""Persistent, evidence-backed gap evaluation. No model or network calls here.

Ports EvalTest's explicit gaps, priority ordering and question rubric into the
session contract. Model assessments propose claims; only expert review verifies.
See docs/EVALUATION.md for parameter definitions and deliberate differences.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import re

from apprentice.domain import (
    AssessmentResult, EvaluationDecision, EvaluationTrace, KnowledgeGap,
    QuestionAttempt, Session,
)


@dataclass(frozen=True)
class EvaluationConfig:
    min_observation_confidence: float = 0.50
    unreadable_confidence_cap: float = 0.35
    min_answer_confidence: float = 0.80
    max_live_evidence_age_s: float = 120
    live_cooldown_s: float = 45
    live_budget_per_10min: int = 5
    max_trace_entries: int = 100
    live_priority_threshold: float = 60


CONFIG = EvaluationConfig()
OPEN = {"open", "partial", "disputed"}
PRIORITY = {"guardrail": 0, "escalation": 0, "contradiction": 0,
            "threshold": 1, "operator": 1, "exception": 1, "scope": 1,
            "reason": 2, "rule": 2, "cue": 3}
WEIGHT = {field: (3 if priority == 0 else 1 if field == "cue" else 2)
          for field, priority in PRIORITY.items()}
CREDIT = {"open": 0, "disputed": 0, "partial": 0.5, "observed": 1,
          "expert_stated": 1, "verified": 1, "not_applicable": 1}
TEMPLATES = {
    "reason": "What made you choose that action?",
    "rule": "What rule should someone follow when making this decision?",
    "scope": "Under which conditions does this rule apply?",
    "threshold": "What is the cutoff, and which value does it apply to?",
    "operator": "What happens when the value is exactly at the stated cutoff?",
    "exception": "What is the closest case where this rule would not apply?",
    "guardrail": "What needs to be resolved before this can proceed?",
    "escalation": "Who can decide whether this can proceed?",
    "contradiction": "Which conditions explain the conflicting guidance for this decision?",
    "cue": "Which cue matters when making this decision?",
}
MAP_FIELDS = {"reason": "reason", "rule": "rule", "exception": "exception",
              "guardrail": "guardrail", "escalation": "escalation"}
UNKNOWN = re.compile(r"^(?:not established|unknown|unclear|unspecified|not provided|tbd|n/?a|none)?[.! ]*$", re.I)
UNCERTAIN = re.compile(r"\b(?:i (?:do not|don't|don’t) know|not sure|unsure|cannot say|can't say|no idea)\b", re.I)
QUALIFIED = re.compile(r"\b(?:usually|normally|generally|typically|sometimes|maybe|probably)\b", re.I)
ACKNOWLEDGEMENT = re.compile(r"^(?:yes|no|ok|okay|fine|sure|thanks|agreed|right)[.! ]*$", re.I)


def established(text):
    return bool(text.strip()) and not UNKNOWN.fullmatch(text.strip())


def expert_sources(session):
    """Exclude trainee material and answers depending on missing/redacted sources."""
    sources = {e.id: e for e in session.evidence if not e.kind.startswith("trainee")}
    while True:
        valid = {i: e for i, e in sources.items() if set(e.related_ids) <= sources.keys()}
        if len(valid) == len(sources):
            return valid
        sources = valid


def trace(session, code, detail, gap_id=""):
    session.evaluation.trace.append(EvaluationTrace(code=code, gap_id=gap_id, detail=detail))
    session.evaluation.trace = session.evaluation.trace[-CONFIG.max_trace_entries:]


def ensure_gap(session, decision_id, field, sources, description=""):
    found = next((g for g in session.evaluation.gaps if g.decision_id == decision_id and g.field == field), None)
    if found:
        return found
    gap = KnowledgeGap(decision_id=decision_id, field=field, description=description or TEMPLATES[field],
                       evidence_ids=list(sources))
    session.evaluation.gaps.append(gap)
    return gap


def observation_decision(obs):
    if obs.case_id and obs.field_name:
        key = json.dumps([obs.case_id, obs.field_name], ensure_ascii=False).encode()
        return "decision:" + hashlib.sha256(key).hexdigest()[:16]
    return f"observation:{obs.id}"


def seed(session):
    state, sources = session.evaluation, expert_sources(session)
    retained_maps = {f"knowledge:{k.id}" for k in session.knowledge if k.status != "rejected"}
    state.decisions = [d for d in state.decisions if d.evidence_ids and set(d.evidence_ids) <= sources.keys()
                       and (not d.id.startswith("knowledge:") or d.id in retained_maps)]
    known = {d.id for d in state.decisions}
    for obs in session.observations:
        if not obs.evidence_ids or not set(obs.evidence_ids) <= sources.keys():
            continue
        if obs.event_type in {"navigation", "step_completed"}:
            continue
        did = observation_decision(obs)
        confidence = obs.confidence
        readable = obs.event_type not in {"field_changed", "action_reversed"} or (obs.before_readable and obs.after_readable)
        if not readable:
            confidence = min(confidence, CONFIG.unreadable_confidence_cap)
        usable = confidence >= CONFIG.min_observation_confidence
        label = " / ".join(x for x in (obs.case_id, obs.field_name) if x) or obs.summary[:160]
        existing = next((d for d in state.decisions if d.id == did), None)
        if existing:
            existing.evidence_ids = list(dict.fromkeys(existing.evidence_ids + obs.evidence_ids))
            existing.observation_usable, existing.observation_confidence = usable, confidence
        else:
            state.decisions.append(EvaluationDecision(id=did, label=label, evidence_ids=obs.evidence_ids,
                observation_confidence=confidence, observation_usable=usable,
                observation_reason="Supported visible event." if usable else "Uncertain or unreadable event; clarification is required."))
        known.add(did)
        fields = {"case_held": ["guardrail", "escalation"], "record_opened": ["cue"],
                  "records_compared": ["cue"], "field_changed": ["reason"],
                  "action_reversed": ["reason"], "dependency_step": ["reason"]}.get(obs.event_type, ["rule"])
        for name in fields:
            ensure_gap(session, did, name, obs.evidence_ids)
    bound_answers = {a.answer_id for a in state.attempts if a.answer_id}
    for e in sources.values():
        if e.kind not in {"note", "answer", "demo"} or not e.text or e.gap_id or e.id in bound_answers:
            continue
        did = f"text:{e.id}"
        if did not in known:
            state.decisions.append(EvaluationDecision(id=did, label=e.text[:120], evidence_ids=[e.id]))
            known.add(did)
            ensure_gap(session, did, "rule", [e.id])
    for item in session.knowledge:
        if item.status == "rejected" or not item.evidence_ids or not set(item.evidence_ids) <= sources.keys():
            continue
        ids = [i for i in item.decision_ids if i in known]
        if not ids:
            matches = [d.id for d in state.decisions if set(item.evidence_ids) & set(d.evidence_ids)]
            ids = matches if len(matches) == 1 else [f"knowledge:{item.id}"]
        for did in ids:
            if did not in known:
                state.decisions.append(EvaluationDecision(id=did, label=item.title, evidence_ids=item.evidence_ids))
                known.add(did)
            for name in MAP_FIELDS:
                ensure_gap(session, did, name, item.evidence_ids)
        # An application-owned binding; cannot spread verification by shared screenshot alone.
        item.decision_ids = ids
    state.gaps = [g for g in state.gaps if g.decision_id in known and set(g.evidence_ids) <= sources.keys()]


def refresh(session):
    """Rebuild derived statuses from retained evidence and current reviews every time."""
    seed(session)
    state, sources = session.evaluation, expert_sources(session)
    source_order = {e.id: i for i, e in enumerate(session.evidence)}
    decisions = {d.id: d for d in state.decisions}
    gaps = {g.id: g for g in state.gaps}
    state.assessments = [a for a in state.assessments if a.decision_id in decisions and a.citations
                         and all(c.evidence_id in sources and c.quote in sources[c.evidence_id].text for c in a.citations)]
    state.assessed_evidence_ids = [i for i in state.assessed_evidence_ids if i in sources]
    state.attempts = [a for a in state.attempts if a.gap_id in gaps and set(a.evidence_ids) <= sources.keys()
                      and (not a.answer_id or a.answer_id in sources)]
    state.reviews = [r for r in state.reviews if r.gap_id in gaps and r.evidence_id in sources]
    state.trace = [t for t in state.trace if not t.gap_id or t.gap_id in gaps][-CONFIG.max_trace_entries:]
    for gap in state.gaps:
        old = gap.status
        gap.status, gap.claim, gap.supporting_evidence_ids, gap.verified_by = "open", "", [], []
        obs = next((o for o in reversed(session.observations) if observation_decision(o) == gap.decision_id), None)
        if obs and decisions[gap.decision_id].observation_usable and gap.field in obs.fields_answered_on_screen:
            gap.status, gap.supporting_evidence_ids = "observed", list(obs.evidence_ids)
        established_claims = set()
        for assessment in state.assessments:
            if (assessment.decision_id, assessment.field) != (gap.decision_id, gap.field):
                continue
            gap.claim = assessment.claim
            gap.supporting_evidence_ids = list(dict.fromkeys(gap.supporting_evidence_ids + [c.evidence_id for c in assessment.citations]))
            if assessment.outcome == "contradictory":
                gap.status = "disputed"
            elif gap.status != "disputed":
                if assessment.outcome == "sufficient":
                    normalized = assessment.claim.strip().casefold().rstrip(".")
                    established_claims.add(normalized)
                    gap.status = "disputed" if len(established_claims) > 1 else "expert_stated"
                elif assessment.outcome in {"partial", "not_applicable"}:
                    gap.status = "partial"  # Inapplicability also requires explicit expert review.
                elif assessment.outcome == "uncertain":
                    gap.status = "open"
        verified_values = set()
        for item in session.knowledge:
            if gap.decision_id not in item.decision_ids or item.status == "rejected":
                continue
            attr = MAP_FIELDS.get(gap.field)
            if not attr:
                continue
            value = getattr(item, attr)
            if item.status == "conflicting":
                gap.status = "disputed"
            elif item.status == "verified" and established(value) and gap.status != "disputed":
                verified_values.add(value.strip().casefold().rstrip("."))
                gap.status, gap.claim = "verified", value
                if len(verified_values) > 1:
                    gap.status = "disputed"
                gap.verified_by.append(item.id)
                gap.supporting_evidence_ids = list(dict.fromkeys(gap.supporting_evidence_ids + item.evidence_ids))
        for review in state.reviews:
            if review.gap_id == gap.id:
                newer = [a for a in state.assessments if (a.decision_id, a.field) == (gap.decision_id, gap.field)
                         and any(source_order[c.evidence_id] > source_order[review.evidence_id] for c in a.citations)]
                if newer:
                    continue
                gap.status, gap.claim = review.outcome, sources[review.evidence_id].text
                gap.supporting_evidence_ids = [review.evidence_id]
                gap.verified_by = [review.evidence_id]
        if old != gap.status:
            trace(session, "GAP_STATUS", f"{old} -> {gap.status}", gap.id)
    return state


def pending_sources(session):
    sources = expert_sources(session)
    done = set(session.evaluation.assessed_evidence_ids)
    return [e for e in sources.values() if e.kind in {"note", "answer", "demo"} and e.text and e.id not in done]


def apply_assessment(session, result: AssessmentResult, assessed_ids):
    """Validate the complete proposal atomically before changing the projection."""
    refresh(session)
    sources = expert_sources(session)
    decisions = {d.id: d for d in session.evaluation.decisions}
    clean = []
    covered = set()
    for assessment in result.assessments:
        a = assessment.model_copy(deep=True)
        if a.decision_id not in decisions or not a.citations:
            raise ValueError("Assessment must reference an existing decision and supporting text.")
        for citation in a.citations:
            source = sources.get(citation.evidence_id)
            if not source or source.kind not in {"answer", "note", "demo"} or not citation.quote.strip() or citation.quote not in source.text:
                raise ValueError("Assessment quote is not present in retained expert evidence.")
            bound = next((g for g in session.evaluation.gaps if g.id == source.gap_id), None)
            if bound and bound.decision_id != a.decision_id:
                raise ValueError("Assessment assigned an answer to a different decision.")
            covered.add(citation.evidence_id)
        quoted = " ".join(c.quote for c in a.citations)
        if a.outcome in {"sufficient", "not_applicable"}:
            if not established(a.claim) or UNCERTAIN.search(quoted) or ACKNOWLEDGEMENT.fullmatch(quoted.strip()):
                a.outcome = "uncertain"
            elif a.confidence < CONFIG.min_answer_confidence or (a.field in {"rule", "threshold", "operator", "scope"} and QUALIFIED.search(quoted)):
                a.outcome = "partial"
        if a.outcome == "out_of_scope":
            continue
        clean.append(a)
    if not set(assessed_ids) <= covered:
        raise ValueError("Assessment omitted pending expert evidence. The evidence remains awaiting assessment.")
    for proposal in result.gaps:
        if proposal.decision_id not in decisions or not proposal.evidence_ids or not set(proposal.evidence_ids) <= sources.keys():
            raise ValueError("Gap proposal must reference retained evidence and an existing decision.")
    for proposal in result.gaps:
        ensure_gap(session, proposal.decision_id, proposal.field, proposal.evidence_ids, proposal.description)
    for a in clean:
        ensure_gap(session, a.decision_id, a.field, decisions[a.decision_id].evidence_ids)
        session.evaluation.assessments.append(a)
    session.evaluation.assessed_evidence_ids = list(dict.fromkeys(session.evaluation.assessed_evidence_ids + list(assessed_ids)))
    trace(session, "ASSESSMENT_APPLIED", f"Validated {len(clean)} field assessments; model output cannot verify knowledge.")
    refresh(session)


def process_score(session, decision_id=None):
    """Evidence completeness, not a rating of the human or proof of correctness."""
    gaps = [g for g in session.evaluation.gaps if decision_id is None or g.decision_id == decision_id]
    total = sum(WEIGHT[g.field] for g in gaps)
    return round(100 * sum(WEIGHT[g.field] * CREDIT[g.status] for g in gaps) / total, 1) if total else None


def question_score(session, gap):
    decision = next(d for d in session.evaluation.decisions if d.id == gap.decision_id)
    confidence = decision.observation_confidence if decision.observation_confidence is not None else 1
    completeness = process_score(session, gap.decision_id) or 0
    return round(60 * WEIGHT[gap.field] / 3 + 25 * (1 - completeness / 100) + 15 * confidence, 1)


def next_gap(session, phase="debrief", decision_ids=None):
    refresh(session)
    decisions = {d.id: d for d in session.evaluation.decisions}
    deferred = {a.gap_id for a in session.evaluation.attempts if a.state == "deferred"}
    counts = {g.id: sum(a.gap_id == g.id for a in session.evaluation.attempts) for g in session.evaluation.gaps}
    sources = expert_sources(session)
    pool = [g for g in session.evaluation.gaps if g.status in OPEN
            and (decision_ids is None or g.decision_id in decision_ids)
            and (phase != "live" or (g.id not in deferred and decisions[g.decision_id].observation_usable
                                    and any(i in sources and session.duration - sources[i].timestamp <= CONFIG.max_live_evidence_age_s for i in g.evidence_ids)
                                    and question_score(session, g) >= CONFIG.live_priority_threshold))]
    order = {g.id: i for i, g in enumerate(session.evaluation.gaps)}
    return min(pool, key=lambda g: (PRIORITY[g.field], counts[g.id], -question_score(session, g), g.field != "reason",
        -(decisions[g.decision_id].observation_confidence if decisions[g.decision_id].observation_confidence is not None else 1),
        order[g.id])) if pool else None


def question_for(session, gap):
    decision = next(d for d in session.evaluation.decisions if d.id == gap.decision_id)
    if not decision.observation_usable:
        return f"For {decision.label}: what actually happened at this step? The recorded values are unclear."
    observed = next((o for o in reversed(session.observations) if observation_decision(o) == gap.decision_id), None)
    if observed and observed.event_type in {"field_changed", "action_reversed"} and observed.before_readable and observed.after_readable:
        return f"You changed {observed.field_name or decision.label} from {observed.before} to {observed.after}. {TEMPLATES[gap.field]}"
    return f"For {decision.label}: {TEMPLATES[gap.field]}"


def ask_gap(session, gap, phase="debrief", text=None):
    active = next((a for a in session.evaluation.attempts if a.state == "asking"), None)
    if active:
        return active
    attempt = QuestionAttempt(gap_id=gap.id, text=text or question_for(session, gap),
                              evidence_ids=list(dict.fromkeys(gap.evidence_ids + gap.supporting_evidence_ids)), phase=phase,
                              timestamp=session.duration, priority_score=question_score(session, gap),
                              process_score=process_score(session))
    session.evaluation.attempts.append(attempt)
    trace(session, "ASK", f"Selected {gap.field}; question priority {attempt.priority_score}/100; process completeness {attempt.process_score}; status {gap.status}.", gap.id)
    return attempt


def summary(session):
    state = refresh(session)
    unresolved = [g for g in state.gaps if g.status in OPEN]
    pending = pending_sources(session)
    return {
        "parameters": asdict(CONFIG),
        "process_score": process_score(session),
        "dimensions": {
            "observation_quality": {"usable": sum(d.observation_usable for d in state.decisions if d.observation_confidence is not None),
                                    "total": sum(d.observation_confidence is not None for d in state.decisions)},
            "answer_sufficiency": {"pending_evidence": len(pending), "partial": sum(g.status == "partial" for g in state.gaps)},
            "rule_completeness": {"unresolved": len(unresolved), "total": len(state.gaps)},
            "consistency": {"disputed": sum(g.status == "disputed" for g in state.gaps)},
            "verification": {"verified": sum(g.status in {"verified", "not_applicable"} for g in state.gaps), "total": len(state.gaps)},
            "learner_correctness": {"method": "verified_rules_for_structured_cases; advisory_for_free_text"},
        },
        "debrief_complete": bool(state.decisions) and not unresolved and not pending,
        "open_critical": [g.id for g in unresolved if PRIORITY[g.field] == 0],
        "gaps": [g.model_dump() for g in state.gaps],
        "trace": [t.model_dump() for t in state.trace[-30:]],
    }


def clear_derived(session):
    """Privacy/deletion invalidates all derived interpretations, not expert text."""
    from apprentice.domain import EvaluationState
    session.evaluation = EvaluationState()
