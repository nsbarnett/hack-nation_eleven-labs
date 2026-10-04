"""
confidence.py - rule-based confidence scoring for the AI Apprentice question controller.

Mirrors the flowchart:
  step 2  Event understanding      -> score_observation()   how far we trust what the vision model saw
  step 3  Knowledge-gap check      -> gap_value()           how much a still-unknown field matters
  step 5  Question rubric          -> run_rubric()          4 hard gates (grounded / not answered by
                                                            screen / no assumption / seeks missing knowledge)
  step 6  Timing                   -> score_readiness()     is this a safe moment to speak

Everything here is deterministic and explainable. Per the behavior spec, all weights and thresholds are
INITIAL SANDBOX TUNING VALUES, not validated numbers. They live in ScoringConfig / TimingConfig so they
can be tuned in one place.

Observation confidence (can we trust the screen read?) is deliberately kept SEPARATE from knowledge
status (do we know the expert's rule?). A high-confidence observation never implies a known reason.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------------------
# Shared vocabulary
# --------------------------------------------------------------------------------------
class Band(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EventType(str, Enum):
    FIELD_CHANGED = "field_changed"            # e.g. cost center 4711 -> 0400
    RECORD_OPENED = "record_opened"            # prior invoice / supplier history opened
    RECORDS_COMPARED = "records_compared"
    CASE_HELD = "case_held"                    # held, flagged, sent for extra approval
    ACTION_REVERSED = "action_reversed"        # undo / contradiction of earlier action
    DEPENDENCY_STEP = "dependency_step"        # unexpected prerequisite step
    STEP_COMPLETED = "step_completed"
    NAVIGATION = "navigation"                  # routine: next invoice, scrolling, tabs
    IDLE = "idle"
    NOVICE_DECISION_POINT = "novice_decision_point"   # tutor mode
    OTHER = "other"


class FieldStatus(str, Enum):
    UNKNOWN = "unknown"
    KNOWN_ON_SCREEN = "known_on_screen"
    EXPERT_STATED = "expert_stated"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"


OPEN_STATUSES = (FieldStatus.UNKNOWN, FieldStatus.DISPUTED)


def to_band(value: float, high: float = 0.7, medium: float = 0.5) -> Band:
    return Band.HIGH if value >= high else Band.MEDIUM if value >= medium else Band.LOW


# --------------------------------------------------------------------------------------
# Inputs: screen events and per-decision knowledge
# --------------------------------------------------------------------------------------
@dataclass
class ScreenEvent:
    """One structured event from the vision model. Events, not narrative summaries."""
    id: str
    ts: float                                   # session clock (seconds) when the event was emitted
    type: EventType
    case_id: str                                # e.g. "invoice-4471"
    decision_id: Optional[str] = None           # groups events/gaps belonging to one decision
    field_name: Optional[str] = None            # e.g. "cost_center"
    before: Optional[str] = None
    after: Optional[str] = None
    before_readable: bool = True
    after_readable: bool = True
    was_default: bool = False                   # 'before' was the displayed default value
    vision_confidence: Optional[float] = None   # 0..1 as reported by the vision model
    instrumented: bool = False                  # value read from controlled-page state, not pixels
    frame_ts: Optional[float] = None            # when the analysed frame was captured (for latency)
    answered_on_screen: frozenset = frozenset() # knowledge fields the screen already states
    summary: str = ""

    @staticmethod
    def from_vision_json(d: dict, ts: float) -> "ScreenEvent":
        """Build from the JSON the vision prompt (see VISION_PROMPT_ADDENDUM) returns."""
        return ScreenEvent(
            id=d["event_id"], ts=ts, type=EventType(d.get("event_type", "other")),
            case_id=d.get("case_id") or "unknown", decision_id=d.get("decision_id") or None,
            field_name=d.get("field_name") or None, before=d.get("before") or None, after=d.get("after") or None,
            before_readable=d.get("before_readable", True), after_readable=d.get("after_readable", True),
            was_default=d.get("before_was_default", False),
            vision_confidence=d.get("confidence"), instrumented=d.get("instrumented", False),
            frame_ts=d.get("frame_ts"),
            answered_on_screen=frozenset(d.get("fields_answered_on_screen", [])),
            summary=d.get("summary", ""),
        )


# Ask the person owning the vision model to add these to their prompt / output schema.
VISION_PROMPT_ADDENDUM = """
Return STRICT JSON, one object per meaningful change (omit anything that is only cursor movement or scrolling):
{
  "event_id": "evt-<n>",
  "event_type": "field_changed | record_opened | records_compared | case_held | action_reversed |
                 dependency_step | step_completed | navigation | idle | other",
  "case_id": "<invoice/ticket number visible on screen>",
  "decision_id": "",                  // leave empty: code derives it from case_id + field_name
  "field_name": "<field that changed, e.g. cost_center>",
  "before": "<value before>",  "after": "<value after>",
  "before_readable": true|false,  "after_readable": true|false,
  "before_was_default": true|false,   // was 'before' a pre-filled default rather than something the user typed?
  "fields_answered_on_screen": [],    // knowledge the screen ALREADY states, e.g. ["guardrail"] if a banner says
                                      // "On hold: asset number missing". Allowed: reason, guardrail,
                                      // escalation_authority, threshold, exception
  "confidence": 0.0-1.0,              // how sure you are of before/after and the event type
  "summary": "<one factual sentence, no inferred reasons>"
}
Never infer WHY the user did something. If a value is blurry or cut off, set *_readable=false.
""".strip()


@dataclass
class DecisionRecord:
    """What we currently know about one decision. Field names match QuestionSpec.field."""
    decision_id: str
    case_id: str
    fields: dict = field(default_factory=dict)          # field -> FieldStatus (absent == UNKNOWN)
    flags: set = field(default_factory=set)             # situation flags (event- or utterance-derived)
    slots: dict = field(default_factory=dict)           # expert-CONFIRMED values for placeholders
    event_ids: list = field(default_factory=list)
    utterance_ids: list = field(default_factory=list)
    revoked: bool = False

    def status(self, name: str) -> FieldStatus:
        return self.fields.get(name, FieldStatus.UNKNOWN)


# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoringConfig:
    max_vision_latency_s: float = 4.0     # slower than this -> screen state stale, hold decisions
    unreadable_cap: float = 0.35          # cap when before/after cannot be read
    stale_cap: float = 0.20
    instrumented_floor: float = 0.85      # reliably instrumented fields read as high confidence
    default_vision_conf: float = 0.50     # when the vision model gives no confidence
    min_obs_live: float = 0.50            # below this we do not interrupt live
    min_obs_debrief: float = 0.40         # retrospective questions tolerate weaker evidence, but not unreadable values
    w_obs: float = 0.5
    w_gap: float = 0.5
    accept_threshold: float = 0.55
    # spec: critical guardrail gap > exception boundary > missing reason > everything else
    gap_by_rank: tuple = (1.0, 0.8, 0.6, 0.4)


@dataclass(frozen=True)
class TimingConfig:
    cooldown_s: float = 45.0              # spec initial value
    max_live_per_10min: int = 5           # spec initial value
    quiet_s: float = 3.0                  # ONE readiness feature, never sufficient alone


# --------------------------------------------------------------------------------------
# Step 2: observation confidence
# --------------------------------------------------------------------------------------
@dataclass
class ObservationScore:
    value: float
    band: Band
    stale: bool
    reasons: list


def score_observation(ev: ScreenEvent, cfg: ScoringConfig = ScoringConfig()) -> ObservationScore:
    reasons = []
    v = ev.vision_confidence if ev.vision_confidence is not None else cfg.default_vision_conf
    reasons.append(f"vision confidence {v:.2f}")

    needs_values = ev.type in (EventType.FIELD_CHANGED, EventType.ACTION_REVERSED)
    if needs_values and not (ev.before_readable and ev.after_readable):
        v = min(v, cfg.unreadable_cap)
        reasons.append("before/after not both readable -> capped")
    elif ev.instrumented:
        v = max(v, cfg.instrumented_floor)
        reasons.append("value read from instrumented page state -> floor raised")

    stale = False
    if ev.frame_ts is not None and (ev.ts - ev.frame_ts) > cfg.max_vision_latency_s:
        stale = True
        v = min(v, cfg.stale_cap)
        reasons.append(f"vision latency {ev.ts - ev.frame_ts:.1f}s -> screen state stale, hold decisions")

    return ObservationScore(round(v, 3), to_band(v), stale, reasons)


# --------------------------------------------------------------------------------------
# Step 3: how much does this gap matter
# --------------------------------------------------------------------------------------
def gap_value(rank: int, ev: ScreenEvent, record: DecisionRecord, field_name: str,
              cfg: ScoringConfig = ScoringConfig()) -> float:
    """rank 0 = critical guardrail, 1 = exception/boundary, 2 = missing reason, 3 = other."""
    if record.status(field_name) not in OPEN_STATUSES:
        return 0.0                                   # nothing missing
    if ev.type in (EventType.NAVIGATION, EventType.IDLE) and not record.flags:
        return 0.0                                   # routine navigation: flowchart case E
    return cfg.gap_by_rank[min(rank, len(cfg.gap_by_rank) - 1)]


# --------------------------------------------------------------------------------------
# Step 5: question rubric (hard gates, in flowchart order)
# --------------------------------------------------------------------------------------
USEFUL_FIELDS = frozenset({
    "reason", "reversal_reason", "dependency_reason", "diagnostic_cue", "boundary_factor", "threshold",
    "operator", "contrast_condition", "exception", "scope", "consequence", "warning_cue", "guardrail",
    "never_rule", "escalation_authority", "stop_boundary", "novice_trap", "past_lesson", "authorization",
    "reliability_scope", "verification", "contradiction", "absence_response", "novice_prediction",
})

# Phrases the question library says to avoid: leading, blaming, bundling.
_LEADING = [
    r"\bright\?\s*$", r"\bisn'?t it\b", r"\bdidn'?t you\b", r"\bbecause (of|the|it)\b",
    r"\bmistake\b", r"\bwhy did you (make|do) that\b", r"\bexplain everything\b",
    r"\band the (rule|exception|amount|approver)\b.*\band the\b",
]


def is_leading(template: str) -> Optional[str]:
    """Check the TEMPLATE (placeholders stripped), never the expert-supplied slot text."""
    text = re.sub(r"\[[^\]]+\]", "", template)
    for rx in _LEADING:
        if re.search(rx, text, re.I):
            return rx
    if text.count("?") > 1:
        return "bundles several questions"
    return None


@dataclass
class RubricResult:
    passed: bool
    checks: dict                      # gate -> bool
    reject_code: Optional[str] = None
    reject_reason: str = ""


def run_rubric(*, target_field: str, template: str, ev: Optional[ScreenEvent],
               record: DecisionRecord, known_event_ids: set) -> RubricResult:
    checks = {}
    # 1. grounded in a screen event
    checks["grounded"] = bool(ev and ev.id in known_event_ids and ev.case_id == record.case_id)
    if not checks["grounded"]:
        return RubricResult(False, checks, "NOT_GROUNDED", "no matching screen event for this decision")
    # 2. the screen must not already answer it, and it must not already be explained
    answered = target_field in ev.answered_on_screen or record.status(target_field) not in OPEN_STATUSES
    checks["not_answered_by_screen"] = not answered
    if answered:
        return RubricResult(False, checks, "SCREEN_ANSWERS_IT", "already visible on screen or already explained")
    # 3. no unconfirmed assumption / leading phrasing
    leading = is_leading(template)
    checks["no_assumption"] = leading is None
    if leading:
        return RubricResult(False, checks, "UNSUPPORTED_ASSUMPTION", f"leading or bundled wording ({leading})")
    # 4. seeks genuinely missing, useful knowledge (reason / rule / guardrail / exception / cue)
    checks["seeks_missing_knowledge"] = target_field in USEFUL_FIELDS
    if not checks["seeks_missing_knowledge"]:
        return RubricResult(False, checks, "NOT_USEFUL", "off-topic: not a reason/rule/guardrail/exception/cue")
    return RubricResult(True, checks)


@dataclass
class CandidateScore:
    observation: ObservationScore
    gap: float
    rubric: RubricResult
    worth_asking: float
    band: Band
    verdict: str                      # ACCEPT | REJECT
    reasons: list


def score_candidate(*, rank: int, target_field: str, template: str, ev: Optional[ScreenEvent],
                    record: DecisionRecord, known_event_ids: set, live: bool,
                    cfg: ScoringConfig = ScoringConfig()) -> CandidateScore:
    rub = run_rubric(target_field=target_field, template=template, ev=ev, record=record,
                     known_event_ids=known_event_ids)
    if ev is None:
        obs = ObservationScore(0.0, Band.LOW, False, ["no event"])
    else:
        obs = score_observation(ev, cfg)
    gap = gap_value(rank, ev, record, target_field, cfg) if ev else 0.0
    worth = round(cfg.w_obs * obs.value + cfg.w_gap * gap, 3)
    reasons = list(obs.reasons) + [f"gap value {gap:.2f} (rank {rank})"]

    verdict = "ACCEPT"
    if not rub.passed:
        verdict = "REJECT"
        reasons.append(f"rubric: {rub.reject_code} - {rub.reject_reason}")
    elif obs.stale:
        verdict = "REJECT"
        reasons.append("stale screen state")
    elif obs.value < (cfg.min_obs_live if live else cfg.min_obs_debrief):
        verdict = "REJECT"
        reasons.append(f"LOW_OBSERVATION: {obs.value:.2f} below minimum")
    elif worth < cfg.accept_threshold:
        verdict = "REJECT"
        reasons.append(f"worth {worth:.2f} below accept threshold {cfg.accept_threshold}")
    return CandidateScore(obs, gap, rub, worth if verdict == "ACCEPT" else 0.0,
                          to_band(worth, 0.7, cfg.accept_threshold), verdict, reasons)


# --------------------------------------------------------------------------------------
# Step 6: readiness / timing
# --------------------------------------------------------------------------------------
@dataclass
class Readiness:
    """Snapshot of 'is it safe to speak', supplied by the app (voice activity + page + vision)."""
    user_speaking: bool = False
    agent_speaking: bool = False
    typing_active: Optional[bool] = None   # None = no typing telemetry in a shared tab
    screen_quiet_s: float = 0.0            # seconds with no visual change (from frame diffs)
    step_boundary: bool = False            # a step was just completed
    explicit_ready: bool = False           # expert pressed Ready / said "go ahead"
    critical_commit_active: bool = False   # e.g. mid-Save
    paused: bool = False
    off_record: bool = False
    screen_stale: bool = False
    # candidate-level suppressors used by the question library
    inspecting_record: bool = False        # still looking at the history record (Q03)
    comparison_ongoing: bool = False       # still comparing (Q09)
    urgent_correction: bool = False        # fixing an error right now (Q04)


@dataclass
class ReadinessResult:
    ready: bool
    band: Band
    blockers: list
    notes: list


def score_readiness(r: Readiness, now: float, cfg: TimingConfig, phase: str,
                    last_ask_ts: Optional[float], live_ask_times: list) -> ReadinessResult:
    """phase: 'live' (full gate) or 'conversational' (debrief / verify / tutor: just don't talk over anyone)."""
    blockers, notes = [], []
    if r.paused:
        blockers.append("paused")
    if r.off_record:
        blockers.append("off_record")
    if r.user_speaking:
        blockers.append("user_speaking")
    if r.agent_speaking:
        blockers.append("agent_speaking")

    if phase == "live":
        if r.typing_active:
            blockers.append("typing_active")
        if r.critical_commit_active:
            blockers.append("critical_commit")
        if r.screen_stale:
            blockers.append("screen_stale")
        if last_ask_ts is not None and now - last_ask_ts < cfg.cooldown_s:
            blockers.append(f"cooldown ({cfg.cooldown_s - (now - last_ask_ts):.0f}s left)")
        if sum(1 for t in live_ask_times if now - t < 600) >= cfg.max_live_per_10min:
            blockers.append("question_budget (5 per 10 min)")

        quiet_ok = r.screen_quiet_s >= cfg.quiet_s
        telemetry = r.typing_active is not None
        if r.explicit_ready:
            permission = True
            notes.append("explicit Ready permission")
        elif r.step_boundary and quiet_ok and telemetry:
            permission = True
            notes.append("completed-step boundary + quiet + typing telemetry")
        else:
            permission = False
            if r.step_boundary and quiet_ok and not telemetry:
                notes.append("no typing telemetry in shared tab: explicit Ready required")
            blockers.append("no_permission (needs step boundary + quiet, or explicit Ready)")
        # note: a quiet interval alone never grants permission
    ready = not blockers
    band = Band.HIGH if ready else Band.MEDIUM if blockers == ["no_permission (needs step boundary + quiet, or explicit Ready)"] else Band.LOW
    return ReadinessResult(ready, band, blockers, notes)
