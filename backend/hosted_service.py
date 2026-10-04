"""Reuse the learning pipeline with browser-owned media and hosted text storage."""
import math
import re

from apprentice.domain import Evidence
from backend.service import Service
from backend.hosted_store import LimitError

IDENTIFIER = re.compile(r"^[0-9a-f]{32}$")
ALLOWED = {"new", "open", "cloud", "recording", "note", "defer", "build-map", "debrief",
           "edit-knowledge", "confirm", "forget", "practice", "tutor", "coaching",
           "local-frame", "local-segment", "delete-session", "recover"}


class HostedService(Service):
    async def launch(self, role, work, apply):
        if not self.settings.openai_key:
            raise ValueError("The hosted OpenAI connection is unavailable. Manual notes and recording still work.")
        if not self.cloud:
            raise ValueError("Enable 'Use AI for this workflow' before requesting model analysis.")
        return await super().launch(role, work, apply)

    async def persist(self):
        if self.session:
            self.session.revision += 1
            await self.repo.save(self.session, {"practice": self.practice})
        await self.emit()

    async def restore(self):
        rows = await self.repo.list()
        if rows:
            self.session = await self.repo.load(rows[0]["id"])
            self.practice = (await self.repo.runtime(self.session.id)).get("practice", {"items": [], "answers": {}})

    async def hosted_command(self, name, data, sid):
        if name not in ALLOWED:
            raise ValueError("That operation is not available in the browser edition.")
        async with self.lock:
            if name not in {"new", "open", "recover"}:
                if not self.session or sid != self.session.id:
                    raise ValueError("The open workflow changed. Refresh before trying again.")
            if name == "new" and len(await self.repo.list()) >= 10:
                raise LimitError("This browser has ten saved workflows. Delete or export one before creating another.")
            if name in {"note", "local-frame", "tutor"} and len(self.require_session().evidence) >= 300:
                raise LimitError("This workflow has reached its evidence limit. Export it and start another.")
            if name == "recording":
                duration = float(data.get("duration", 0))
                if not math.isfinite(duration) or not 0 <= duration <= 301:
                    raise ValueError("Browser recordings are limited to five minutes per workflow.")
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
                await self.persist()
                return {}
            if name == "delete-session":
                if self.recording != "idle":
                    raise ValueError("Stop recording before deleting this workflow.")
                self.invalidate()
                await self.repo.delete(self.session.id)
                self.session = None
                self.practice = {"items": [], "answers": {}}
                self.cloud = False
                await self.emit()
                return {}
            if name == "recover":
                # A browser refresh cannot restore MediaStream tracks. Keep its text
                # and local chunks, but never claim capture is still running.
                self.invalidate()
                self.recording = "idle"
                self.cloud = False
                self.coaching = False
                await self.emit()
                return {}
            runtime = await self.repo.runtime(data["id"]) if name == "open" else None
            result = await self._command(name, data)
            if runtime:
                self.practice = runtime.get("practice", {"items": [], "answers": {}})
                await self.persist()
            return result

    async def hosted_frame(self, payload, duration, idle, sid, identifier):
        if not IDENTIFIER.fullmatch(identifier):
            raise ValueError("Invalid evidence identifier.")
        if not math.isfinite(duration) or not 0 <= duration <= 301 or not math.isfinite(idle):
            raise ValueError("Invalid recording duration.")
        # Request handlers for this guest are serialized by the API's operation
        # lock; Service.frame also holds its own state lock during mutation.
        if not self.session or sid != self.session.id:
            raise ValueError("The open workflow changed.")
        if not self.cloud:
            raise ValueError("Enable cloud analysis before sending a screenshot.")
        if len(self.session.evidence) >= 300:
            raise LimitError("This workflow has reached its evidence limit.")
        if any(e.id == identifier for e in self.session.evidence):
            return
        await self.frame(payload, duration, max(0, min(idle, 3600)), identifier)
