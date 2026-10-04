"""Reviewer decisions, opt-in timing, privacy, and selected-workflow deletion."""
import time

from fastapi.testclient import TestClient
from apprentice import evaluation as ev
from apprentice.agents.assessor import Assessor
from apprentice.config import Settings
from apprentice.domain import Evidence, Observation, Session
from tests.test_hosted import HEADERS, command, make_app, state


def idle(client):
    for _ in range(200):
        snapshot = state(client)
        if not snapshot["busy"]:
            return snapshot
        time.sleep(.01)
    raise AssertionError("The fixture job did not finish")


def observed_session(client, *, confidence=.95, event="field_changed"):
    command(client, "new", {"title": "Reviewed action"})
    snapshot = state(client)
    service = client.app.state.runtime.guests[snapshot["guest"]].service
    s = service.session
    source = Evidence(kind="screen", timestamp=10, image="approved.jpg")
    s.duration = 20
    s.evidence.append(source)
    s.observations.append(Observation(summary="Cost center changed", evidence_ids=[source.id],
        event_type=event, field_name="cost center", before="4711", after="0400",
        before_readable=True, after_readable=True, confidence=confidence))
    s.privacy.status = "approved"
    s.privacy.analyzed_frames.append(source.id)
    return service, source


def test_ai_is_available_after_create_open_recover_without_switch(tmp_path):
    with TestClient(make_app(tmp_path), headers=HEADERS) as c:
        state(c)
        command(c, "new", {"title": "AI built in"})
        sid = state(c)["session"]["id"]
        for name, data in [("cloud", {"enabled": False}), ("recover", {}), ("open", {"id": sid})]:
            assert command(c, name, data).status_code == 200
            assert state(c)["cloud"]


def test_deleting_other_workflow_preserves_active_capture_and_enforces_ownership(tmp_path):
    with TestClient(make_app(tmp_path), headers=HEADERS) as c:
        state(c)
        command(c, "new", {"title": "Delete target"})
        target = state(c)["session"]["id"]
        command(c, "new", {"title": "Keep active"})
        active = state(c)["session"]["id"]
        command(c, "recording", {"state": "recording"})
        assert command(c, "delete-session", {"id": active, "confirmed": True}).status_code == 400
        for confirmation in (False, "true", 1, None):
            assert command(c, "delete-session", {"id": target, "confirmed": confirmation}).status_code == 400
        assert command(c, "delete-session", {"id": "f" * 32, "confirmed": True}).status_code == 404
        assert command(c, "delete-session", {"id": target, "confirmed": True}).status_code == 200
        snapshot = state(c)
        assert snapshot["session"]["id"] == active and snapshot["recording"] == "recording"
        assert [s["id"] for s in snapshot["sessions"]] == [active]
        c.cookies.clear()
        state(c)
        assert command(c, "delete-session", {"id": active, "confirmed": True}).status_code == 404


def test_review_completion_asks_once_and_never_for_stale_revision(tmp_path):
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="fixture")), headers=HEADERS) as c:
        state(c)
        service, source = observed_session(c)
        assert command(c, "review-complete", {"revision": 99}).status_code == 400
        assert command(c, "review-complete", {"revision": 0}).status_code == 200
        first = state(c)["question"]
        assert "4711 to 0400" in first["text"] and first["evidence_ids"] == [source.id]
        assert first["priority_score"] >= 60 and first["process_score"] == 0
        command(c, "defer", {"expectedQuestionId": first["id"]})
        command(c, "review-complete", {"revision": 0})
        assert state(c)["question"] is None
        assert len(service.session.evaluation.attempts) == 1


def test_routine_or_uncertain_screen_evidence_does_not_produce_auto_question(tmp_path):
    with TestClient(make_app(tmp_path), headers=HEADERS) as c:
        state(c)
        for event, confidence in [("navigation", .99), ("field_changed", .3)]:
            observed_session(c, confidence=confidence, event=event)
            assert command(c, "review-complete", {"revision": 0}).status_code == 200
            snapshot = state(c)
            assert snapshot["question"] is None
            assert "No supported screen question" in snapshot["session"]["messages"][-1]["text"]


def test_live_note_questions_respect_preferences_availability_and_cooldown(tmp_path, monkeypatch):
    def assess(self, session):
        ev.refresh(session)
        for source in ev.pending_sources(session):
            session.evaluation.assessed_evidence_ids.append(source.id)
            ev.ensure_gap(session, "text:" + source.id, "reason", [source.id])
        return session.evaluation
    monkeypatch.setattr(Assessor, "run", assess)
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="fixture")), headers=HEADERS) as c:
        state(c)
        command(c, "new", {"title": "Live notes"})
        command(c, "recording", {"state": "recording", "duration": 0})
        command(c, "note", {"text": "I changed the cost center to 0400."})
        command(c, "reviewer-tick", {"duration": 5, "available": True})
        assert not state(c)["busy"] and not state(c)["question"]
        command(c, "reviewer", {"enabled": True, "presentation": "both"})
        command(c, "reviewer-tick", {"duration": 5, "available": False})
        assert not state(c)["question"] and not state(c)["busy"]
        command(c, "reviewer-tick", {"duration": 5, "available": True})
        idle(c)
        command(c, "reviewer-tick", {"duration": 7, "available": True})
        question = state(c)["question"]
        assert question["phase"] == "live" and "What made you choose" in question["text"]
        assert state(c)["session"]["privacy"]["status"] == "unreviewed"
        assert c.post(f'/api/frame?sessionId={state(c)["session"]["id"]}&id={"a"*32}', content=b"raw").status_code == 400
        command(c, "defer", {"expectedQuestionId": question["id"]})
        command(c, "reviewer-tick", {"duration": 20, "available": True})
        assert not state(c)["question"]
        command(c, "reviewer", {"enabled": False, "presentation": "both"})
        command(c, "reviewer-tick", {"duration": 60, "available": True})
        assert not state(c)["question"]


def test_failed_note_assessment_requires_retry_instead_of_repeated_provider_calls(tmp_path, monkeypatch):
    calls = []
    def fail(*args):
        calls.append(1)
        raise ValueError("Fixture provider failure")
    monkeypatch.setattr(Assessor, "run", fail)
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="fixture")), headers=HEADERS) as c:
        state(c)
        command(c, "new", {"title": "Failure"})
        command(c, "recording", {"state": "recording"})
        command(c, "reviewer", {"enabled": True, "presentation": "text"})
        command(c, "note", {"text": "An unexplained decision"})
        for _ in range(3):
            command(c, "reviewer-tick", {"duration": 10, "available": True})
            idle(c)
        assert calls == [1] and state(c)["question"] is None
        command(c, "reviewer-tick", {"duration": 10, "available": True, "retry": True})
        idle(c)
        assert calls == [1, 1]


def test_stale_critical_gap_does_not_hide_recent_live_question():
    old = Evidence(kind="note", text="Old decision", timestamp=0)
    recent = Evidence(kind="note", text="New decision", timestamp=190)
    session = Session(title="Recent notes", evidence=[old, recent], duration=200)
    ev.refresh(session)
    ev.ensure_gap(session, "text:" + old.id, "guardrail", [old.id])
    ev.ensure_gap(session, "text:" + recent.id, "reason", [recent.id])
    assert ev.next_gap(session, "live").evidence_ids == [recent.id]


def test_failed_delete_retains_active_workflow_and_question_for_retry(tmp_path, monkeypatch):
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="fixture")), headers=HEADERS) as c:
        state(c)
        service, _ = observed_session(c)
        command(c, "review-complete", {"revision": 0})
        before = state(c)
        original = service.repo.delete
        async def fail(target):
            raise ValueError("Storage unavailable; retry deletion.")
        monkeypatch.setattr(service.repo, "delete", fail)
        payload = {"id": before["session"]["id"], "confirmed": True}
        assert command(c, "delete-session", payload).status_code == 400
        after = state(c)
        assert after["session"]["id"] == before["session"]["id"]
        assert after["question"] == before["question"]
        monkeypatch.setattr(service.repo, "delete", original)
        assert command(c, "delete-session", payload).status_code == 200
        assert state(c)["session"] is None
