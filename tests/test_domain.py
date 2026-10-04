"""Knowledge must remain traceable, reviewable, and safe to evaluate."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from apprentice.context import context_for
from apprentice.demo import create_demo
from apprentice.domain import Condition, Evidence, Observation, Session
from apprentice.evidence import forget, require_sources
from apprentice.exporting import export_session
from apprentice.rules import evaluate
from apprentice.scoring import QuestionPolicy, completeness
from apprentice.store import SessionStore


def verified_demo():
    session = create_demo()
    for item in session.knowledge:
        item.status = "verified"
    session.confirmed = True
    return session


def case(**changes):
    return dict(amount="7200", category="CAPEX", asset_number="A-21", supplier_status="known", purchase_type="equipment", currency="EUR", **{}) | changes


@pytest.mark.parametrize("changes,verdict", [
    ({"category": "OPEX"}, "warn"),
    ({"asset_number": ""}, "warn"),
    ({"supplier_status": "unknown"}, "warn"),
    ({"amount": "5000", "category": "OPEX", "asset_number": ""}, "ok"),
    ({"amount": "5000", "category": "CAPEX"}, "warn"),
    ({"amount": "5001"}, "ok"),
    ({"currency": "USD"}, "unknown"),
    ({"purchase_type": "service"}, "unknown"),
    ({"amount": "not a number"}, "unknown"),
    ({"amount": "NaN"}, "unknown"),
])
def test_boundary_and_guardrail_checks(changes, verdict):
    result = evaluate(verified_demo().knowledge, case(**changes), {"category"})
    assert result.verdict == verdict


def test_unverified_rules_cannot_authorize_case():
    assert evaluate(create_demo().knowledge, case(), {"category"}).verdict == "unknown"


def test_conditions_are_not_executable_code():
    with pytest.raises(ValidationError):
        Condition(field="amount", operator="eval", value="__import__('os')")


def test_references_reject_unknown_sources():
    with pytest.raises(ValueError):
        require_sources(["made-up"], {"real"})
    with pytest.raises(ValueError):
        require_sources([], {"real"})
    assert require_sources(["real", "real"], {"real"}) == ["real"]


def test_exclusion_cascades_and_invalidates_derived_map():
    s = verified_demo()
    source = s.evidence[0]
    answer = Evidence(kind="answer", text="private answer", related_ids=[source.id])
    followup = Evidence(kind="answer", text="dependent", related_ids=[answer.id])
    s.evidence.extend([answer, followup])
    removed = forget(s, source.id)
    assert {source.id, answer.id, followup.id} == removed
    assert not s.confirmed and not s.knowledge and not s.observations
    assert not any(e.id in removed for e in s.evidence)


def test_questions_respect_activity_cooldown_and_budget():
    p = QuestionPolicy()
    assert not p.eligible(100, 2, 9, True, False)
    assert not p.eligible(100, 20, 1, True, False)
    assert not p.eligible(100, 20, 9, True, True)
    assert not p.eligible(100, 20, 9, False, False)
    assert p.eligible(100, 20, 9, True, False)
    p.delivered = [100]
    assert not p.eligible(150, 20, 9, True, False)
    p.delivered = [100, 200, 300]
    assert not p.eligible(500, 20, 9, True, False)
    assert p.eligible(901, 20, 9, True, False)


def test_question_selection_prefers_significant_guardrail():
    a = Observation(summary="Change", evidence_ids=["a"], question="Why?", significance=3)
    b = Observation(summary="Missing prerequisite", evidence_ids=["b"], question="When do you stop?", significance=3, guardrail=True)
    assert QuestionPolicy().choose([a, b]) is b
    b.asked = True
    assert QuestionPolicy().choose([a, b]) is a


def test_store_roundtrip_and_path_traversal(tmp_path):
    store = SessionStore(tmp_path)
    s = create_demo()
    store.save(s)
    assert store.load(s.id) == s
    assert store.list()[0]["id"] == s.id
    for path in ("../outside.txt", "", str(tmp_path / "outside.txt")):
        with pytest.raises(ValueError):
            store.media(s.id, path)
    store.close()


def test_future_schema_fails_instead_of_silent_migration():
    payload = create_demo().model_dump()
    payload["schema_version"] = 999
    with pytest.raises(ValidationError):
        Session.model_validate(payload)


def test_context_excludes_trainee_material_and_is_bounded():
    s = create_demo()
    for i in range(200):
        s.evidence.append(Evidence(kind="note", text=f"note {i}"))
    s.evidence.append(Evidence(kind="trainee_note", text="Incorrect trainee rule"))
    result = context_for(s)
    assert len(result["evidence"]) == 80
    assert all(e["kind"] != "trainee_note" for e in result["evidence"])


def test_export_escapes_content_and_preserves_provenance(tmp_path):
    store = SessionStore(tmp_path / "data")
    s = verified_demo()
    s.knowledge[0].reason = "<script>alert('test')</script>"
    folder = export_session(s, store, tmp_path / "exports")
    html = (folder / "work-map.html").read_text(encoding="utf-8")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert s.evidence[1].id[:8] in html
    assert json.loads((folder / "work-map.json").read_text())["confirmed"]
    assert (folder / "work-map.md").is_file()
    store.close()


def test_field_coverage_does_not_confirm_rules():
    s = create_demo()
    assert completeness(s.knowledge) > 50
    assert not s.confirmed and all(k.status == "inferred" for k in s.knowledge)
