import json
import logging
import time

import httpx
from fastapi.testclient import TestClient

from apprentice.agents.knowledge import KnowledgeBuilder
from apprentice.agents.assessor import Assessor
from apprentice.config import Settings
from tests.test_hosted import HEADERS, command, make_app, state


def records(caplog):
    return [json.loads(r.message.split("apprentice ", 1)[1]) for r in caplog.records if r.message.startswith("apprentice ")]


def test_request_id_version_validation_and_no_sensitive_input(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    with TestClient(make_app(tmp_path), headers=HEADERS) as client:
        state(client)
        rid = "a" * 32
        response = client.post("/api/command", headers={"X-Apprentice-Request-ID": rid}, json={"name": "new", "data": {"title": "PRIVATE-TITLE"}})
        assert response.headers["x-apprentice-request-id"] == rid
        assert response.headers["x-apprentice-version"] == "0.5.0"
        event = next(r for r in records(caplog) if r.get("request_id") == rid)
        assert event["operation"] == "new" and event["status"] == 200
        malformed = client.post("/api/command", json={"name": "PRIVATE-TOKEN" * 30})
        assert malformed.status_code == 422 and "PRIVATE-TOKEN" not in malformed.text
        denied = client.post("/api/command", headers={"Origin": "https://other.example"}, json={"name": "new"})
        assert denied.status_code == 403 and len(denied.headers["x-apprentice-request-id"]) == 32
        health = client.get("/healthz").json()
        assert health["version"] == "0.5.0" and health["revision"]
        assert "PRIVATE-TITLE" not in caplog.text and "PRIVATE-TOKEN" not in caplog.text


def test_unhandled_server_failure_returns_correlated_json_and_sanitized_trace(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    with TestClient(make_app(tmp_path), headers=HEADERS) as client:
        snapshot = state(client)
        service = client.app.state.runtime.guests[snapshot["guest"]].service
        async def broken():
            raise RuntimeError("PRIVATE-DATABASE-PASSWORD and private note")
        monkeypatch.setattr(service.repo, "list", broken)
        response = client.get("/api/state", headers={"X-Apprentice-Request-ID": "b" * 32})
        assert response.status_code == 500 and response.headers["x-apprentice-request-id"] == "b" * 32
        assert "request ID" in response.json()["detail"]
        event = next(r for r in records(caplog) if r["event"] == "request_exception")
        assert event["error_type"] == "RuntimeError" and event["trace"][-1]["function"] == "broken"
        assert "PRIVATE-DATABASE" not in caplog.text + response.text


def test_async_provider_failure_links_to_command_without_logging_provider_content(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    def fail(*_):
        raise httpx.HTTPStatusError("PRIVATE-PROVIDER-CONTENT", request=httpx.Request("POST", "https://provider.test/private"), response=httpx.Response(401))
    monkeypatch.setattr(KnowledgeBuilder, "run", fail)
    monkeypatch.setattr(Assessor, "run", lambda self, session: session.evaluation)
    with TestClient(make_app(tmp_path, settings=Settings(openai_key="PRIVATE-API-KEY")), headers=HEADERS) as client:
        state(client)
        command(client, "new", {"title": "Fixture"})
        command(client, "note", {"text": "PRIVATE-NOTE"})
        rid = "c" * 32
        sid = state(client)["session"]["id"]
        response = client.post("/api/command", headers={"X-Apprentice-Request-ID": rid}, json={"name": "build-map", "data": {}, "sessionId": sid})
        assert response.status_code == 200
        for _ in range(100):
            if not state(client)["busy"]: break
            time.sleep(.01)
        failure = next(r for r in records(caplog) if r["event"] == "provider_failed")
        assert failure["request_id"] == rid and failure["job_id"]
        assert failure["provider_status"] == 401 and failure["operation"] == "knowledge"
        assert any(r["event"] == "job_failed" and r["request_id"] == rid for r in records(caplog))
        assert "PRIVATE-PROVIDER-CONTENT" not in caplog.text and "PRIVATE-API-KEY" not in caplog.text
        assert "PRIVATE-NOTE" not in caplog.text
