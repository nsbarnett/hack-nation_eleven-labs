"""Provider contracts and session lifecycle, without external services."""

import json
from types import SimpleNamespace

import httpx
import pytest

from apprentice.agents.observer import Observer
from apprentice.config import Settings
from apprentice.domain import ObservationResult, SeenAction, Evidence
from apprentice.voice import ElevenVoice
from tests.test_domain import case


def test_observer_rejects_hallucinated_evidence():
    from apprentice.demo import create_demo
    response = ObservationResult(actions=[SeenAction(summary="Changed field", evidence_ids=["unknown"], question="Why?", novelty=1, ambiguity=1, significance=2, guardrail=False)])
    fake = SimpleNamespace(request=lambda *args: response)
    with pytest.raises(ValueError):
        Observer(fake).run(create_demo(), [])


def test_elevenlabs_request_shapes():
    calls = []
    def transport(request):
        calls.append(request)
        assert request.headers["xi-api-key"] == "test-key"
        if request.url.path.endswith("speech-to-text"):
            assert b"name=\"file\"" in request.content
            assert b"scribe_v1" in request.content
            return httpx.Response(200, json={"text": "Hold without an asset number."})
        assert json.loads(request.content)["text"] == "Why did you hold this?"
        return httpx.Response(200, content=b"fake-mp3")
    service = ElevenVoice(Settings(eleven_key="test-key"), httpx.MockTransport(transport))
    assert service.speak("Why did you hold this?") == b"fake-mp3"
    assert service.transcribe(b"RIFF-test") == "Hold without an asset number."
    assert len(calls) == 2


def test_missing_voice_key_is_explicit():
    with pytest.raises(ValueError):
        ElevenVoice(Settings()).speak("Hello")


def test_demo_confirm_teach_save_and_restore(controller):
    c = controller
    c.loadDemo()
    assert not c.session.confirmed
    assert json.loads(c.checkCase(json.dumps(case())))["verdict"] == "unknown"
    c.confirmMap()
    assert c.session.confirmed
    assert json.loads(c.checkCase(json.dumps(case(category="OPEX"))))["verdict"] == "warn"
    assert not c.savePractice(json.dumps(case(category="OPEX")))
    assert c.savePractice(json.dumps(case()))
    assert c.session.evidence[-1].kind == "trainee_attempt"
    sid = c.session.id
    c.openSession(sid)
    assert c.session.confirmed and not c.cloud_enabled


def test_edit_clears_confirmation_and_rejects_invalid_check(controller):
    c = controller
    c.loadDemo()
    c.confirmMap()
    item = c.session.knowledge[0]
    c.editKnowledge(item.id, json.dumps({"reason": "Expert correction"}))
    assert not c.session.confirmed
    assert c.session.knowledge[0].status == "inferred"
    original = c.session.knowledge[0].model_dump()
    c.editKnowledge(item.id, json.dumps({"check": {"conditions": [], "field": "amount", "operator": "eval", "value": "1"}}))
    assert c.session.knowledge[0].model_dump() == original


def test_clarification_prevents_confirmation(controller):
    controller.loadDemo()
    controller.session.knowledge[0].status = "needs_clarification"
    controller.confirmMap()
    assert not controller.session.confirmed


def test_exclusion_removes_local_images_videos_and_map(controller):
    c = controller
    c.loadDemo()
    e = c.session.evidence[0]
    e.image = "source.jpg"
    image = c.store.media(c.session.id, e.image)
    image.write_bytes(b"fixture")
    video = c.store.media(c.session.id, "recording.mp4")
    video.write_bytes(b"fixture")
    c.session.recordings = ["recording.mp4"]
    c.forgetEvidence(e.id)
    assert not image.exists() and not video.exists()
    assert not c.session.knowledge and not c.session.recordings


def test_paused_and_off_record_do_not_save_notes(controller):
    c = controller
    c.newSession("Example", "Context", 0, False)
    c.off_record = True
    c.addNote("Do not retain this")
    c.addReference("Private", "Do not retain this")
    assert not c.session.evidence


def test_old_job_cannot_update_new_session(controller, monkeypatch):
    c = controller
    c.loadDemo()
    pending = []
    monkeypatch.setattr(c.jobs, "submit", lambda name, fn, callback: pending.append(callback) or True)
    applied = []
    c._submit("map", lambda: None, lambda result: applied.append(result))
    c.newSession("Another session", "", 0, False)
    pending[0]("stale result", "")
    assert applied == []


def test_old_job_cannot_restore_forgotten_evidence(controller, monkeypatch):
    c = controller
    c.loadDemo()
    pending, applied = [], []
    monkeypatch.setattr(c.jobs, "submit", lambda name, fn, callback: pending.append(callback) or True)
    c._submit("map", lambda: None, applied.append)
    c.forgetEvidence(c.session.evidence[0].id)
    pending[0]("private result", "")
    assert not applied


def test_answer_binds_to_exact_question_sources(controller):
    c = controller
    c.loadDemo()
    source = c.session.evidence[0].id
    c._ask("What made you choose this?", [source])
    c.addNote("It met the threshold.")
    answer = c.session.evidence[-1]
    assert answer.kind == "answer" and answer.related_ids == [source]
    assert answer.question == "What made you choose this?"


def test_provider_errors_are_sanitized(controller, monkeypatch):
    c = controller
    c.loadDemo()
    callbacks = []
    monkeypatch.setattr(c.jobs, "submit", lambda name, fn, callback: callbacks.append(callback) or True)
    c._submit("map", lambda: None, lambda _result: None)
    callbacks[0](None, "AuthenticationError")
    assert "AuthenticationError" in c.notice and "retry" in c.notice


@pytest.mark.parametrize("amount", ["-1", "0", "NaN", "Infinity"])
def test_invalid_amount_cannot_be_saved(controller, amount):
    controller.loadDemo()
    controller.confirmMap()
    payload = json.dumps(case(amount=amount))
    assert json.loads(controller.checkCase(payload))["verdict"] == "unknown"
    assert not controller.savePractice(payload)


def test_capture_pause_privacy_resume_and_stop(controller, monkeypatch):
    from PySide6.QtGui import QImage
    c = controller
    segments, stops = [], []
    monkeypatch.setattr(c.capture, "start", lambda monitor, path, started: segments.append(path))
    monkeypatch.setattr(c.capture, "stop", lambda: stops.append(True))
    c.newSession("Capture lifecycle", "", 0, False)
    c.startRecording()
    frame = QImage(100, 80, QImage.Format.Format_RGB32)
    frame.fill("green")
    c._sample(frame, 1)
    assert len(c.session.evidence) == 1
    c.togglePause()
    c._sample(frame, 2)
    c.addNote("Paused note must not be saved")
    assert c.paused and len(c.session.evidence) == 1
    c.offRecord()
    c._sample(frame, 3)
    assert len(c.session.evidence) == 1
    c.togglePause()
    c._sample(frame, 4)
    assert not c.off_record and len(segments) == 2
    c.stopRecording()
    assert not c.recording and c.session.phase == "debrief"
    assert len(c.store.load(c.session.id).evidence) == 2
    assert len(stops) == 2


def test_session_switch_and_deletion_clear_preview(controller):
    from PySide6.QtGui import QImage, QColor
    c = controller
    c.newSession("First", "", 0, False)
    first_id = c.session.id
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill("red")
    e = Evidence(kind="screen", image="screen.jpg")
    assert image.save(str(c.store.media(first_id, e.image)))
    c.session.evidence.append(e)
    c._save()
    c.openSession(first_id)
    assert c.preview.image.pixelColor(0, 0).red() > 240
    c.newSession("Second", "", 0, False)
    assert c.preview.image.pixelColor(0, 0) == QColor("#f3f4f6")
    c.openSession(first_id)
    c.forgetEvidence(e.id)
    assert c.preview.image.pixelColor(0, 0) == QColor("#f3f4f6")


def test_storage_failure_stops_observation_and_reports_unsaved_state(controller, monkeypatch):
    import sqlite3
    c = controller
    c.loadDemo()
    c.confirmMap()
    def unavailable(_session):
        raise sqlite3.OperationalError("disk full")
    # Restore save before fixture teardown; shutdown retries persistence.
    with monkeypatch.context() as patch:
        patch.setattr(c.store, "save", unavailable)
        assert not c.savePractice(json.dumps(case()))
        assert c.off_record and not c.recording
        assert "remains in memory" in c.notice


def test_off_record_blocks_practice_evidence(controller):
    controller.loadDemo()
    controller.confirmMap()
    count = len(controller.session.evidence)
    controller.offRecord()
    assert not controller.savePractice(json.dumps(case()))
    assert json.loads(controller.checkCase(json.dumps(case())))["verdict"] == "unknown"
    assert len(controller.session.evidence) == count


def test_trainee_notes_do_not_change_expert_confirmation(controller):
    from apprentice.context import context_for
    c = controller
    c.loadDemo()
    c.confirmMap()
    c.teaching = True
    c.addNote("A trainee guess, not an expert policy")
    assert c.session.confirmed
    assert c.session.evidence[-1].kind == "trainee_note"
    assert "A trainee guess" not in json.dumps(context_for(c.session))


def test_builder_rejects_trainee_or_omitted_sources():
    from apprentice.agents.knowledge import KnowledgeBuilder
    from apprentice.demo import create_demo
    from apprentice.domain import DraftKnowledge, MapResult
    s = create_demo()
    trainee = Evidence(kind="trainee_note", text="My incorrect assumption")
    s.evidence.append(trainee)
    draft = DraftKnowledge(**s.knowledge[0].model_dump(exclude={"id", "status", "check_verified"}), needs_clarification=False)
    draft.evidence_ids = [trainee.id]
    response = MapResult(items=[draft], teach_back="Test response", gaps=[])
    fake = SimpleNamespace(request=lambda *args: response)
    with pytest.raises(ValueError):
        KnowledgeBuilder(fake).run(s)
    # A retained source outside the supplied context is also insufficient.
    draft.evidence_ids = [s.evidence[0].id]
    s.evidence.extend(Evidence(kind="note", text="Later expert context") for _ in range(85))
    with pytest.raises(ValueError):
        KnowledgeBuilder(fake).run(s)


def test_confirmation_rejects_trainee_only_provenance(controller):
    c = controller
    c.loadDemo()
    source = Evidence(kind="trainee_note", text="An unconfirmed guess")
    c.session.evidence.append(source)
    c.session.knowledge[0].evidence_ids = [source.id]
    c.confirmMap()
    assert not c.session.confirmed
