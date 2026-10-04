"""Shared contracts. AI proposes knowledge; only the application can verify it.

These Pydantic models are used at provider, persistence, and UI boundaries. IDs
link knowledge to source evidence rather than to an agent's private conversation.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return uuid4().hex


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Evidence(Contract):
    id: str = Field(default_factory=new_id)
    kind: Literal["screen", "note", "answer", "reference", "demo", "trainee_screen", "trainee_attempt", "trainee_note"]
    timestamp: float = 0
    text: str = ""
    image: str = ""  # Relative to this session's directory; never an arbitrary path.
    question: str = ""
    related_ids: list[str] = Field(default_factory=list)
    gap_id: str = ""  # Explicit answer binding; never infer the most recent decision.


class Observation(Contract):
    id: str = Field(default_factory=new_id)
    summary: str
    evidence_ids: list[str]
    question: str = ""
    novelty: int = Field(default=0, ge=0, le=3)
    ambiguity: int = Field(default=0, ge=0, le=3)
    significance: int = Field(default=0, ge=0, le=3)
    guardrail: bool = False
    asked: bool = False
    event_type: Literal["field_changed", "record_opened", "records_compared", "case_held", "action_reversed", "dependency_step", "step_completed", "navigation", "other"] = "other"
    case_id: str = ""
    field_name: str = ""
    before: str = ""
    after: str = ""
    before_readable: bool = False
    after_readable: bool = False
    before_was_default: bool = False
    confidence: float = Field(default=0, ge=0, le=1)
    fields_answered_on_screen: list[str] = Field(default_factory=list)


class Condition(Contract):
    field: str
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "present", "absent"]
    value: str


class RuleCheck(Contract):
    """An inspectable predicate, never executable model-generated Python."""
    conditions: list[Condition]
    field: str
    operator: Literal["eq", "ne", "present", "absent"]
    value: str


class Knowledge(Contract):
    id: str = Field(default_factory=new_id)
    title: str
    action: str
    decision: str
    reason: str
    rule: str
    exception: str
    guardrail: str
    escalation: str
    evidence_ids: list[str]
    check: RuleCheck | None = None
    status: Literal["inferred", "verified", "needs_clarification", "conflicting", "rejected"] = "inferred"
    decision_ids: list[str] = Field(default_factory=list)
    check_verified: bool = False


class Message(Contract):
    id: str = Field(default_factory=new_id)
    role: Literal["assistant", "user", "system"]
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class PrivacyReview(Contract):
    """Hosted screen evidence is eligible for AI only at this approved revision."""
    revision: int = Field(default=0, ge=0)
    status: Literal["unreviewed", "approved"] = "unreviewed"
    analyzed_frames: list[str] = Field(default_factory=list)
    question_revision: int = -1


class ReviewerPreferences(Contract):
    enabled: bool = False
    presentation: Literal["text", "voice", "both"] = "text"


GapField = Literal["reason", "rule", "scope", "threshold", "operator", "exception", "guardrail", "escalation", "contradiction", "cue"]
AssessmentOutcome = Literal["sufficient", "partial", "uncertain", "contradictory", "out_of_scope", "not_applicable"]


class EvidenceQuote(Contract):
    evidence_id: str
    quote: str


class FieldAssessment(Contract):
    decision_id: str
    field: GapField
    outcome: AssessmentOutcome
    claim: str
    citations: list[EvidenceQuote]
    confidence: float = Field(ge=0, le=1)
    rationale: str


class GapProposal(Contract):
    decision_id: str
    field: GapField
    description: str
    evidence_ids: list[str]


class AssessmentResult(Contract):
    assessments: list[FieldAssessment] = Field(max_length=100)
    gaps: list[GapProposal] = Field(max_length=100)


class EvaluationDecision(Contract):
    id: str
    label: str
    evidence_ids: list[str]
    observation_confidence: float | None = None
    observation_usable: bool = True
    observation_reason: str = "Expert text; visual confidence does not apply."


class KnowledgeGap(Contract):
    id: str = Field(default_factory=new_id)
    decision_id: str
    field: GapField
    description: str
    evidence_ids: list[str]
    status: Literal["open", "partial", "observed", "expert_stated", "verified", "disputed", "not_applicable"] = "open"
    claim: str = ""
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    verified_by: list[str] = Field(default_factory=list)


class QuestionAttempt(Contract):
    id: str = Field(default_factory=new_id)
    gap_id: str
    text: str
    evidence_ids: list[str]
    phase: Literal["live", "debrief"] = "debrief"
    state: Literal["asking", "answered", "deferred", "cancelled"] = "asking"
    answer_id: str = ""
    timestamp: float = 0
    priority_score: float = 0
    process_score: float | None = None


class EvaluationTrace(Contract):
    code: str
    gap_id: str = ""
    detail: str


class GapReview(Contract):
    gap_id: str
    evidence_id: str
    outcome: Literal["verified", "not_applicable"]


class EvaluationState(Contract):
    version: Literal[1] = 1
    decisions: list[EvaluationDecision] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    assessments: list[FieldAssessment] = Field(default_factory=list)
    assessed_evidence_ids: list[str] = Field(default_factory=list)
    attempts: list[QuestionAttempt] = Field(default_factory=list)
    reviews: list[GapReview] = Field(default_factory=list)
    trace: list[EvaluationTrace] = Field(default_factory=list)


class Session(Contract):
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=new_id)
    title: str
    context: str = ""
    mode: Literal["live", "demo"] = "live"
    created: str = Field(default_factory=utc_now)
    phase: Literal["capture", "debrief", "review", "teach"] = "capture"
    evidence: list[Evidence] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    knowledge: list[Knowledge] = Field(default_factory=list)
    recordings: list[str] = Field(default_factory=list)
    duration: float = 0
    revision: int = 0
    confirmed: bool = False
    privacy: PrivacyReview = Field(default_factory=PrivacyReview)
    evaluation: EvaluationState = Field(default_factory=EvaluationState)
    reviewer: ReviewerPreferences = Field(default_factory=ReviewerPreferences)


# Provider response contracts deliberately omit IDs and verification authority.
class SeenAction(Contract):
    summary: str
    evidence_ids: list[str]
    question: str
    novelty: int = Field(ge=0, le=3)
    ambiguity: int = Field(ge=0, le=3)
    significance: int = Field(ge=0, le=3)
    guardrail: bool


class SeenEvent(Contract):
    """Current provider contract; legacy SeenAction remains loadable by older clients."""
    summary: str
    evidence_ids: list[str]
    event_type: Literal["field_changed", "record_opened", "records_compared", "case_held", "action_reversed", "dependency_step", "step_completed", "navigation", "other"]
    case_id: str
    field_name: str
    before: str
    after: str
    before_readable: bool
    after_readable: bool
    before_was_default: bool
    confidence: float = Field(ge=0, le=1)
    fields_answered_on_screen: list[GapField]


class EventResult(Contract):
    actions: list[SeenEvent] = Field(max_length=3)


class ObservationResult(Contract):
    actions: list[SeenAction]


class QuestionResult(Contract):
    question: str
    evidence_ids: list[str]


class DraftKnowledge(Contract):
    title: str
    action: str
    decision: str
    reason: str
    rule: str
    exception: str
    guardrail: str
    escalation: str
    evidence_ids: list[str]
    check: RuleCheck | None
    needs_clarification: bool
    decision_ids: list[str] = Field(default_factory=list)


class MapResult(Contract):
    items: list[DraftKnowledge]
    teach_back: str
    gaps: list[str]


class TutorJudgment(Contract):
    verdict: Literal["ok", "warn", "unknown"]
    explanation: str
    knowledge_ids: list[str]


class TutorResult(TutorJudgment):
    evaluation_method: Literal["advisory", "verified_rules"] = "advisory"


class TrainingCase(Contract):
    """The built-in purchase practice form. Other workflows use advisory tutoring."""
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    category: Literal["OPEX", "CAPEX"]
    asset_number: str
    supplier_status: Literal["known", "unknown"]
    purchase_type: str
    currency: str
