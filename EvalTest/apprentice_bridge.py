"""
apprentice_bridge.py - connects the existing app (Observation / Knowledge / Evidence objects, the Qt
Controller) to question_controller.py + confidence.py.

Deliberately framework-agnostic: no Qt, no pydantic, no `apprentice.*` imports. It reads the app's objects
by attribute (duck typing), so it works unchanged if the team moves from the desktop app to a web backend.
Everything the other files must change is listed in INTEGRATION_NOTES.md.

Session clock: pass `session.duration` (seconds) as `now` everywhere, never time.monotonic(), so cooldowns
and event timestamps share one clock, as the spec requires.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

try:
    from .confidence import DecisionRecord, EventType, FieldStatus, Readiness, ScoringConfig, ScreenEvent, TimingConfig
    from .question_controller import Action, QuestionController, SessionState, Tags, tag_utterance
except ImportError:
    from confidence import DecisionRecord, EventType, FieldStatus, Readiness, ScoringConfig, ScreenEvent, TimingConfig
    from question_controller import Action, QuestionController, SessionState, Tags, tag_utterance


# --------------------------------------------------------------------------------------
# Config and output
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EngineConfig:
    typing_idle_s: float = 2.0          # OS input idle below this counts as 'typing_active'
    ready_window_s: float = 30.0        # how long a Ready press stays valid
    # The observer batches frames, so analysis latency is far larger than a per-frame pipeline.
    # 4s (the spec's single-frame starting value) would mark every batched event stale.
    max_vision_latency_s: float = 20.0
    fallback_confidence: float = 0.6    # used when the observer returns no confidence (legacy output)
    # Spec: idle/silence alone is never enough. Leave False unless the demo has no Ready button.
    allow_idle_boundary: bool = False
    idle_boundary_s: float = 8.0


@dataclass
class Plan:
    """What the app should say now. Feed `text` to the existing _ask(text, evidence_ids)."""
    text: str
    evidence_ids: list
    question_id: str
    candidate_id: Optional[str]
    reason: str
    critical: bool = False

    def to_dict(self):
        return self.__dict__.copy()


# --------------------------------------------------------------------------------------
# Legacy observation -> ScreenEvent (used only while the observer returns the old schema)
# --------------------------------------------------------------------------------------
_CASE = re.compile(r"(?:invoice|inv\.?|ticket|case)\s*#?\s*([A-Za-z0-9-]*\d[A-Za-z0-9-]*)|#(\d{3,})", re.I)
_CHANGED = re.compile(r"(?:changed|changes|set|updated|re-?coded|moved)\s+(?:the\s+)?([\w ]{2,30}?)\s+from\s+(.+?)\s+to\s+(.+?)(?=\s+(?:on|in|for|at|during)\s|[.;,]|$)", re.I)
_RX = [
    (EventType.ACTION_REVERSED, re.compile(r"\b(undid|undo|reverted|reversed|changed (?:it )?back)\b", re.I)),
    (EventType.CASE_HELD, re.compile(r"\b(held|on hold|flagged|escalat\w*|sent .{0,40}(?:approval|authori[sz]ation))\b", re.I)),
    (EventType.RECORDS_COMPARED, re.compile(r"\bcompar\w*", re.I)),
    (EventType.RECORD_OPENED, re.compile(r"\b(opened|viewed|looked at|checked)\b.{0,40}\b(history|previous|prior|past)\b", re.I)),
    (EventType.FIELD_CHANGED, _CHANGED),
    (EventType.NAVIGATION, re.compile(r"\b(opened (?:the )?next|navigat\w*|scroll\w*|switched (?:to )?tab|next invoice|opened invoice)\b", re.I)),
]


def classify_summary(summary: str) -> dict:
    """Best-effort fallback so the pipeline runs before the observer prompt/schema is upgraded."""
    out = {"type": EventType.OTHER, "case_id": "unknown", "field_name": None, "before": None, "after": None}
    m = _CASE.search(summary)
    if m:
        out["case_id"] = f"inv-{m.group(1) or m.group(2)}"
    for etype, rx in _RX:
        hit = rx.search(summary)
        if hit:
            out["type"] = etype
            if etype == EventType.FIELD_CHANGED:
                out["field_name"] = re.sub(r"\s+", "_", hit.group(1).strip().lower())
                out["before"], out["after"] = hit.group(2).strip(), hit.group(3).strip()
            break
    return out


def to_screen_event(obs, now: float, evidence_times: dict, cfg: EngineConfig) -> ScreenEvent:
    """obs: the app's Observation (or SeenAction). Uses rich fields when present, else the fallback."""
    g = lambda name, default=None: getattr(obs, name, default)
    etype_raw = g("event_type")
    frame_ts = max((evidence_times.get(e, 0.0) for e in obs.evidence_ids), default=None)
    if etype_raw and etype_raw != "other":
        etype = EventType(etype_raw)
        case_id = g("case_id") or "unknown"
        field_name, before, after = g("field_name") or None, g("before") or None, g("after") or None
        was_default = bool(g("before_was_default", False))
        conf = g("confidence")
        before_ok, after_ok = g("before_readable", True), g("after_readable", True)
        on_screen = frozenset(g("fields_answered_on_screen", []) or [])
    else:                                                   # legacy: infer from the summary text
        c = classify_summary(obs.summary)
        etype, case_id, field_name, before, after = c["type"], c["case_id"], c["field_name"], c["before"], c["after"]
        was_default = etype == EventType.FIELD_CHANGED      # stopgap: unknown whether before was a default
        conf, before_ok, after_ok, on_screen = cfg.fallback_confidence, True, True, frozenset()
    decision_id = g("decision_id") or None
    if not decision_id and etype not in (EventType.NAVIGATION, EventType.IDLE, EventType.OTHER, EventType.STEP_COMPLETED):
        decision_id = f"{case_id}:{field_name or etype.value}"
    return ScreenEvent(
        id=obs.id, ts=now, type=etype, case_id=case_id, decision_id=decision_id, field_name=field_name,
        before=before, after=after, before_readable=before_ok, after_readable=after_ok, was_default=was_default,
        vision_confidence=conf, instrumented=bool(g("instrumented", False)), frame_ts=frame_ts,
        answered_on_screen=on_screen, summary=obs.summary)


# --------------------------------------------------------------------------------------
# The engine the app talks to
# --------------------------------------------------------------------------------------
class QuestionEngine:
    def __init__(self, cfg: EngineConfig = EngineConfig(), timing: TimingConfig = TimingConfig(),
                 tagger=tag_utterance):
        self.cfg = cfg
        self.qc = QuestionController(ScoringConfig(max_vision_latency_s=cfg.max_vision_latency_s), timing, tagger)
        self._evidence_of_event: dict = {}
        self._ready_until = -1.0
        self._boundary = False
        self.last_decision = None

    # ---- lifecycle -------------------------------------------------------------------
    def begin_capture(self):
        self.qc.start_capture()

    def begin_debrief(self, now: float):
        self.qc.on_finish(now)

    @property
    def in_debrief(self) -> bool:
        return self.qc.state == SessionState.DEBRIEF

    def signal_ready(self, now: float):
        """Expert pressed Ready / said 'go ahead': grants permission to ask for a short window."""
        self._ready_until = now + self.cfg.ready_window_s

    # ---- inputs ----------------------------------------------------------------------
    def on_observations(self, observations: Iterable, now: float, evidence_times: dict) -> int:
        """Call with the observations the app ACTUALLY appended (after its own de-duplication)."""
        n = 0
        for obs in observations:
            self._evidence_of_event[obs.id] = list(obs.evidence_ids)
            ev = to_screen_event(obs, now, evidence_times, self.cfg)
            n += len(self.qc.on_event(ev))
            if ev.type in (EventType.NAVIGATION, EventType.STEP_COMPLETED):
                self._boundary = True                       # the expert moved on: a completed-step boundary
            elif ev.decision_id:
                self._boundary = False                      # new decision-bearing work started
        return n

    def on_note(self, text: str, now: float, evidence_id: str, answering: bool) -> int:
        """Every saved expert note/answer. `evidence_id` becomes the utterance id (provenance + revocation)."""
        active = self.qc.active
        if answering and active:
            return len(self.qc.on_answer(active.id, now, text, utt_id=evidence_id))
        return len(self.qc.on_utterance(now, text, utt_id=evidence_id))

    def on_defer(self):
        if self.qc.active:
            self.qc.defer(self.qc.active.id)

    def release_active(self):
        """Ask cancelled by the system (pause, off-record, session switch, invalidation)."""
        if self.qc.active:
            self.qc.release(self.qc.active.id)

    def revoke_evidence(self, evidence_id: str) -> list:
        events = [eid for eid, evs in self._evidence_of_event.items() if evidence_id in evs]
        return self.qc.revoke(event_ids=events, utterance_ids=[evidence_id])

    def sync_knowledge(self, items: Iterable, evidence: Iterable):
        """After buildMap / confirmMap / edits: mirror the Work Map into the controller's gap tracking.

        A field counts as known only if the expert supplied it: confirmed, or backed by an answer/note.
        Model-inferred text does not close a gap, so the apprentice still asks about it.
        """
        kinds = {e.id: e.kind for e in evidence}
        fmap = {"reason": "reason", "guardrail": "guardrail", "exception": "exception",
                "escalation": "escalation_authority"}
        for item in items:
            if getattr(item, "status", "") == "rejected":
                continue
            sources = set(item.evidence_ids)
            for rec in self.qc.records.values():
                rec_sources = {e for eid in rec.event_ids for e in self._evidence_of_event.get(eid, [])} | set(rec.utterance_ids)
                if not (sources & rec_sources):
                    continue
                expert_backed = any(kinds.get(e) in ("answer", "note") for e in sources)
                for attr, fld in fmap.items():
                    if not (getattr(item, attr, "") or "").strip():
                        continue
                    if item.status == "verified":
                        rec.fields[fld] = FieldStatus.CONFIRMED
                    elif item.status in ("needs_clarification", "conflicting"):
                        rec.fields[fld] = FieldStatus.DISPUTED
                    elif expert_backed and rec.status(fld) == FieldStatus.UNKNOWN:
                        rec.fields[fld] = FieldStatus.EXPERT_STATED

    def verify_plan(self, items: Iterable):
        """Optional: before confirmMap, queue a Q23 'is this rule accurate for [scope]?' per active rule."""
        batch = []
        for item in items:
            if getattr(item, "status", "") == "rejected":
                continue
            for rec in self.qc.records.values():
                if set(item.evidence_ids) & {e for eid in rec.event_ids for e in self._evidence_of_event.get(eid, [])}:
                    batch.append({"decision_id": rec.decision_id, "scope": item.title})
                    break
        if batch:
            self.qc.enter_verify(batch)

    # ---- the one call the app polls ------------------------------------------------------
    def poll(self, now: float, *, input_idle_s: float, screen_stable_s: float, user_speaking: bool,
             agent_speaking: bool, paused: bool = False, off_record: bool = False,
             critical_commit: bool = False) -> Optional[Plan]:
        boundary = self._boundary or (self.cfg.allow_idle_boundary and input_idle_s >= self.cfg.idle_boundary_s
                                      and screen_stable_s >= self.qc.timing.quiet_s)
        r = Readiness(
            user_speaking=user_speaking, agent_speaking=agent_speaking,
            typing_active=input_idle_s < self.cfg.typing_idle_s,      # desktop: real OS input idle
            screen_quiet_s=screen_stable_s, step_boundary=boundary,
            explicit_ready=now < self._ready_until, critical_commit_active=critical_commit,
            paused=paused, off_record=off_record)
        d = self.qc.decide(now, r)
        self.last_decision = d
        if d.action != Action.ASK_NOW:
            return None
        self._boundary = False
        text = f"{d.anchor} {d.text}" if d.anchor else d.text
        ev_ids = self._evidence_of_event.get(self.qc.candidates[d.candidate_id].event_id, [])
        return Plan(text, ev_ids, d.question_id, d.candidate_id, d.reason)

    # ---- tutor ---------------------------------------------------------------------------
    def intervention(self, knowledge_item, *, paused=False, off_record=False, expert="The expert") -> Optional[Plan]:
        """For a tutor 'warn' verdict: spec State 9 wording, overrides cooldown/budget/boundary timing."""
        d = self.qc.guardrail_intervention(
            Readiness(paused=paused, off_record=off_record), expert,
            (knowledge_item.guardrail or knowledge_item.rule).strip().rstrip("."),
            (knowledge_item.reason or "the expert's rule").strip().rstrip("."), knowledge_item.id)
        return Plan(d.text, list(knowledge_item.evidence_ids), "INTERVENTION", None, d.reason, True) \
            if d.action == Action.ASK_NOW else None

    # ---- for the UI / demo --------------------------------------------------------------------
    def status(self) -> dict:
        ds = self.qc.debrief_status()
        return {
            "state": self.qc.state.value,
            "queued": [{"question": c.spec.id, "decision": c.decision_id, "worth": c.score.worth_asking}
                       for c in self.qc.candidates.values() if c.state.value == "QUEUED"],
            "debrief": {"followups_done": ds.followups_done, "open_critical": ds.open_critical,
                        "open_contradictions": ds.open_contradictions, "complete": ds.complete,
                        "remaining_unknowns": ds.explicit_unknowns},
            "acceptance": self.qc.acceptance_summary(),
            "last_decision": [self.last_decision.reason, list(self.last_decision.blockers)] if self.last_decision else [],
        }

    @property
    def trace(self) -> list:
        """Human-readable log of every ask / hold / cancel: the answer to 'when' and 'what' to ask."""
        return self.qc.log
