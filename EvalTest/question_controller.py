"""
question_controller.py - decides WHETHER, WHEN and WHICH question the AI Apprentice asks.

Implements the behavior spec's controller:
  on event      -> store observation, update gaps, enqueue ONE candidate per (decision, missing field)
  on utterance  -> cancel candidates the expert answered unprompted, add new flags/candidates
  on readiness  -> decide(): ASK_NOW / QUEUE / SUPPRESS for the single highest-priority eligible candidate
  on Finish     -> DEBRIEF: one question at a time, track completion
  VERIFY / TEACH hooks for Q23, Q24 and Q26, plus the pre-Save guardrail intervention

Scoring lives in confidence.py. Candidate priority is an ORDINAL tuple, as the spec asks, not a numeric
information-gain model: (critical guardrail > exception/boundary > missing reason > other), then clearer
evidence, then older unresolved event.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

try:                                   # works as a package (apprentice/asking/) or as loose files
    from .confidence import (
        OPEN_STATUSES, Band, CandidateScore, DecisionRecord, EventType, FieldStatus, Readiness,
        ScoringConfig, ScreenEvent, TimingConfig, score_candidate, score_readiness,
    )
except ImportError:
    from confidence import (
        OPEN_STATUSES, Band, CandidateScore, DecisionRecord, EventType, FieldStatus, Readiness,
        ScoringConfig, ScreenEvent, TimingConfig, score_candidate, score_readiness,
    )


# --------------------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------------------
class SessionState(str, Enum):
    READY = "READY"
    CAPTURE = "CAPTURE"
    DEBRIEF = "DEBRIEF"
    VERIFY = "VERIFY"
    MAP_CONFIRMED = "MAP_CONFIRMED"
    TEACH = "TEACH"
    COMPLETE = "COMPLETE"


class QState(str, Enum):
    CANDIDATE = "CANDIDATE"
    QUEUED = "QUEUED"
    ASKING = "ASKING"
    ANSWERED = "ANSWERED"
    SUPPRESSED = "SUPPRESSED"
    EXPIRED = "EXPIRED"


class Action(str, Enum):
    ASK_NOW = "ASK_NOW"
    QUEUE = "QUEUE"
    SUPPRESS = "SUPPRESS"


LIVE, DEBRIEF, VERIFY, TUTOR = "live", "debrief", "verify", "tutor"
_STATE_PHASE = {SessionState.CAPTURE: LIVE, SessionState.DEBRIEF: DEBRIEF,
                SessionState.VERIFY: VERIFY, SessionState.TEACH: TUTOR}


# --------------------------------------------------------------------------------------
# Question library (verbatim from AI_Apprentice_Question_Library.docx)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class QuestionSpec:
    id: str
    purpose: str
    template: str
    phases: frozenset
    field: str                          # knowledge field this question fills
    rank: int                           # 0 critical guardrail, 1 exception/boundary, 2 reason, 3 other
    flags_all: frozenset = frozenset()  # all must be present
    flags_any: frozenset = frozenset()  # at least one must be present (if non-empty)
    required_slots: frozenset = frozenset()   # placeholders with NO safe fallback (never invent values)
    fallbacks: tuple = ()               # ((slot, safe default), ...)
    suppress_flags: frozenset = frozenset()   # record flags that suppress it
    suppress_readiness: frozenset = frozenset()  # Readiness attributes that suppress it right now


def _S(id, purpose, template, phases, fld, rank, all=(), any=(), slots=(), fb=(), sf=(), sr=()):
    return QuestionSpec(id, purpose, template, frozenset(phases), fld, rank, frozenset(all), frozenset(any),
                        frozenset(slots), tuple(fb), frozenset(sf), frozenset(sr))


LIBRARY: tuple = (
    _S("Q01", "Reason", "What made you change that classification?", [LIVE], "reason", 2, all=["default_changed"]),
    _S("Q02", "Cue", "What first caught your attention in this case?", [LIVE], "diagnostic_cue", 2, all=["looked_wrong"]),
    _S("Q03", "History", "What were you checking in that history?", [LIVE], "diagnostic_cue", 2,
       all=["history_opened"], sr=["inspecting_record"]),
    _S("Q04", "Reversal", "What changed your decision?", [LIVE], "reversal_reason", 2,
       all=["action_reversed"], sr=["urgent_correction"]),
    _S("Q05", "Reason", "Why was that step necessary before you could continue?", [LIVE], "dependency_reason", 2,
       all=["unexpected_dependency"], sf=["routine_navigation"]),
    _S("Q06", "Boundary", "Which factor changes the decision most here?", [LIVE, DEBRIEF], "boundary_factor", 1,
       all=["depends_or_usually"]),
    _S("Q07", "Threshold", "What is the cutoff, and which value does it apply to?", [DEBRIEF], "threshold", 1,
       all=["amount_rule_no_threshold"]),
    _S("Q08", "Exact boundary", "What happens when the value is exactly [cutoff]?", [DEBRIEF], "operator", 1,
       all=["operator_unclear"], slots=["cutoff"]),
    _S("Q09", "Comparison", "Which difference between those records mattered?", [LIVE], "diagnostic_cue", 2,
       all=["records_compared"], sr=["comparison_ongoing"]),
    _S("Q10", "Alternative", "What would make you choose the other option?", [DEBRIEF], "contrast_condition", 1,
       all=["decision_made"], sf=["other_option_unavailable"]),
    _S("Q11", "Exception", "What is the closest case where this rule would not apply?", [DEBRIEF], "exception", 1,
       all=["general_rule"], sf=["hard_prohibition"]),
    _S("Q12", "Scope", "Does that apply to all [case_types] or just this one?", [DEBRIEF], "scope", 1,
       all=["single_case_generalized"], fb=[("case_types", "cases like this one")]),
    _S("Q13", "Risk", "What could go wrong if someone proceeded here?", [LIVE], "consequence", 1,
       any=["case_held", "unusual_check"]),
    _S("Q14", "Warning", "What is the earliest sign that this case is going off track?", [DEBRIEF], "warning_cue", 1,
       all=["failure_history"]),
    _S("Q15", "Guardrail", "What needs to be resolved before this can proceed?", [LIVE], "guardrail", 0,
       any=["case_held", "missing_evidence"]),
    _S("Q16", "Never rule", "Is there anything you would never do in this situation?", [DEBRIEF], "never_rule", 0,
       all=["hazardous_shortcut"]),
    _S("Q17", "Escalation", "Who can decide whether this hold can be released?", [DEBRIEF], "escalation_authority", 0,
       all=["hold_rule_known"]),
    _S("Q18", "Escalation", "What uncertainty would make you stop and ask someone?", [DEBRIEF], "stop_boundary", 0,
       all=["partial_evidence_proceed"], sf=["unsafe_trial"]),
    _S("Q19", "Novice trap", "What would a beginner most likely miss in this case?", [DEBRIEF], "novice_trap", 3,
       all=["non_obvious_confirmed"]),
    _S("Q20", "Past lesson", "Was there a previous case that taught you to check this?", [DEBRIEF], "past_lesson", 3,
       all=["lesson_invoked"]),
    _S("Q21", "Authority", "Is that an approved rule, a local convention, or your preferred method?", [DEBRIEF],
       "authorization", 3, all=["always_do_this"]),
    _S("Q22", "Confidence", "Where does this explanation stop being reliable?", [DEBRIEF], "reliability_scope", 3,
       all=["heuristic_confident"]),
    _S("Q23", "Verification", "Is this rule accurate for [scope], or what should I change?", [VERIFY], "verification", 0,
       all=["map_condition_ready"], slots=["scope"]),
    _S("Q24", "Contradiction", "Earlier you said [A], and here you said [B]. Do different conditions explain that?",
       [DEBRIEF], "contradiction", 1, all=["contradiction"], slots=["A", "B"]),
    _S("Q25", "Missing evidence", "What would you do if [required_evidence] were missing?", [DEBRIEF],
       "absence_response", 0, all=["requirement_confirmed"], slots=["required_evidence"]),
    _S("Q26", "Novice prediction", "Before choosing, which cue changes the decision in this case?", [TUTOR],
       "novice_prediction", 2, all=["novice_in_scope_decision"]),
)
SPEC_BY_ID = {s.id: s for s in LIBRARY}
ORDER = {s.id: i for i, s in enumerate(LIBRARY)}


def render(spec: QuestionSpec, slots: dict) -> Optional[str]:
    """Fill placeholders from CONFIRMED slots only. Returns None if a required value is missing."""
    values = dict(spec.fallbacks)
    values.update({k: v for k, v in slots.items() if v})
    if not spec.required_slots <= values.keys():
        return None
    return re.sub(r"\[(\w+)\]", lambda m: str(values.get(m.group(1), m.group(0))), spec.template)


# --------------------------------------------------------------------------------------
# Utterance tagging (heuristic stand-in; swap for an LLM tagger via QuestionController(tagger=...))
# --------------------------------------------------------------------------------------
@dataclass
class Tags:
    fields_addressed: set = field(default_factory=set)
    flags: set = field(default_factory=set)
    slots: dict = field(default_factory=dict)


_R = lambda p: re.compile(p, re.I)
_FIELD_RX = {
    "reason": _R(r"\b(because|since|that'?s why|so that|otherwise|the rule is|policy|always|never|must)\b"),
    "guardrail": _R(r"\b(stop and ask|escalat\w*|approval|hold|can'?t (book|post)|do not (book|post)|never|without)\b"),
    "escalation_authority": _R(r"\b(controller|manager|supervisor|approver|finance lead)\b"),
    "threshold": _R(r"\d{3,}|\b\d+\s?k\b"),
    "exception": _R(r"\b(except|unless|apart from|but not|not for)\b"),
    "boundary_factor": _R(r"\b(depends on|main factor|the deciding)\b"),
}
_FLAG_RX = {
    "depends_or_usually": _R(r"\b(depends|usually|normally|generally|typically|most of the time)\b"),
    "looked_wrong": _R(r"\b(looks? (wrong|off|odd|weird)|looked (wrong|off|odd)|just know|gut feel|feels? off|something'?s off)\b"),
    "general_rule": _R(r"\b(always|every|all|any)\b"),
    "single_case_generalized": _R(r"\b(always|every|all|any)\b"),
    "failure_history": _R(r"\b(double[- ]bill\w*|last time|got burned|once (had|got)|bit us)\b"),
    "lesson_invoked": _R(r"\b(learned the hard way|last time|got burned|years ago|that taught me)\b"),
    "hazardous_shortcut": _R(r"\b(irreversible|can'?t (be )?undo\w*|cannot (be )?undo\w*|shortcut)\b"),
    "hold_rule_known": _R(r"\b(hold|on hold|release)\b"),
    "partial_evidence_proceed": _R(r"\b(good enough|proceed anyway|even though|without waiting|go ahead anyway)\b"),
    "always_do_this": _R(r"\b(we always do|that'?s how we do|workaround|my way|i prefer|nobody checks|unwritten)\b"),
    "heuristic_confident": _R(r"\b(rule of thumb|never fails|always works|trust me|definitely|for sure)\b"),
    "requirement_confirmed": _R(r"\b(must have|required|requires?|need(s)? (an?|the) )"),
}
_NUM = _R(r"(\d[\d.,]*\s?(?:k|€|eur|usd)?)")
_OVER = _R(r"\b(over|above|under|below|more than|less than)\b")
_INCLUSIVE = _R(r"\b(at least|or more|or less|exactly|inclusive|equal)\b|>=|≥")
_AMOUNTISH = _R(r"\b(amount|over|above|too (high|large|big)|large|expensive|big)\b")
_REQ = _R(r"(?:need(?:s)?|require[sd]?|must have)\s+(?:an?|the)\s+([\w\- ]{3,30}?)(?:[.,;]|$| before| to )")


def tag_utterance(text: str) -> Tags:
    t = Tags()
    for name, rx in _FIELD_RX.items():
        if rx.search(text):
            t.fields_addressed.add(name)
    # 'reason' given also resolves reversal/dependency reasons
    if "reason" in t.fields_addressed:
        t.fields_addressed |= {"reversal_reason", "dependency_reason"}
    for name, rx in _FLAG_RX.items():
        if rx.search(text):
            t.flags.add(name)
    has_num = "threshold" in t.fields_addressed
    if _AMOUNTISH.search(text) and not has_num:
        t.flags.add("amount_rule_no_threshold")
    if has_num and _OVER.search(text) and not _INCLUSIVE.search(text):
        t.flags.add("operator_unclear")
        m = _NUM.search(text)
        if m:
            t.slots["cutoff"] = m.group(1).strip()
    m = _REQ.search(text)
    if m:
        t.slots["required_evidence"] = m.group(1).strip()
    return t


# --------------------------------------------------------------------------------------
# Candidates and decisions
# --------------------------------------------------------------------------------------
@dataclass
class Candidate:
    id: str
    spec: QuestionSpec
    decision_id: str
    event_id: str
    text: str
    score: CandidateScore
    created_ts: float
    state: QState = QState.QUEUED
    asked_ts: Optional[float] = None
    asked_in: Optional[str] = None          # phase it was actually asked in
    answer_utterance_id: Optional[str] = None
    deferred: bool = False                  # expert pressed 'defer': only eligible again in debrief
    note: str = ""

    @property
    def key(self):
        return (self.decision_id, self.spec.field)

    def priority(self):
        # ordinal tuple: category rank, clearer evidence (higher obs first), older event first
        return (self.spec.rank, -self.score.observation.value, self.created_ts, ORDER[self.spec.id])


@dataclass
class Decision:
    action: Action
    reason: str
    question_id: Optional[str] = None
    candidate_id: Optional[str] = None
    text: Optional[str] = None              # exactly what the agent should say
    anchor: Optional[str] = None            # spoken lead-in when asked away from its live moment
    blockers: list = field(default_factory=list)
    score: Optional[CandidateScore] = None
    critical: bool = False


@dataclass
class DebriefStatus:
    followups_done: int
    open_critical: list
    open_contradictions: list
    explicit_unknowns: list
    complete: bool


# --------------------------------------------------------------------------------------
# Controller
# --------------------------------------------------------------------------------------
class QuestionController:
    def __init__(self, scoring: ScoringConfig = ScoringConfig(), timing: TimingConfig = TimingConfig(),
                 tagger: Callable[[str], Tags] = tag_utterance, min_debrief_followups: int = 3,
                 live_expiry_s: float = 120.0):
        self.scoring, self.timing, self.tagger = scoring, timing, tagger
        self.min_debrief_followups = min_debrief_followups
        self.live_expiry_s = live_expiry_s   # a live-only question goes stale after this long; debrief re-asks it
        self.state = SessionState.READY
        self.events: dict = {}
        self.records: dict = {}
        self.candidates: dict = {}          # candidate id -> Candidate
        self.rejected: list = []            # rubric/score rejects, kept for audit and demo explanations
        self.unknowns: list = []            # explicit remaining unknowns after debrief
        self.live_ask_times: list = []
        self.last_ask_ts: Optional[float] = None
        self.current_case: Optional[str] = None
        self.log: list = []                 # human-readable trace: answers "when / what to ask"
        self._n = 0

    # ---- helpers -----------------------------------------------------------
    def _id(self, prefix):
        self._n += 1
        return f"{prefix}-{self._n}"

    def _phase(self):
        return _STATE_PHASE.get(self.state)

    def _say(self, msg):
        self.log.append(msg)

    @property
    def active(self) -> Optional[Candidate]:
        return next((c for c in self.candidates.values() if c.state == QState.ASKING), None)

    def _record(self, decision_id, case_id) -> DecisionRecord:
        return self.records.setdefault(decision_id, DecisionRecord(decision_id, case_id))

    # ---- state transitions --------------------------------------------------
    def start_capture(self):
        self.state = SessionState.CAPTURE

    def on_finish(self, ts: float):
        """Expert pressed Finish: enter DEBRIEF, defer live candidates, rescan every decision for gaps."""
        self.state = SessionState.DEBRIEF
        for rec in self.records.values():
            if not rec.revoked and rec.event_ids:
                self._generate(rec, ts)

    def enter_verify(self, items: list):
        """items: [{'decision_id':..., 'scope': 'equipment invoices over EUR 5,000'}, ...]"""
        self.state = SessionState.VERIFY
        for it in items:
            rec = self.records[it["decision_id"]]
            rec.flags.add("map_condition_ready")
            rec.slots["scope"] = it["scope"]
            self._generate(rec, 0.0)

    def confirm_map(self):
        self.state = SessionState.MAP_CONFIRMED

    def start_teach(self):
        self.state = SessionState.TEACH

    # ---- on event -----------------------------------------------------------
    def on_event(self, ev: ScreenEvent) -> list:
        self.events[ev.id] = ev
        if ev.case_id not in ("unknown", None):
            self.current_case = ev.case_id
        if not ev.decision_id or ev.type in (EventType.NAVIGATION, EventType.IDLE, EventType.STEP_COMPLETED):
            return []                                    # observation only; no invented reason
        rec = self._record(ev.decision_id, ev.case_id)
        if rec.revoked:
            return []
        rec.event_ids.append(ev.id)
        derived = {
            EventType.FIELD_CHANGED: {"decision_made"} | ({"default_changed"} if ev.was_default else set()),
            EventType.RECORD_OPENED: {"history_opened"},
            EventType.RECORDS_COMPARED: {"records_compared"},
            EventType.CASE_HELD: {"case_held"},
            EventType.ACTION_REVERSED: {"action_reversed"},
            EventType.DEPENDENCY_STEP: {"unexpected_dependency"},
            EventType.NOVICE_DECISION_POINT: {"novice_in_scope_decision"},
        }.get(ev.type, set())
        rec.flags |= derived
        for f in ev.answered_on_screen:                  # e.g. a visible 'On hold: asset number missing' banner
            if rec.status(f) == FieldStatus.UNKNOWN:
                rec.fields[f] = FieldStatus.KNOWN_ON_SCREEN
        return self._generate(rec, ev.ts)

    # ---- on utterance / answer ------------------------------------------------
    def on_utterance(self, ts: float, text: str, utt_id: Optional[str] = None,
                     decision_id: Optional[str] = None) -> list:
        """Unprompted expert speech. Cancels candidates it already answers and may add new ones."""
        utt_id = utt_id or self._id("utt")
        rec = self.records.get(decision_id) if decision_id else self._latest_record()
        if not rec or rec.revoked:
            return []
        tags = self.tagger(text)
        rec.utterance_ids.append(utt_id)
        for f in tags.fields_addressed:
            if rec.status(f) in OPEN_STATUSES:
                rec.fields[f] = FieldStatus.EXPERT_STATED
                for c in self.candidates.values():
                    if c.key == (rec.decision_id, f) and c.state in (QState.QUEUED, QState.CANDIDATE):
                        c.state = QState.SUPPRESSED
                        c.answer_utterance_id = utt_id
                        c.note = "answered spontaneously"
                        self._say(f"CANCEL {c.spec.id}: expert already explained '{f}' ({utt_id})")
        rec.flags |= tags.flags
        rec.slots.update(tags.slots)
        return self._generate(rec, ts)

    def on_answer(self, candidate_id: str, ts: float, text: str, utt_id: Optional[str] = None) -> list:
        c = self.candidates[candidate_id]
        utt_id = utt_id or self._id("utt")
        rec = self.records[c.decision_id]
        c.state, c.answer_utterance_id = QState.ANSWERED, utt_id
        rec.fields[c.spec.field] = FieldStatus.EXPERT_STATED
        rec.utterance_ids.append(utt_id)
        tags = self.tagger(text)
        tags.fields_addressed.discard(c.spec.field)
        for f in tags.fields_addressed:
            if rec.status(f) in OPEN_STATUSES:
                rec.fields[f] = FieldStatus.EXPERT_STATED
        rec.flags |= tags.flags
        rec.slots.update(tags.slots)
        self._say(f"ANSWERED {c.spec.id} ({utt_id}); follow-up flags: {sorted(tags.flags)}")
        return self._generate(rec, ts)

    def defer(self, candidate_id: str):
        """Expert deferred the question being asked: back to the queue, asked again only in debrief."""
        c = self.candidates[candidate_id]
        if c.state == QState.ASKING:
            c.state, c.deferred, c.note = QState.QUEUED, True, "deferred by expert"
            self._say(f"DEFER {c.spec.id}: moved to debrief")

    def release(self, candidate_id: str):
        """The ask was cancelled by the system (pause, off-record, session switch), not by the expert."""
        c = self.candidates[candidate_id]
        if c.state == QState.ASKING:
            c.state, c.note = QState.QUEUED, "ask cancelled before an answer"
            self._say(f"RELEASE {c.spec.id}: back in queue")

    def on_skip(self, candidate_id: str, reason: str = "expert declined"):
        """Expert skips (e.g. confidential): stays an explicit remaining unknown, never silently dropped."""
        c = self.candidates[candidate_id]
        c.state, c.note = QState.SUPPRESSED, reason
        self.unknowns.append((c.decision_id, c.spec.field, reason))

    def set_flag(self, decision_id: str, flag: str, ts: float, slots: Optional[dict] = None,
                 status: Optional[FieldStatus] = None, field_name: Optional[str] = None) -> list:
        """Escape hatch for LLM taggers / other modules (e.g. 'non_obvious_confirmed', 'contradiction')."""
        rec = self.records[decision_id]
        rec.flags.add(flag)
        rec.slots.update(slots or {})
        if field_name and status:
            rec.fields[field_name] = status
        return self._generate(rec, ts)

    def report_contradiction(self, decision_id: str, a: str, b: str, ts: float) -> list:
        rec = self.records[decision_id]
        rec.fields["contradiction"] = FieldStatus.DISPUTED
        return self.set_flag(decision_id, "contradiction", ts, {"A": a, "B": b})

    def _latest_record(self):
        for eid in reversed(list(self.events)):
            ev = self.events[eid]
            if ev.decision_id in self.records:
                return self.records[ev.decision_id]
        return None

    # ---- candidate generation (one per decision + missing field) --------------
    def _generate(self, rec: DecisionRecord, ts: float) -> list:
        phase = self._phase() or LIVE
        best = {}
        for spec in LIBRARY:
            if spec.flags_all and not spec.flags_all <= rec.flags:
                continue
            if spec.flags_any and not (spec.flags_any & rec.flags):
                continue
            if not spec.flags_all and not spec.flags_any:
                continue
            if spec.suppress_flags & rec.flags:
                self._say(f"SUPPRESS {spec.id}: suppression flag present")
                continue
            if rec.status(spec.field) not in OPEN_STATUSES:
                continue
            if spec.field in best and (best[spec.field].rank, ORDER[best[spec.field].id]) <= (spec.rank, ORDER[spec.id]):
                continue
            best[spec.field] = spec
        created = []
        for spec in best.values():
            key = (rec.decision_id, spec.field)
            prior = [c for c in self.candidates.values() if c.key == key]
            if any(c.state in (QState.QUEUED, QState.CANDIDATE, QState.ASKING, QState.ANSWERED) for c in prior):
                continue
            if any(c.state == QState.EXPIRED for c in prior) and self.state != SessionState.DEBRIEF:
                continue
            text = render(spec, rec.slots)
            if text is None:
                self._say(f"WAIT {spec.id} on {rec.decision_id}: required slot missing "
                          f"({sorted(spec.required_slots - rec.slots.keys())}); will not invent it")
                continue
            ev = self.events.get(rec.event_ids[-1]) if rec.event_ids else None
            sc = score_candidate(rank=spec.rank, target_field=spec.field, template=spec.template, ev=ev,
                                 record=rec, known_event_ids=set(self.events), live=LIVE in spec.phases,
                                 cfg=self.scoring)
            if sc.verdict == "REJECT":
                self.rejected.append((spec.id, rec.decision_id, sc.reasons[-1]))
                self._say(f"REJECT {spec.id} on {rec.decision_id}: {sc.reasons[-1]}")
                continue
            c = Candidate(self._id("cand"), spec, rec.decision_id, ev.id, text, sc, ts)
            self.candidates[c.id] = c
            created.append(c)
            self._say(f"QUEUE {spec.id} on {rec.decision_id} (worth {sc.worth_asking}, rank {spec.rank})")
        return created

    # ---- the decision -------------------------------------------------------------
    def _eligible(self, phase: str, now: float) -> list:
        out = []
        for c in self.candidates.values():
            if c.state not in (QState.QUEUED, QState.CANDIDATE):
                continue
            rec = self.records[c.decision_id]
            if rec.revoked:
                c.state, c.note = QState.SUPPRESSED, "revoked"
                continue
            if c.deferred and phase == LIVE:
                continue
            if phase == LIVE and DEBRIEF not in c.spec.phases and now - c.created_ts > self.live_expiry_s:
                c.state = QState.EXPIRED
                c.note = f"older than {self.live_expiry_s:.0f}s: moment has passed; event kept, debrief will re-ask"
                self._say(f"EXPIRE {c.spec.id} on {c.decision_id}: {c.note}")
                continue
            if rec.status(c.spec.field) not in OPEN_STATUSES:
                c.state, c.note = QState.SUPPRESSED, "answered before asking"
                self._say(f"CANCEL {c.spec.id}: field '{c.spec.field}' no longer missing")
                continue
            if phase in c.spec.phases or (phase == DEBRIEF and LIVE in c.spec.phases):
                out.append(c)
        return sorted(out, key=Candidate.priority)

    def decide(self, now: float, r: Readiness) -> Decision:
        phase = self._phase()
        if phase is None:
            return Decision(Action.SUPPRESS, f"no questions in state {self.state.value}")
        if r.paused or r.off_record:
            return Decision(Action.SUPPRESS, "paused / off record: no speech and no new capture",
                            blockers=["paused" if r.paused else "off_record"])
        if self.active:
            return Decision(Action.SUPPRESS, "one active question at a time", blockers=["active_question"])

        pool = self._eligible(phase, now)
        if not pool:
            return Decision(Action.SUPPRESS, "no eligible candidate (silence and dwell are not evidence of judgment)")

        usable = [c for c in pool if not any(getattr(r, f, False) for f in c.spec.suppress_readiness)]
        if not usable:
            names = sorted({f for c in pool for f in c.spec.suppress_readiness if getattr(r, f, False)})
            return Decision(Action.QUEUE, "candidate waiting: " + ", ".join(names), blockers=names)
        top = usable[0]

        res = score_readiness(r, now, self.timing, "live" if phase == LIVE else "conversational",
                              self.last_ask_ts, self.live_ask_times)
        if not res.ready:
            self._say(f"HOLD {top.spec.id}: {res.blockers}")
            return Decision(Action.QUEUE, "valuable question waits; not a safe moment",
                            question_id=top.spec.id, candidate_id=top.id, blockers=res.blockers, score=top.score)

        top.state, top.asked_ts, top.asked_in = QState.ASKING, now, phase
        self.last_ask_ts = now
        if phase == LIVE:
            self.live_ask_times.append(now)
        anchor = None
        ev = self.events[top.event_id]
        if phase in (DEBRIEF, VERIFY) or ev.case_id != self.current_case:   # away from its moment: say which case
            anchor = f"Going back to {ev.case_id}" + (f" ({ev.field_name})" if ev.field_name else "") + ":"
        self._say(f"ASK {top.spec.id} in {phase}: {'; '.join(res.notes) or 'conversational gate'}")
        return Decision(Action.ASK_NOW, "safe moment and highest-priority eligible gap", top.spec.id, top.id,
                        top.text, anchor, [], top.score)

    # ---- tutor: guardrail intervention (State 9) -----------------------------------
    def guardrail_intervention(self, r: Readiness, expert: str, condition: str, reason: str,
                               rule_id: str) -> Decision:
        """Imminent confirmed in-scope violation before Save. Overrides cooldown/budget/boundary timing;
        only an explicit pause or off-record stops it. The caller must keep Save blocked regardless."""
        if r.paused or r.off_record:
            return Decision(Action.SUPPRESS, "paused / off record", critical=True)
        text = f"Pause here. {expert} required {condition} because {reason}. What needs to change?"
        self._say(f"INTERVENE on {rule_id}: critical override, Save stays blocked")
        return Decision(Action.ASK_NOW, "imminent confirmed guardrail breach", "INTERVENTION", None, text,
                        critical=True)

    # ---- off record / revocation ----------------------------------------------------
    def revoke(self, event_ids=(), utterance_ids=()) -> list:
        """Cancel questions and mark dependent records revoked. Returns affected decision ids."""
        ev_ids, ut_ids, hit = set(event_ids), set(utterance_ids), []
        for rec in self.records.values():
            if ev_ids & set(rec.event_ids) or ut_ids & set(rec.utterance_ids):
                rec.revoked = True
                hit.append(rec.decision_id)
        for c in self.candidates.values():
            if c.decision_id in hit and c.state in (QState.QUEUED, QState.CANDIDATE, QState.ASKING):
                c.state, c.note = QState.SUPPRESSED, "revoked"
        self._say(f"REVOKE records {hit}: questions cancelled; map and tutor context must be rebuilt")
        return hit

    # ---- debrief / acceptance -------------------------------------------------------
    def debrief_status(self) -> DebriefStatus:
        done = [c for c in self.candidates.values() if c.state == QState.ANSWERED and c.asked_in == DEBRIEF]
        open_ = [c for c in self.candidates.values() if c.state in (QState.QUEUED, QState.CANDIDATE, QState.ASKING)]
        crit = [c.spec.id for c in open_ if c.spec.rank == 0 and VERIFY not in c.spec.phases]
        contra = [c.decision_id for c in open_ if c.spec.id == "Q24"]
        complete = len(done) >= self.min_debrief_followups and not crit and not contra
        return DebriefStatus(len(done), crit, contra, list(self.unknowns), complete)

    def acceptance_summary(self) -> dict:
        """Challenge requirements: >=3 live screen-grounded questions incl. >=1 guardrail; >=3 debrief follow-ups."""
        live = [c for c in self.candidates.values() if c.asked_in == LIVE]
        return {
            "live_questions_asked": len(live),
            "live_guardrail_asked": any(c.spec.rank == 0 for c in live),
            "all_live_grounded": all(c.event_id in self.events for c in live),
            "debrief_followups_answered": self.debrief_status().followups_done,
            "live_requirement_met": len(live) >= 3 and any(c.spec.rank == 0 for c in live),
            "debrief_requirement_met": self.debrief_status().followups_done >= 3,
        }
