"""Deterministic provider fixtures ONLY for browser automation; never used by backend.web."""
from pathlib import Path
import os

from apprentice.agents.gateway import Gateway
from apprentice.config import Settings
from apprentice.domain import DraftKnowledge, MapResult, ObservationResult, QuestionResult, TutorResult
from backend.training import Exercises, Exercise
from backend.web import create_web_app


def request(self, schema, instructions, data, images=None):
    if schema is ObservationResult:
        return ObservationResult(actions=[])
    if schema is QuestionResult:
        return QuestionResult(question="What makes this check necessary?", evidence_ids=[data["evidence"][0]["id"]])
    if schema is MapResult:
        source = next(e for e in data["evidence"] if e["kind"] == "note")
        return MapResult(items=[DraftKnowledge(title="Review the work", action="Review the current task",
            decision="Continue after review", reason=source["text"], rule="Review before proceeding",
            exception="Not established", guardrail="Ask when uncertain", escalation="Ask the expert",
            evidence_ids=[source["id"]], check=None, needs_clarification=False)], teach_back="Review before proceeding.", gaps=[])
    if schema is Exercises:
        return Exercises(items=[Exercise(question="How would you decide whether to continue?", knowledge_ids=[data["knowledge"][0]["id"]])])
    if schema is TutorResult:
        return TutorResult(verdict="ok", explanation="Your answer follows the confirmed review step.", knowledge_ids=[data["verified_knowledge"][0]["id"]])
    raise AssertionError(schema)


Gateway.request = request
app = create_web_app("sqlite:///" + str(Path(os.getenv("HOSTED_TEST_DB", ".artifacts/browser-test.sqlite3")).resolve()),
                     "browser-test-only-secret-32-characters", Settings(openai_key="fixture-only"), production=False)
