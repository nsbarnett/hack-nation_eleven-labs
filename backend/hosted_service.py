"""Reuse the learning pipeline with browser-owned media and hosted text storage."""
import asyncio
import math
import re
import io
from PIL import Image

from apprentice.domain import Evidence
from apprentice.agents.observer import Observer
from apprentice.agents.gateway import Gateway
from backend.service import Service
from backend.hosted_store import LimitError
from apprentice import evaluation

IDENTIFIER = re.compile(r"^[0-9a-f]{32}$")
ALLOWED = {"new", "open", "cloud", "recording", "note", "defer", "build-map", "debrief",
           "edit-knowledge", "confirm", "forget", "practice", "tutor", "coaching",
           "local-frame", "local-segment", "delete-session", "recover", "privacy-reset", "privacy-approve", "review-gap",
           "reviewer", "reviewer-tick", "review-complete"}


class HostedService(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cloud = True

    def clear_screen_derivatives(self):
        """Keep expert text; discard knowledge which may depend on old screen pixels."""
        self.invalidate()
        for task in tuple(self.tasks):
            task.cancel()
        session = self.require_session()
        session.privacy.status = "unreviewed"
        session.privacy.revision += 1
        session.privacy.analyzed_frames = []
        session.privacy.question_revision = -1
        session.evidence = [e for e in session.evidence if e.kind not in {"screen", "trainee_screen"}]
        session.observations = []
        session.knowledge = []
        session.messages = [m for m in session.messages if m.role != "assistant"]
        session.confirmed = False
        evaluation.clear_derived(session)
        self.practice = {"items": [], "answers": {}}

    async def launch(self, role, work, apply):
        session = self.require_session()
        note_interjection = role == "assessment" and self.recording == "recording" and session.reviewer.enabled
        if not note_interjection and (session.recordings or self.recording != "idle" or any(e.image for e in session.evidence)) and session.privacy.status != "approved":
            raise ValueError("Review and approve the recording's privacy edits before using screen-based AI.")
        if not self.settings.openai_key:
            raise ValueError("The hosted OpenAI connection is unavailable. Manual notes and recording still work.")
        self.cloud = True
        return await super().launch(role, work, apply)

    async def persist(self):
        if self.session:
            evaluation.refresh(self.session)
            self.session.revision += 1
            await self.repo.save(self.session, {"practice": self.practice})
        await self.emit()

    async def restore(self):
        rows = await self.repo.list()
        if rows:
            self.session = await self.repo.load(rows[0]["id"])
            self.practice = (await self.repo.runtime(self.session.id)).get("practice", {"items": [], "answers": {}})
            self.restore_question()

    async def hosted_command(self, name, data, sid):
        if name not in ALLOWED:
            raise ValueError("That operation is not available in the browser edition.")
        async with self.lock:
            if name == "delete-session":
                target = str(data.get("id", ""))
                if data.get("confirmed") is not True or not IDENTIFIER.fullmatch(target):
                    raise ValueError("Confirm the selected workflow's deletion.")
                await self.repo.load(target)  # Guest-scoped ownership check.
                active = self.session and target == self.session.id
                if active:
                    if self.recording != "idle":
                        raise ValueError("Stop recording before deleting this workflow.")
                    self.invalidate(preserve_question=True)
                    tasks = tuple(self.tasks)
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                try:
                    await self.repo.delete(target)
                except Exception:
                    if active:
                        self.restore_question()
                    raise
                if active:
                    self.session = None
                    self.practice = {"items": [], "answers": {}}
                await self.emit()
                return {}
            if name not in {"new", "open", "recover"}:
                if not self.session or sid != self.session.id:
                    raise ValueError("The open workflow changed. Refresh before trying again.")
            if name == "cloud":
                self.cloud = True  # Compatibility: AI is a built-in browser capability.
                await self.emit()
                return {}
            if name == "review-complete":
                session = self.require_session()
                if session.privacy.status != "approved" or data.get("revision") != session.privacy.revision:
                    raise ValueError("The privacy revision changed. Review it before analysis.")
                if self.jobs or self.recording != "idle" or not session.privacy.analyzed_frames:
                    raise ValueError("Finish analyzing the approved frames first.")
                if session.privacy.question_revision == session.privacy.revision:
                    return {}
                if self.question:
                    session.privacy.question_revision = session.privacy.revision
                    await self.persist()
                    return {}
                return await self._command("debrief", {"_review_revision": session.privacy.revision})
            if name == "new" and len(await self.repo.list()) >= 10:
                raise LimitError("This browser has ten saved workflows. Delete or export one before creating another.")
            if name in {"note", "defer"} and "expectedQuestionId" in data:
                if data["expectedQuestionId"] != (self.question or {}).get("id"):
                    raise ValueError("The question changed. Review the current question before answering.")
            if name in {"privacy-reset", "privacy-approve"}:
                session = self.require_session()
                if self.recording != "idle":
                    raise ValueError("Stop recording before reviewing privacy.")
                if data.get("revision") != session.privacy.revision:
                    raise ValueError("The privacy revision changed. Refresh the review.")
                if name == "privacy-reset":
                    self.clear_screen_derivatives()
                else:
                    if not session.recordings:
                        raise ValueError("Record a workflow before approving its media.")
                    session.privacy.status = "approved"
                await self.persist()
                return session.privacy.model_dump()
            if name in {"note", "review-gap", "local-frame", "tutor"} and len(self.require_session().evidence) >= 300:
                raise LimitError("This workflow has reached its evidence limit. Export it and start another.")
            if name == "recording":
                duration = float(data.get("duration", 0))
                if not math.isfinite(duration) or not 0 <= duration <= 301:
                    raise ValueError("Browser recordings are limited to five minutes per workflow.")
                if data.get("state") == "recording" and self.recording != "recording":
                    if self.recording not in {"idle", "paused"}:
                        raise ValueError("Invalid recording transition.")
                    self.clear_screen_derivatives()
            if name == "local-frame":
                if self.recording != "recording":
                    return {}
                identifier = str(data.get("id", ""))
                if not IDENTIFIER.fullmatch(identifier):
                    raise ValueError("Invalid evidence identifier.")
                if not any(e.id == identifier for e in self.session.evidence):
                    timestamp = float(data.get("duration", 0))
                    if not math.isfinite(timestamp) or not 0 <= timestamp <= 301:
                        raise ValueError("Invalid recording duration.")
                    self.session.evidence.append(Evidence(id=identifier, kind="trainee_screen" if self.coaching else "screen",
                                                          image=identifier + ".jpg", timestamp=timestamp))
                    await self.persist()
                return {}
            if name == "local-segment":
                filename = str(data.get("filename", ""))
                if not re.fullmatch(r"[0-9a-f]{32}\.webm", filename):
                    raise ValueError("Invalid local recording identifier.")
                if filename not in self.session.recordings:
                    self.session.recordings.append(filename)
                if "start" in data and "duration" in data:
                    start, duration = float(data["start"]), float(data["duration"])
                    if not math.isfinite(start + duration) or min(start, duration) < 0 or start + duration > 301:
                        raise ValueError("Invalid local segment timing.")
                    self.session.duration = max(self.session.duration, start + duration)
                await self.persist()
                return {}
            if name == "recover":
                # A browser refresh cannot restore MediaStream tracks. Keep its text
                # and local chunks, but never claim capture is still running.
                self.invalidate(preserve_question=True)
                self.recording = "idle"
                self.cloud = True
                self.coaching = False
                if self.session:
                    self.restore_question()
                await self.emit()
                return {}
            runtime = await self.repo.runtime(data["id"]) if name == "open" else None
            result = await self._command(name, data)
            self.cloud = True
            if name == "forget":
                self.clear_screen_derivatives()
                await self.persist()
            if runtime:
                self.practice = runtime.get("practice", {"items": [], "answers": {}})
                await self.persist()
            return result

    async def hosted_frame(self, payload, duration, idle, sid, identifier):
        raise ValueError("Live screen uploads are disabled. Review the recording and upload approved redacted frames.")

    async def reviewed_frame(self, payload, duration, sid, identifier, revision):
        """Post-capture analysis. No raw recording endpoint exists on the server."""
        async with self.lock:
            session = self.require_session()
            if sid != session.id or self.recording != "idle":
                raise ValueError("Stop recording and open the reviewed workflow first.")
            if session.privacy.status != "approved" or revision != session.privacy.revision:
                raise ValueError("This privacy revision is not approved.")
            if not self.settings.openai_key:
                raise ValueError("The hosted AI connection is unavailable. Contact the app owner.")
            if not IDENTIFIER.fullmatch(identifier) or not math.isfinite(duration) or not 0 <= duration <= session.duration + 1:
                raise ValueError("Invalid reviewed frame metadata.")
            if identifier in session.privacy.analyzed_frames:
                return
            if self.jobs:
                raise LimitError("Wait for the current analysis to finish.")
            if len(session.evidence) >= 300:
                raise LimitError("This workflow has reached its evidence limit.")
            def decode():
                image = Image.open(io.BytesIO(payload))
                if image.width * image.height > 16_000_000:
                    raise ValueError("Screen image is too large.")
                image.thumbnail((1280, 900))
                output = io.BytesIO()
                image.convert("RGB").save(output, "JPEG", quality=75)
                return output.getvalue()
            jpeg = await self.repo.call(decode)
            evidence = Evidence(id=identifier, kind="screen", timestamp=duration, image=identifier + ".jpg")
            session.evidence.append(evidence)
            await self.repo.save_frame(sid, evidence.image, jpeg)
            images = await self.repo.images(session, "screen")
            snapshot = session.model_copy(deep=True)
            def apply(result):
                self.session.observations.extend(result)
                self.session.privacy.analyzed_frames.append(identifier)
                # Historical frames are never rejected because the recording has ended.
                # Automatic question selection runs after the whole approved batch.
                evaluation.refresh(self.session)
            await self.launch("observer", lambda: Observer(Gateway(self.settings)).run(snapshot, images), apply)
            await self.persist()
