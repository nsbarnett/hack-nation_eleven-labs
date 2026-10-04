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


class Message(Contract):
    id: str = Field(default_factory=new_id)
    role: Literal["assistant", "user", "system"]
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


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


# Provider response contracts deliberately omit IDs and verification authority.
class SeenAction(Contract):
    summary: str
    evidence_ids: list[str]
    question: str
    novelty: int = Field(ge=0, le=3)
    ambiguity: int = Field(ge=0, le=3)
    significance: int = Field(ge=0, le=3)
    guardrail: bool


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


class MapResult(Contract):
    items: list[DraftKnowledge]
    teach_back: str
    gaps: list[str]


class TutorResult(Contract):
    verdict: Literal["ok", "warn", "unknown"]
    explanation: str
    knowledge_ids: list[str]


class TrainingCase(Contract):
    """The built-in purchase practice form. Other workflows use advisory tutoring."""
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    category: Literal["OPEX", "CAPEX"]
    asset_number: str
    supplier_status: Literal["known", "unknown"]
    purchase_type: str
    currency: str
