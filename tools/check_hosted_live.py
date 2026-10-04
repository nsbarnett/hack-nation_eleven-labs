"""Opt-in paid-provider smoke check using disposable, explicitly synthetic notes.

Run from the repository root. Does not record the screen, seed the application,
mock the model, or print credentials. Three real OpenAI calls are expected.
"""
import secrets
import tempfile
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from apprentice.config import Settings
from backend.web import create_web_app


def main():
    settings = Settings.load(Path.cwd())
    if not settings.openai_key:
        raise SystemExit("Configure OPENAI_API_KEY before running this opt-in check.")
    with tempfile.TemporaryDirectory(prefix="apprentice-live-") as directory:
        app = create_web_app("sqlite:///" + str(Path(directory) / "text.sqlite3"),
                             secrets.token_urlsafe(48), settings, production=False)
        with TestClient(app, headers={"Origin": "http://testserver", "X-Apprentice-Client": "web"}) as client:
            state = client.get("/api/state").json()
            def command(name, data=None):
                response = client.post("/api/command", json={"name": name, "data": data or {},
                    "sessionId": (state.get("session") or {}).get("id")})
                response.raise_for_status()
            def settled():
                nonlocal state
                for _ in range(120):
                    state = client.get("/api/state").json()
                    if not state["busy"]:
                        return
                    time.sleep(0.75)
                raise RuntimeError("Live model job did not finish within 90 seconds.")
            command("new", {"title": "Disposable live-provider verification", "cloud": True,
                "context": "Synthetic test of documenting a local writing task; not a real customer workflow."})
            settled()
            command("note", {"text": "For this test, I open a draft, read each paragraph, correct spelling, and save a new version. I save a new version to preserve the original. If a sentence changes meaning, I ask the author before changing it."})
            command("debrief")
            settled()
            if not state["question"]:
                raise RuntimeError("The real provider returned no debrief question; inspect configuration and provider access.")
            print("PASS: real OpenAI debrief question", flush=True)
            command("note", {"text": "For this synthetic test, the author reviews meaning changes. Spelling-only edits do not need that review.", "kind": "answer"})
            command("build-map")
            settled()
            items = state["session"]["knowledge"]
            if not items:
                raise RuntimeError("The real provider did not produce a supported Work Map.")
            print(f"PASS: real Work Map with {len(items)} evidence-linked steps", flush=True)
            # Only disposable synthetic evidence is confirmed in this smoke check.
            for item in items:
                command("edit-knowledge", {"id": item["id"], "patch": {"status": "verified"}})
            command("confirm")
            command("practice")
            settled()
            if not state["practice"]["items"]:
                raise RuntimeError("The real provider did not produce grounded practice.")
            print("PASS: real practice generated from confirmed test knowledge", flush=True)
            print("Voice is not exercised by this check; it requires a separately initiated microphone answer.", flush=True)
            command("delete-session", {"confirmation": "confirm delete"})


if __name__ == "__main__":
    main()
