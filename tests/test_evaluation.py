"""Adversarial gap closure, persistence and learner evaluation regressions."""
import asyncio
from types import SimpleNamespace

import pytest

from apprentice import evaluation as ev
from apprentice.domain import (
    AssessmentResult, Evidence, EvidenceQuote, FieldAssessment, GapProposal, GapReview,
    Knowledge, Observation, Session,
)
from apprentice.demo import create_demo
from apprentice.config import Settings
from apprentice.agents.assessor import Assessor
from apprentice.agents.observer import Observer
from apprentice.evidence import forget
from backend.service import Service
from backend.training import Exercise, Exercises, CaseValue, evaluate_exercise, generate


def observed(*, duration=300, confidence=.9, readable=True):
    source = Evidence(kind="screen", timestamp=10)
    action = Observation(summary="Classification changed", evidence_ids=[source.id], event_type="field_changed",
                         case_id="invoice-1", field_name="classification", before="A", after="B",
                         before_readable=readable, after_readable=readable, confidence=confidence)
    session = Session(title="Test", evidence=[source], observations=[action], duration=duration)
    ev.refresh(session)
    return session, session.evaluation.gaps[0]


def answer(session, gap, text):
    source = Evidence(kind="answer", text=text, gap_id=gap.id, related_ids=gap.evidence_ids)
    session.evidence.append(source)
    return source


def assessment(session, gap, source, *, outcome="sufficient", confidence=.95, claim=None):
    value = FieldAssessment(decision_id=gap.decision_id, field=gap.field, outcome=outcome,
        claim=claim or source.text, citations=[EvidenceQuote(evidence_id=source.id, quote=source.text)],
        confidence=confidence, rationale="Fixture assessment.")
    ev.apply_assessment(session, AssessmentResult(assessments=[value], gaps=[]), [source.id])


@pytest.mark.parametrize("text,confidence,expected", [
    ("I don't know", .99, "open"), ("I'm not sure", .99, "open"),
    ("Fine.", .99, "open"), ("Yes", .99, "open"),
    ("The rule depends on the purchase type.", .79, "partial"),
    ("The rule depends on the purchase type.", .80, "expert_stated"),
])
def test_answer_received_is_not_automatically_gap_closed(text, confidence, expected):
    session, gap = observed()
    source = answer(session, gap, text)
    assessment(session, gap, source, confidence=confidence)
    assert gap.status == expected
    assert gap.status != "verified"


def test_qualified_threshold_stays_partial_and_exact_boundary_remains_open():
    session, original = observed()
    gap = ev.ensure_gap(session, original.decision_id, "threshold", original.evidence_ids)
    source = answer(session, gap, "Usually above 5,000 EUR.")
    assessment(session, gap, source)
    ev.apply_assessment(session, AssessmentResult(assessments=[], gaps=[
        GapProposal(decision_id=gap.decision_id, field="operator", description="Exactly 5,000 EUR is unresolved.", evidence_ids=[source.id])
    ]), [])
    assert gap.status == "partial"
    assert next(g for g in session.evaluation.gaps if g.field == "operator").status == "open"
    assert not ev.summary(session)["debrief_complete"]


def test_proposal_validation_is_atomic_and_rejects_invented_quotes():
    session, gap = observed()
    source = answer(session, gap, "Because of the equipment type.")
    valid = FieldAssessment(decision_id=gap.decision_id, field="reason", outcome="sufficient", claim="Equipment",
        citations=[EvidenceQuote(evidence_id=source.id, quote=source.text)], confidence=.9, rationale="Evidence")
    invalid = valid.model_copy(deep=True)
    invalid.citations[0].quote = "An invented policy"
    with pytest.raises(ValueError, match="quote"):
        ev.apply_assessment(session, AssessmentResult(assessments=[valid, invalid], gaps=[]), [source.id])
    assert not session.evaluation.assessments
    assert source.id not in session.evaluation.assessed_evidence_ids


def test_omitted_evidence_stays_pending_instead_of_silently_reviewed():
    session, gap = observed()
    source = answer(session, gap, "I have a different explanation.")
    with pytest.raises(ValueError, match="omitted"):
        ev.apply_assessment(session, AssessmentResult(assessments=[], gaps=[]), [source.id])
    assert source.id in {e.id for e in ev.pending_sources(session)}


def test_answer_cannot_be_assigned_to_another_decision():
    session, gap = observed()
    other = Evidence(kind="note", text="A different task")
    session.evidence.append(other)
    ev.refresh(session)
    other_gap = next(g for g in session.evaluation.gaps if g.decision_id == f"text:{other.id}")
    source = answer(session, gap, "Equipment classification is required.")
    with pytest.raises(ValueError, match="different decision"):
        assessment(session, other_gap, source)


def test_trainee_text_cannot_close_expert_gap():
    session, gap = observed()
    source = Evidence(kind="trainee_note", text="Trust my rule")
    session.evidence.append(source)
    with pytest.raises(ValueError, match="expert evidence"):
        assessment(session, gap, source)


def test_conflicting_sufficient_claims_require_explicit_review():
    session, gap = observed()
    first = answer(session, gap, "The reason is equipment type.")
    assessment(session, gap, first)
    second = answer(session, gap, "The reason is supplier identity.")
    assessment(session, gap, second)
    assert gap.status == "disputed"
    resolution = answer(session, gap, "Equipment type controls this case; the supplier explanation was incorrect.")
    session.evaluation.reviews.append(GapReview(gap_id=gap.id, evidence_id=resolution.id, outcome="verified"))
    ev.refresh(session)
    assert gap.status == "verified"
    # A later conflicting statement invalidates that resolution's authority.
    later = answer(session, gap, "The latest guidance contradicts that equipment rule.")
    assessment(session, gap, later, outcome="contradictory")
    assert gap.status == "disputed"


def test_rejecting_a_verified_map_reopens_its_gap():
    session, gap = observed()
    item = Knowledge(title="Rule", action="Act", decision="Choose", reason="Equipment", rule="Rule",
                     exception="Not established", guardrail="Hold", escalation="Owner", evidence_ids=gap.evidence_ids,
                     status="verified", decision_ids=[gap.decision_id])
    session.knowledge.append(item)
    ev.refresh(session)
    assert gap.status == "verified"
    item.status = "rejected"
    ev.refresh(session)
    assert gap.status == "open" and not gap.verified_by


def test_removing_an_answer_revokes_the_assessment_and_review():
    session, gap = observed()
    source = answer(session, gap, "Because the asset is equipment.")
    assessment(session, gap, source)
    session.evaluation.reviews.append(GapReview(gap_id=gap.id, evidence_id=source.id, outcome="verified"))
    ev.refresh(session)
    assert gap.status == "verified"
    session.evidence.remove(source)
    ev.refresh(session)
    assert gap.status == "open"
    assert not session.evaluation.assessments and not session.evaluation.reviews


def test_forget_clears_derived_trace_and_dependent_answers():
    session, gap = observed()
    source = answer(session, gap, "Private supporting text")
    assessment(session, gap, source)
    ev.ask_gap(session, gap)
    removed = forget(session, gap.evidence_ids[0])
    assert source.id in removed
    assert not session.evaluation.gaps and not session.evaluation.trace
    assert "Private supporting text" not in session.model_dump_json()


def test_historical_frames_are_not_stale_and_low_quality_stays_explicit():
    session, gap = observed(duration=300)
    assert ev.next_gap(session).id == gap.id
    assert "recorded values are unclear" not in ev.question_for(session, gap)
    uncertain, gap = observed(readable=False)
    assert uncertain.evaluation.decisions[0].observation_confidence == .35
    assert ev.next_gap(uncertain, "live") is None
    assert "recorded values are unclear" in ev.question_for(uncertain, gap)


def test_same_visible_case_and_field_share_a_decision():
    session, gap = observed()
    duplicate = session.observations[0].model_copy(update={"id": "next-observation"})
    session.observations.append(duplicate)
    ev.refresh(session)
    assert len(session.evaluation.decisions) == 1
    assert len(session.evaluation.gaps) == 1


def test_notes_only_persistence_and_no_minimum_question_quota():
    source = Evidence(kind="note", text="Hold when approval is missing.")
    session = Session(title="Notes only", evidence=[source])
    ev.refresh(session)
    gap = session.evaluation.gaps[0]
    assessment(session, gap, source)
    assert ev.summary(session)["debrief_complete"]  # zero questions, sufficient scoped evidence
    restored = Session.model_validate_json(session.model_dump_json())
    assert ev.summary(restored)["debrief_complete"]
    assert restored.evaluation.gaps[0].status == "expert_stated"
    assert not restored.confirmed
    old = Session.model_validate({"title": "Old saved workflow"})
    assert not old.evaluation.gaps


def test_observer_uses_event_contract_without_guessing_defaults():
    from apprentice.domain import EventResult, SeenEvent
    session, _ = observed()
    returned = EventResult(actions=[SeenEvent(summary="Changed", evidence_ids=[session.evidence[0].id],
        event_type="field_changed", case_id="invoice-1", field_name="category", before="A", after="B",
        before_readable=True, after_readable=True, before_was_default=False, confidence=.9, fields_answered_on_screen=[])])
    schemas = []
    def request(schema, *args):
        schemas.append(schema)
        return returned
    result = Observer(SimpleNamespace(request=request)).run(session, [])
    assert schemas == [EventResult]
    assert result[0].before_was_default is False and result[0].question == ""


def test_deferred_and_active_questions_survive_roundtrip(tmp_path):
    async def scenario():
        service = Service(tmp_path, Settings())
        service.session, gap = observed()
        service.ask_evaluated(gap)
        qid = service.question["id"]
        await service.persist()
        restored = Service(tmp_path, Settings())
        await restored.command("open", {"id": service.session.id})
        assert restored.question["id"] == qid
        await restored.command("defer", {})
        assert restored.session.evaluation.attempts[0].state == "deferred"
        assert ev.next_gap(restored.session, "live") is None
        assert ev.next_gap(restored.session, "debrief").id == gap.id
        await service.close()
        await restored.close()
    asyncio.run(scenario())


def test_editing_rule_invalidates_executable_check(tmp_path):
    async def scenario():
        service = Service(tmp_path, Settings())
        session = create_demo()
        session.mode = "live"
        item = session.knowledge[0]
        item.status, item.check_verified = "verified", True
        service.session = session
        await service.command("edit-knowledge", {"id": item.id, "patch": {"rule": "Different rule"}})
        edited = service.session.knowledge[0]
        assert edited.check is None and not edited.check_verified
        assert edited.status == "needs_clarification"
        assert not service.session.confirmed
        await service.close()
    asyncio.run(scenario())


def practice_fixture():
    session = create_demo()
    session.confirmed = True
    for item in session.knowledge:
        item.status, item.check_verified = "verified", True
    exercise = {"question": "Classify this EUR equipment purchase.", "knowledge_ids": [k.id for k in session.knowledge[:2]],
                "scenario": [{"field": "amount", "value": "5000"}, {"field": "currency", "value": "EUR"},
                             {"field": "purchase_type", "value": "equipment"}], "answer_fields": ["category"]}
    return session, exercise


@pytest.mark.parametrize("amount,category,verdict", [("4999", "OPEX", "ok"), ("5000", "OPEX", "ok"),
    ("5000", "CAPEX", "warn"), ("5001", "CAPEX", "ok"), ("NaN", "CAPEX", "unknown")])
def test_structured_evaluation_exact_thresholds(amount, category, verdict):
    session, item = practice_fixture()
    item["scenario"][0]["value"] = amount
    result = evaluate_exercise(session, item, {"category": category})
    assert result.verdict == verdict and result.evaluation_method == "verified_rules"


def test_missing_or_out_of_scope_input_never_passes():
    session, item = practice_fixture()
    assert evaluate_exercise(session, item, {}).verdict == "unknown"
    item["scenario"][1]["value"] = "USD"
    assert evaluate_exercise(session, item, {"category": "CAPEX"}).verdict == "unknown"
    with pytest.raises(ValueError, match="only the fields"):
        evaluate_exercise(session, item, {"category": "CAPEX", "amount": "9999"})


def test_conflicting_applicable_rules_never_pass():
    session, item = practice_fixture()
    conflict = session.knowledge[1].model_copy(deep=True)
    conflict.id = "conflict"
    conflict.check.value = "CAPEX"
    session.knowledge.append(conflict)
    result = evaluate_exercise(session, item, {"category": "OPEX"})
    assert result.verdict == "unknown" and "disagree" in result.explanation


def test_unreviewed_check_cannot_grade_structured_practice():
    session, item = practice_fixture()
    session.knowledge[0].check_verified = False
    with pytest.raises(ValueError, match="checks changed"):
        evaluate_exercise(session, item, {"category": "OPEX"})


def test_advisory_model_cannot_claim_deterministic_authority():
    from apprentice.agents.tutor import Tutor
    from apprentice.domain import TutorResult
    session, item = practice_fixture()
    fake = SimpleNamespace(request=lambda *args: TutorResult(verdict="ok", explanation="Model assertion",
        knowledge_ids=item["knowledge_ids"], evaluation_method="verified_rules"))
    assert Tutor(fake).explain(session, "Explain this").evaluation_method == "advisory"


def test_new_expert_evidence_invalidates_existing_checks(tmp_path):
    async def scenario():
        service = Service(tmp_path, Settings())
        service.session, _ = practice_fixture()
        await service.command("note", {"text": "The classification rule has changed."})
        assert not service.session.confirmed
        assert all(k.check is None and not k.check_verified and k.status == "needs_clarification" for k in service.session.knowledge)
        await service.close()
    asyncio.run(scenario())


def test_explicit_absence_is_distinct_from_an_unanswered_field():
    session, _ = practice_fixture()
    item = session.knowledge[2]
    exercise = {"knowledge_ids": [item.id], "scenario": [{"field": "category", "value": "CAPEX"}], "answer_fields": ["asset_number"]}
    assert evaluate_exercise(session, exercise, {}).verdict == "unknown"
    assert evaluate_exercise(session, exercise, {"asset_number": None}).verdict == "warn"
    item.check.operator = "absent"
    assert evaluate_exercise(session, exercise, {"asset_number": None}).verdict == "ok"


def test_training_rejects_scenario_that_supplies_the_answer():
    session, item = practice_fixture()
    item["scenario"].append({"field": "category", "value": "OPEX"})
    fake = SimpleNamespace(request=lambda *args: Exercises(items=[Exercise.model_validate(item)]))
    with pytest.raises(ValueError, match="rule fields"):
        generate(fake, session)


def test_pipeline_cancellation_prevents_second_provider_call(tmp_path, monkeypatch):
    async def scenario():
        calls = []
        async def runner(role, callback):
            calls.append(role)
            result = callback()
            service.invalidate()
            return result
        service = Service(tmp_path, Settings(openai_key="fixture"), work_runner=runner)
        monkeypatch.setattr(Assessor, "run", lambda self, session: session.evaluation)
        await service.command("new", {"title": "Cancel", "cloud": True})
        await service.command("note", {"text": "Expert evidence"})
        await service.command("build-map", {})
        await asyncio.gather(*service.tasks, return_exceptions=True)
        assert calls == ["assessment"]
        assert not service.session.knowledge
        await service.close()
    asyncio.run(scenario())


def test_hosted_assessment_stages_charge_separately_and_question_survives_recovery(tmp_path, monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from apprentice.agents.gateway import Gateway
    from apprentice.domain import QuestionResult
    from tests.test_hosted import HEADERS, command, make_app, state

    def provider(self, schema, instructions, data, images=None):
        if schema is AssessmentResult:
            source = data["expert_evidence"][0]
            return AssessmentResult(assessments=[FieldAssessment(decision_id=data["decisions"][0]["id"], field="rule",
                outcome="uncertain", claim="", confidence=.9, rationale="The rule remains unclear.",
                citations=[EvidenceQuote(evidence_id=source["id"], quote=source["text"])])], gaps=[])
        assert schema is QuestionResult
        return QuestionResult(question="Which rule applies here?", evidence_ids=data["target_gap"]["evidence_ids"])

    monkeypatch.setattr(Gateway, "request", provider)
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="fixture")), headers=HEADERS) as client:
        state(client)
        command(client, "new", {"title": "Quota and recovery", "cloud": True})
        command(client, "note", {"text": "A decision was made, but the rule is unclear."})
        assert command(client, "debrief").status_code == 200
        for _ in range(100):
            snapshot = state(client)
            if not snapshot["busy"]:
                break
            time.sleep(.01)
        assert snapshot["question"]
        qid = snapshot["question"]["id"]
        database = client.app.state.runtime.database
        used = client.portal.call(database.call, lambda: database.execute(
            "SELECT used FROM hosted_quotas WHERE scope=?", (snapshot["guest"],)).fetchone()[0])
        assert used == 2
        command(client, "recover")
        assert state(client)["question"]["id"] == qid
        assert state(client)["cloud"]
