"""Public-host boundary tests. All generated examples stay in this test file."""
import asyncio
import io
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apprentice.config import Settings
from apprentice.domain import Knowledge, Evidence
from backend.web import create_web_app, COOKIE
from backend.hosted_store import HostedDatabase, LimitError

HEADERS = {"Origin": "http://testserver", "X-Apprentice-Client": "web"}
SECRET = "test-hosted-cookie-signing-key-at-least-32"


def make_app(tmp_path, **kwargs):
    return create_web_app("sqlite:///" + str(tmp_path / "hosted.sqlite3"), SECRET,
                          kwargs.pop("settings", Settings()), production=False, **kwargs)


@pytest.fixture
def client(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        client.headers.update(HEADERS)
        client.get("/api/state")
        yield client


def state(client):
    response = client.get("/api/state")
    assert response.status_code == 200, response.text
    return response.json()


def command(client, name, data=None, sid=None):
    sid = sid or (state(client)["session"] or {}).get("id")
    return client.post("/api/command", json={"name": name, "data": data or {}, "sessionId": sid})


def test_empty_bootstrap_cookie_and_public_surface(client):
    snapshot = state(client)
    assert snapshot["session"] is None and snapshot["sessions"] == []
    assert snapshot["hosted"] and snapshot["limits"]["recordingSeconds"] == 300
    response = client.get("/api/state")
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    for forbidden in ("credentials", "segment", "arbitrary", "import", "export"):
        assert command(client, forbidden).status_code == 400
    assert client.get("/healthz").status_code == 200


def test_csrf_payload_and_cookie_boundaries(client):
    assert client.post("/api/command", json={"name": "new"}, headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post("/api/command", content=b"x" * 65537).status_code == 413
    client.cookies.set(COOKIE, "forged.value.signature", domain="testserver.local", path="/")
    assert client.post("/api/command", json={"name": "new"}).status_code == 401


def test_guests_cannot_read_or_mutate_other_sessions(client):
    assert command(client, "new", {"title": "Expert's private work"}).status_code == 200
    command(client, "note", {"text": "Confidential expert note"})
    first = state(client)
    first_cookie = client.cookies.get(COOKIE)
    client.cookies.clear()
    second = state(client)
    assert second["guest"] != first["guest"] and second["sessions"] == []
    assert command(client, "open", {"id": first["session"]["id"]}).status_code == 404
    assert command(client, "forget", {"id": first["session"]["evidence"][0]["id"]}, first["session"]["id"]).status_code == 400
    client.cookies.set(COOKIE, first_cookie, domain="testserver.local", path="/")
    assert state(client)["session"]["messages"][0]["text"] == "Confidential expert note"


def test_local_media_metadata_is_not_a_file_upload(client, tmp_path):
    command(client, "new", {"title": "Local media"})
    sid = state(client)["session"]["id"]
    command(client, "recording", {"state": "recording"})
    assert client.post(f"/api/frame?sessionId={sid}&id={'a'*32}", content=b"private-image").status_code == 400
    assert command(client, "local-frame", {"id": "../evil", "duration": 1}).status_code == 400
    assert command(client, "local-frame", {"id": "a" * 32, "duration": 1}).status_code == 200
    assert command(client, "local-segment", {"filename": "b" * 32 + ".webm"}).status_code == 200
    assert command(client, "local-segment", {"filename": "../outside.webm"}).status_code == 400
    saved = state(client)["session"]
    assert saved["evidence"][0]["image"] == "a" * 32 + ".jpg"
    assert list(tmp_path.iterdir()) == [tmp_path / "hosted.sqlite3"]
    assert b"private-image" not in (tmp_path / "hosted.sqlite3").read_bytes()


def test_reviewed_frames_require_approval_and_keep_only_bounded_memory(tmp_path, monkeypatch):
    from apprentice.agents.observer import Observer
    monkeypatch.setattr(Observer, "run", lambda *args: [])
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="test-only")), headers=HEADERS) as client:
        state(client)
        command(client, "new", {"title": "Opted in", "cloud": True})
        command(client, "recording", {"state": "recording"})
        snapshot = state(client)
        entry = client.app.state.runtime.guests[snapshot["guest"]]
        sid = snapshot["session"]["id"]
        revision = snapshot["session"]["privacy"]["revision"]
        buf = io.BytesIO()
        Image.new("RGB", (40, 30), "white").save(buf, "JPEG")
        endpoint = f"/api/reviewed-frame?sessionId={sid}&revision={revision}"
        assert client.post(endpoint + f"&id={'a'*32}", content=buf.getvalue()).status_code == 400
        assert client.post(f"/api/frame?sessionId={sid}&id={'a'*32}", content=buf.getvalue()).status_code == 400
        command(client, "local-segment", {"filename": "b"*32 + ".webm"})
        command(client, "recording", {"state": "idle", "duration": 10})
        assert command(client, "privacy-approve", {"revision": revision-1}).status_code == 400
        assert command(client, "privacy-approve", {"revision": revision}).status_code == 200
        for index in range(4):
            entry.last_frame = 0
            response = client.post(endpoint + f"&id={index:032x}&duration={index*2}", content=buf.getvalue())
            assert response.status_code == 200, response.text
            for _ in range(100):
                if not state(client)["busy"]: break
                time.sleep(.01)
        assert len(entry.service.repo.frames) == 3
        assert len(state(client)["session"]["privacy"]["analyzed_frames"]) == 4
        assert not list(tmp_path.glob("**/*.jpg"))
        assert command(client, "privacy-reset", {"revision": revision}).status_code == 200
        assert not state(client)["session"]["observations"]
        assert not entry.service.repo.frames
        entry.last_frame = 0
        assert client.post(endpoint + f"&id={'f'*32}", content=buf.getvalue()).status_code == 400


def test_privacy_edit_cancels_inflight_observation_and_rejects_stale_answer(tmp_path, monkeypatch):
    from apprentice.agents.observer import Observer
    from apprentice.domain import Observation
    started, release = threading.Event(), threading.Event()
    def slow(self, session, images):
        started.set(); release.wait(3)
        return [Observation(summary="Obsolete pixels", evidence_ids=[session.evidence[-1].id])]
    monkeypatch.setattr(Observer, "run", slow)
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="test-only")), headers=HEADERS) as client:
        state(client); command(client, "new", {"title": "Revision", "cloud": True})
        command(client, "local-segment", {"filename": "a"*32 + ".webm"})
        command(client, "recording", {"state": "idle", "duration": 5})
        revision = state(client)["session"]["privacy"]["revision"]
        command(client, "privacy-approve", {"revision": revision})
        sid = state(client)["session"]["id"]
        buf = io.BytesIO(); Image.new("RGB", (30,30), "black").save(buf, "JPEG")
        response = client.post(f"/api/reviewed-frame?sessionId={sid}&revision={revision}&id={'b'*32}", content=buf.getvalue())
        assert response.status_code == 200 and started.wait(2)
        command(client, "privacy-reset", {"revision": revision}); release.set()
        for _ in range(50):
            if not state(client)["busy"]: break
            time.sleep(.01)
        assert state(client)["session"]["observations"] == []
        assert state(client)["session"]["privacy"]["status"] == "unreviewed"
        assert command(client, "note", {"text": "Late answer", "expectedQuestionId": "stale"}).status_code == 400


def test_recover_and_database_restart_preserve_text_but_not_capture(tmp_path):
    with TestClient(make_app(tmp_path), headers=HEADERS) as first:
        state(first)
        command(first, "new", {"title": "Retained workflow"})
        command(first, "note", {"text": "Expert reasoning"})
        command(first, "recording", {"state": "recording", "duration": 2})
        cookie = first.cookies.get(COOKIE)
        command(first, "recover")
        assert state(first)["recording"] == "idle"
    with TestClient(make_app(tmp_path), headers=HEADERS) as second:
        second.cookies.set(COOKIE, cookie, domain="testserver.local", path="/")
        snapshot = state(second)
        assert snapshot["session"]["evidence"][0]["text"] == "Expert reasoning"
        assert snapshot["recording"] == "idle" and not snapshot["cloud"]


def test_forget_and_delete_clear_derived_data(client):
    command(client, "new", {"title": "Forget me"})
    command(client, "note", {"text": "My evidence"})
    snapshot = state(client)
    service = client.app.state.runtime.guests[snapshot["guest"]].service
    source = service.session.evidence[0]
    service.session.knowledge = [Knowledge(title="Step", action="Check", decision="Continue", reason="Evidence",
        rule="Check first", exception="", guardrail="", escalation="", evidence_ids=[source.id], status="verified")]
    service.session.confirmed = True
    assert command(client, "forget", {"id": source.id}).status_code == 200
    assert not state(client)["session"]["knowledge"]
    for payload in ({}, {"confirmation": "delete"}, {"confirmation": "Confirm delete"}, {"confirmation": "confirm delete "}):
        assert command(client, "delete-session", payload).status_code == 400
        assert state(client)["session"]["id"] == snapshot["session"]["id"]
        assert len(state(client)["sessions"]) == 1
    assert command(client, "delete-session", {"confirmation": "confirm delete"}, sid="stale-workflow").status_code == 400
    assert state(client)["session"]["id"] == snapshot["session"]["id"]
    assert command(client, "delete-session", {"confirmation": "confirm delete"}).status_code == 200
    assert state(client)["sessions"] == [] and state(client)["session"] is None


def test_pending_ai_cannot_resurrect_deleted_session(tmp_path, monkeypatch):
    from apprentice.agents.knowledge import KnowledgeBuilder
    from apprentice.agents.assessor import Assessor
    monkeypatch.setattr(Assessor, "run", lambda self, session: session.evaluation)
    started, release = threading.Event(), threading.Event()
    def delayed(self, session):
        started.set()
        release.wait(3)
        return [], "Finished", []
    monkeypatch.setattr(KnowledgeBuilder, "run", delayed)
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="test-secret")), headers=HEADERS) as client:
        state(client)
        command(client, "new", {"title": "Cancel work", "cloud": True})
        command(client, "note", {"text": "Real input"})
        assert command(client, "build-map").status_code == 200
        assert started.wait(2)
        assert command(client, "delete-session", {"confirmation": "confirm delete"}).status_code == 200
        release.set()
        for _ in range(50):
            if not state(client)["busy"]: break
            time.sleep(.01)
        assert state(client)["session"] is None and state(client)["sessions"] == []
        assert "test-secret" not in client.get("/api/state").text


def test_provider_failure_is_real_error_not_fabricated_result(tmp_path, monkeypatch):
    from backend.voice import ElevenVoice
    import httpx
    monkeypatch.setattr(ElevenVoice, "transcribe", lambda *args: (_ for _ in ()).throw(httpx.ConnectError("sensitive-provider-detail")))
    with TestClient(make_app(tmp_path, settings=Settings(eleven_key="test-secret")), headers=HEADERS) as client:
        state(client)
        command(client, "new", {"title": "Voice"})
        sid = state(client)["session"]["id"]
        response = client.post(f"/api/transcribe?sessionId={sid}", content=b"audio")
        assert response.status_code == 502 and "sensitive-provider-detail" not in response.text
        assert state(client)["session"]["evidence"] == []


def test_budgets_are_atomic_and_persisted(tmp_path):
    async def run():
        db = HostedDatabase("sqlite:///" + str(tmp_path / "quota.sqlite3"))
        await db.consume("first", 1, 2)
        with pytest.raises(LimitError): await db.consume("first", 1, 2)
        await db.consume("second", 1, 2)
        with pytest.raises(LimitError): await db.consume("third", 1, 2)
        await db.close()
        db = HostedDatabase("sqlite:///" + str(tmp_path / "quota.sqlite3"))
        with pytest.raises(LimitError): await db.consume("fourth", 1, 2)
        await db.close()
    asyncio.run(run())


def test_production_requires_database_and_secret(monkeypatch):
    with pytest.raises(RuntimeError):
        create_web_app("sqlite:///:memory:", "short", production=True)
    monkeypatch.delenv("GUEST_SECRET", raising=False)
    monkeypatch.setenv("SESSION_SECRET", "replit-provisioned-test-secret-32-characters")
    # Construction validates configuration; no network connection until lifespan.
    create_web_app("postgresql://configured-at-startup", settings=Settings(), production=True)


def test_websocket_uses_cookie_and_checks_origin(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/events", headers={"Origin": "https://evil.test"}): pass
    with client.websocket_connect("/api/events", headers={"Origin": "http://testserver"}) as socket:
        assert socket.receive_json()["type"] == "resync"
        command(client, "new", {"title": "Socket"})
        assert socket.receive_json()["sessionId"] == state(client)["session"]["id"]
