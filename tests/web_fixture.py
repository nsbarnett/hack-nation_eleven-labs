"""Deterministic provider fixtures ONLY for browser automation; never used by backend.web."""
from pathlib import Path
import os
import time

from apprentice.agents.gateway import Gateway
from apprentice.config import Settings
from apprentice.domain import AssessmentResult, Condition, DraftKnowledge, EventResult, EvidenceQuote, FieldAssessment, GapProposal, MapResult, ObservationResult, QuestionResult, RuleCheck, SeenEvent, TutorJudgment, TutorResult
from backend.training import CaseValue, Exercises, Exercise
from backend.web import create_web_app


def request(self, schema, instructions, data, images=None):
    if ((schema is MapResult and data.get("task") == "Processing feedback fixture") or
            (schema is AssessmentResult and any("processing feedback fixture" in e["text"] for e in data["expert_evidence"]))):
        time.sleep(2)  # Make both actual backend stages observable across navigation.
    if schema is AssessmentResult:
        if any("interjection fixture" in e["text"] for e in data["expert_evidence"]):
            return AssessmentResult(assessments=[FieldAssessment(decision_id="text:"+e["id"], field="reason",
                outcome="uncertain", claim="", confidence=.9, rationale="The reported change has no explanation.",
                citations=[EvidenceQuote(evidence_id=e["id"], quote=e["text"])])
                for e in data["expert_evidence"] if e["id"] in data["pending_evidence_ids"]], gaps=[])
        return AssessmentResult(assessments=[FieldAssessment(decision_id=data["decisions"][0]["id"], field="rule",
            outcome="uncertain", claim="", confidence=.9, rationale="Synthetic fixture leaves the gap open.",
            citations=[EvidenceQuote(evidence_id=e["id"], quote=e["text"])])
            for e in data["expert_evidence"] if e["id"] in data["pending_evidence_ids"]], gaps=[])
    if schema is EventResult:
        if data["task"] == "Screen change fixture" and len(data["new_image_ids"]) >= 2 and not data["observations"]:
            return EventResult(actions=[SeenEvent(summary="Cost center changed", evidence_ids=data["new_image_ids"],
                event_type="field_changed", case_id="test-case", field_name="cost center", before="4711", after="0400",
                before_readable=True, after_readable=True, before_was_default=False, confidence=.98,
                fields_answered_on_screen=[])])
        return EventResult(actions=[])
    if schema is ObservationResult:
        return ObservationResult(actions=[])
    if schema is QuestionResult:
        return QuestionResult(question="What makes this check necessary?", evidence_ids=[data["evidence"][0]["id"]])
    if schema is MapResult:
        source = next((e for e in data["evidence"] if e["kind"] == "note"), data["evidence"][0])
        if data["task"] == "Structured evaluation workflow":
            return MapResult(items=[DraftKnowledge(title="Classify at the threshold", action="Inspect amount and currency",
                decision="CAPEX for EUR purchases at least 5000", reason=source["text"], rule="EUR purchases at least 5000 require CAPEX",
                exception="Other currencies are outside this rule", guardrail="Hold uncovered cases", escalation="Ask the expert",
                evidence_ids=[source["id"]], decision_ids=[data["decisions"][0]["id"]],
                check=RuleCheck(conditions=[Condition(field="amount", operator="gte", value="5000"), Condition(field="currency", operator="eq", value="EUR")],
                    field="category", operator="eq", value="CAPEX"), needs_clarification=False)], teach_back="Check the inclusive threshold.", gaps=[])
        return MapResult(items=[DraftKnowledge(title="Review the work", action="Review the current task",
            decision="Continue after review", reason=source["text"], rule="Review before proceeding",
            exception="Not established", guardrail="Ask when uncertain", escalation="Ask the expert",
            evidence_ids=[source["id"]], check=None, needs_clarification=False)], teach_back="Review before proceeding.", gaps=[])
    if schema is Exercises:
        if data["knowledge"][0].get("check_verified"):
            return Exercises(items=[Exercise(question="Classify this EUR purchase at exactly 5000.", knowledge_ids=[data["knowledge"][0]["id"]],
                scenario=[CaseValue(field="amount", value="5000"), CaseValue(field="currency", value="EUR")], answer_fields=["category"])])
        return Exercises(items=[Exercise(question="How would you decide whether to continue?", knowledge_ids=[data["knowledge"][0]["id"]])])
    if schema is TutorJudgment:
        return TutorResult(verdict="ok", explanation="Your answer follows the confirmed review step.", knowledge_ids=[data["verified_knowledge"][0]["id"]])
    raise AssertionError(schema)


Gateway.request = request
app = create_web_app("sqlite:///" + str(Path(os.getenv("HOSTED_TEST_DB", ".artifacts/browser-test.sqlite3")).resolve()),
                     "browser-test-only-secret-32-characters", Settings(openai_key="fixture-only"), production=False)
