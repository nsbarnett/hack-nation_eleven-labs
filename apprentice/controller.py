"""Application coordinator and the only QML-facing API.

Slots implement user actions, services do focused work, and agents return typed
proposals. Every async callback carries a session ID and privacy generation;
switching sessions, stopping observation, or deleting evidence invalidates it.
"""

import json
import sqlite3
from pathlib import Path
import time

import numpy as np
from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot, Qt, QMicrophonePermission
from PySide6.QtGui import QDesktopServices, QGuiApplication, QImage

from apprentice.agents.gateway import Gateway
from apprentice.agents.interviewer import Interviewer
from apprentice.agents.knowledge import KnowledgeBuilder
from apprentice.agents.observer import Observer
from apprentice.agents.tutor import Tutor
from apprentice.capture import Capture, PreviewProvider
from apprentice.context import context_for
from apprentice.demo import create_demo
from apprentice.domain import Evidence, Knowledge, Message, Session, TrainingCase, new_id
from apprentice.evidence import forget
from apprentice.exporting import export_session
from apprentice.platforms import idle_seconds
from apprentice.rules import evaluate
from apprentice.scoring import QuestionPolicy, completeness
from apprentice.voice import Audio, ElevenVoice
from apprentice.workers import Jobs


class Controller(QObject):
    changed = Signal()
    clockChanged = Signal()
    previewChanged = Signal()
    showMain = Signal()
    minimizeMain = Signal()
    navigate = Signal(str)
    quitReady = Signal()

    def __init__(self, settings, store, parent=None, timers=True):
        super().__init__(parent)
        self.settings, self.store = settings, store
        self.session = None
        self.recording = self.paused = self.off_record = False
        self.teaching = False
        self.cloud_enabled = False
        self.prompts = True
        self.voice_enabled = False
        self.monitor = 0
        self.notice = "Start a session or explore the offline demonstration."
        self.pending_question = ""
        self.pending_sources = []
        self.generation = 0
        self.audio_generation = 0
        self.started = 0.0
        self.preview_version = 0
        self.last_analysis = 0.0
        self.last_analyzed_ids = set()
        self.last_change = time.monotonic()
        self.previous_thumbnail = None
        self.last_frame = None
        self.preview = PreviewProvider()
        self.capture = Capture(self, settings.sample_seconds)
        self.capture.sampled.connect(self._sample)
        # Native backends can report failure from inside start(). Queue the
        # handler so shutdown cannot re-enter an unfinished start operation.
        self.capture.failed.connect(self._capture_error, Qt.ConnectionType.QueuedConnection)
        self.audio = Audio(self)
        self.audio.changed.connect(self.changed)
        self.audio.failed.connect(self._notify)
        self.audio.captured.connect(self._transcribe)
        self.audio.speechFinished.connect(self._after_speech)
        self.jobs = Jobs(self)
        self.policy = QuestionPolicy()
        gateway = Gateway(settings)
        self.observer = Observer(gateway)
        self.interviewer = Interviewer(gateway)
        self.builder = KnowledgeBuilder(gateway)
        self.tutor = Tutor(gateway)
        self.voice = ElevenVoice(settings)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        if timers:
            self.timer.start()

    @Property("QVariantMap", notify=changed)
    def state(self):
        s = self.session
        evidence = []
        if s:
            for e in reversed(s.evidence[-80:]):
                item = e.model_dump()
                item["imageUrl"] = QUrl.fromLocalFile(str(self.store.media(s.id, e.image))).toString() if e.image else ""
                evidence.append(item)
        return {
            "sessionId": s.id if s else "", "title": s.title if s else "Your expert, understood.",
            "context": s.context if s else "", "mode": s.mode if s else "live", "phase": s.phase if s else "capture",
            "recording": self.recording, "paused": self.paused, "offRecord": self.off_record,
            "teaching": self.teaching,
            "prompts": self.prompts, "voiceEnabled": self.voice_enabled,
            "cloudEnabled": self.cloud_enabled, "openaiReady": bool(self.settings.openai_key),
            "elevenReady": bool(self.settings.eleven_key),
            "listening": self.audio.listening, "speaking": self.audio.speaking,
            "notice": self.notice, "busy": bool(self.jobs.active),
            "history": self.store.list(), "evidence": evidence,
            "observations": [o.model_dump() for o in s.observations[-60:]] if s else [],
            "knowledge": [k.model_dump() for k in s.knowledge] if s else [],
            "messages": [m.model_dump() for m in s.messages[-60:]] if s else [],
            "confirmed": s.confirmed if s else False,
            "coverage": completeness(s.knowledge) if s else 0,
            "evidenceCount": len(s.evidence) if s else 0,
            "pendingQuestion": self.pending_question,
            "monitors": [f"{i + 1}. {x.name()} ({x.size().width()} × {x.size().height()})" for i, x in enumerate(QGuiApplication.screens())],
            "dataPath": str(self.store.root), "model": self.settings.model,
        }

    @Property(str, notify=clockChanged)
    def clock(self):
        seconds = int(self.session.duration) if self.session else 0
        return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"

    @Property(str, notify=previewChanged)
    def previewUrl(self):
        return f"image://screen/frame?{self.preview_version}"

    def _notify(self, text):
        self.notice = text
        self.changed.emit()

    def _save(self):
        if self.session:
            try:
                self.store.save(self.session)
            except (OSError, sqlite3.Error):
                self.capture.stop()
                self._invalidate()
                self.recording = False
                self.off_record = True
                self.notice = "Storage is unavailable. Observation stopped to avoid losing evidence. Free disk space or restore folder access; this session remains in memory."
                self.changed.emit()
                return False
        self.changed.emit()
        return True

    def _reset_observation(self):
        """Clear session-specific caches and restore only this session's image."""
        self.policy = QuestionPolicy()
        self.last_analyzed_ids.clear()
        self.last_analysis = 0
        self.previous_thumbnail = None
        self.last_frame = None
        image = QImage()
        if self.session:
            for evidence in reversed(self.session.evidence):
                if evidence.image:
                    image = QImage(str(self.store.media(self.session.id, evidence.image)))
                    if not image.isNull():
                        break
        if image.isNull():
            image = QImage(1280, 720, QImage.Format.Format_RGB32)
            image.fill("#f3f4f6")
        self.preview.image = image
        self.preview_version += 1
        self.previewChanged.emit()

    def _message(self, text, role="assistant", sources=None):
        if self.session:
            self.session.messages.append(Message(role=role, text=text, evidence_ids=sources or []))
            self._save()

    def _invalidate(self):
        self.generation += 1
        self.audio_generation += 1
        self.audio.cancel()

    def _submit(self, name, fn, success):
        if not self.session:
            return
        sid, generation = self.session.id, self.generation

        def done(result, error):
            if not self.session or self.session.id != sid or self.generation != generation:
                self.changed.emit()
                return
            if error:
                self._notify(f"{name.title()} could not finish ({error}). Your session is saved. Check credentials/network and retry.")
                return
            try:
                success(result)
            except (ValueError, OSError, KeyError):
                self._notify(f"{name.title()} returned an unusable result. Retained evidence is unchanged; please retry.")
            self.changed.emit()

        if self.jobs.submit(name, fn, done):
            self.changed.emit()
        else:
            self._notify(f"{name.title()} is already running.")

    @Slot(str, str, int, bool)
    def newSession(self, title, context, monitor, cloud):
        if self.recording:
            self._notify("Stop the current recording before creating another session.")
            return
        self._invalidate()
        self.session = Session(title=title.strip()[:160] or "Untitled workflow", context=context.strip()[:12000])
        self.paused = self.off_record = self.teaching = False
        self.monitor = max(0, monitor)
        self.cloud_enabled = bool(cloud and self.settings.openai_key)
        self.pending_question, self.pending_sources = "", []
        self._reset_observation()
        self.notice = "Session ready. Start recording when the intended screen is visible."
        self._save()
        self.clockChanged.emit()
        self.navigate.emit("Capture")

    @Slot()
    def loadDemo(self):
        if self.recording:
            self._notify("Stop recording before opening a demonstration.")
            return
        self._invalidate()
        self.session = create_demo()
        self.paused = self.off_record = self.teaching = False
        self.pending_question, self.pending_sources = "", []
        self.cloud_enabled = False
        self._reset_observation()
        self.notice = "Fictional offline demo. Review the draft rules, confirm the map, then open Teach."
        self._save()
        self.clockChanged.emit()
        self.navigate.emit("Work Map")

    @Slot(str)
    def openSession(self, session_id):
        if self.recording:
            self._notify("Stop recording before opening another session.")
            return
        try:
            session = self.store.load(session_id)
        except (KeyError, ValueError):
            self._notify("This session could not be opened.")
            return
        self._invalidate()
        self.session = session
        self.paused = self.off_record = self.teaching = False
        self.cloud_enabled = False  # Reopening never silently re-enables upload.
        self.pending_question, self.pending_sources = "", []
        self._reset_observation()
        self.notice = "Session restored. Cloud analysis is off until explicitly enabled."
        self._save()
        self.clockChanged.emit()
        self.navigate.emit("Work Map" if session.knowledge else "Capture")

    @Slot()
    def startRecording(self):
        self._begin_recording(False)

    @Slot()
    def startTeaching(self):
        if not self.session or not self.session.confirmed:
            self._notify("Confirm the Work Map before watching a trainee.")
            return
        self._begin_recording(True)

    def _begin_recording(self, teaching):
        if not self.session or self.recording:
            return
        if self.session.mode == "demo":
            self._notify("The demo contains fictional evidence. Create a new live session to record your screen.")
            return
        self.started = time.monotonic() - self.session.duration
        self.recording, self.paused, self.off_record = True, False, False
        self.teaching = teaching
        self.session.phase = "teach" if teaching else "capture"
        if not teaching:
            self.session.confirmed = False
        self.last_analysis = 0
        try:
            self._start_segment()
        except (ValueError, OSError) as exc:
            self.recording = False
            self._notify(str(exc))
            return
        self.notice = "Recording. Minimized controls remain available; microphone is off."
        if self._save():
            self.minimizeMain.emit()

    def _start_segment(self):
        name = f"recording-{new_id()[:12]}.mp4"
        self.capture.start(self.monitor, self.store.media(self.session.id, name), self.started)
        self.session.recordings.append(name)

    @Slot()
    def stopRecording(self):
        if not self.recording:
            return
        self.capture.stop()
        self._invalidate()
        self.recording = self.paused = self.off_record = False
        self.session.duration = time.monotonic() - self.started
        self.session.phase = "teach" if self.teaching else "debrief"
        self.notice = "Trainee observation saved. The confirmed expert map is unchanged." if self.teaching else "Recording saved. Add remaining context, ask a debrief question, then build the Work Map."
        self.teaching = False
        self._save()
        self.showMain.emit()

    @Slot()
    def togglePause(self):
        if not self.recording:
            return
        if self.paused:
            try:
                self._start_segment()
            except (ValueError, OSError) as exc:
                self._notify(str(exc))
                return
            self.paused = self.off_record = False
            self.notice = "Observation resumed in a new video segment."
        else:
            self.capture.stop()
            self._invalidate()
            self.paused = True
            self.notice = "Paused: screen capture, microphone, and new AI requests are stopped."
        self._save()

    @Slot()
    def offRecord(self):
        if self.recording and not self.paused:
            self.togglePause()
        else:
            self._invalidate()
        self.off_record = True
        self.pending_question, self.pending_sources = "", []
        self._notify("Off the record. No new capture, notes, or uploads until observation resumes. Previously sent data cannot be recalled.")

    def _capture_error(self, text):
        if self.recording:
            self.stopRecording()
        self._notify("Recording stopped: " + text + " Check screen permission, monitor connection, and available disk space.")

    def _sample(self, image, timestamp):
        if not self.recording or self.paused or self.off_record or not self.session:
            return
        self.last_frame = image.copy()
        self.preview.image = image.copy()
        self.preview_version += 1
        self.previewChanged.emit()
        tiny = image.scaled(64, 40).convertToFormat(QImage.Format.Format_Grayscale8)
        pixels = np.frombuffer(tiny.constBits(), dtype=np.uint8).copy()
        if self.previous_thumbnail is None or np.mean(np.abs(pixels.astype(float) - self.previous_thumbnail)) > 3:
            self.last_change = time.monotonic()
        self.previous_thumbnail = pixels.astype(float)
        evidence = Evidence(kind="trainee_screen" if self.teaching else "screen", timestamp=timestamp, text="Trainee screen sample" if self.teaching else "Screen sample")
        evidence.image = evidence.id + ".jpg"
        try:
            saved = image.save(str(self.store.media(self.session.id, evidence.image)), "JPEG", 82)
        except OSError:
            saved = False
        if not saved:
            self._capture_error("Could not save a screenshot")
            return
        self.session.evidence.append(evidence)
        self._save()

    def _tick(self):
        if not self.session:
            return
        now = time.monotonic()
        if self.recording:
            self.session.duration = now - self.started
            self.clockChanged.emit()
        if not self.recording or self.paused or self.off_record:
            return
        if self.teaching:
            if self.cloud_enabled and now - self.last_analysis >= self.settings.analysis_seconds and "tutor_watch" not in self.jobs.active:
                self._watch_trainee()
            return
        if self.cloud_enabled and now - self.last_analysis >= self.settings.analysis_seconds and "observe" not in self.jobs.active:
            self.analyzeLatest()
        if self.policy.eligible(now, idle_seconds(), now - self.last_change, self.prompts,
                                bool(self.pending_question) or self.audio.listening or self.audio.speaking or "speak" in self.jobs.active):
            times = {e.id: e.timestamp for e in self.session.evidence}
            recent = [o for o in self.session.observations if self.session.duration - max((times.get(e, 0) for e in o.evidence_ids), default=0) <= 120]
            candidate = self.policy.choose(recent)
            if candidate:
                candidate.asked = True
                self.policy.delivered.append(now)
                self._ask(candidate.question, candidate.evidence_ids)

    def _watch_trainee(self):
        screens = [e for e in self.session.evidence if e.kind == "trainee_screen" and e.id not in self.last_analyzed_ids][-3:]
        if not screens:
            return
        self.last_analysis = time.monotonic()
        snapshot = self.session.model_copy(deep=True)
        images = [(e.id, self.store.media(snapshot.id, e.image)) for e in screens]

        def received(result):
            self.last_analyzed_ids.update(e.id for e in screens)
            if result.verdict == "warn" and result.explanation not in [m.text for m in self.session.messages[-6:]]:
                refs = [e.id for e in screens] + list({e for k in snapshot.knowledge if k.id in result.knowledge_ids for e in k.evidence_ids})
                self._message(result.explanation, sources=refs)
                self.notice = "The tutor spotted a possible issue. Open the app to review its evidence."
                self.changed.emit()
        self._submit("tutor_watch", lambda: self.tutor.observe(snapshot, images), received)

    @Slot()
    def analyzeLatest(self):
        if not self._can_cloud() or self.session.mode == "demo":
            return
        screens = [e for e in self.session.evidence if e.kind == "screen" and e.image and e.id not in self.last_analyzed_ids][-4:]
        if not screens:
            return
        self.last_analysis = time.monotonic()
        snapshot = self.session.model_copy(deep=True)
        images = [(e.id, self.store.media(snapshot.id, e.image)) for e in screens]

        def received(actions):
            self.last_analyzed_ids.update(e.id for e in screens)
            summaries = {o.summary.casefold() for o in self.session.observations}
            self.session.observations.extend(a for a in actions if a.summary.casefold() not in summaries)
            self.notice = f"Observed {len(actions)} meaningful change(s). Questions wait for a pause."
            self._save()

        self._submit("observe", lambda: self.observer.run(snapshot, images), received)

    def _can_cloud(self):
        if self.off_record or self.paused:
            self._notify("Resume observation before using AI.")
            return False
        if not self.cloud_enabled or not self.settings.openai_key:
            self._notify("Enable cloud analysis in Settings and configure OPENAI_API_KEY to use this action.")
            return False
        return bool(self.session)

    def _ask(self, question, sources):
        self.pending_question, self.pending_sources = question, list(sources)
        self._message(question, sources=sources)
        self.notice = "A question is ready. Answer by text or voice, or defer it."
        if self.voice_enabled and self.settings.eleven_key:
            token = self.audio_generation

            def play(data):
                if self.voice_enabled and self.prompts and token == self.audio_generation and not self.off_record:
                    self.audio.play(data)
            self._submit("speak", lambda: self.voice.speak(question), play)
        self.changed.emit()

    @Slot()
    def deferQuestion(self):
        self.pending_question, self.pending_sources = "", []
        self.audio_generation += 1
        self.audio.cancel()
        self._notify("Question deferred. You can explain it later in the debrief.")

    @Slot(str)
    def addNote(self, text):
        if not self.session or not text.strip():
            return
        if self.off_record or self.paused:
            self._notify("Notes are disabled while observation is paused or off the record.")
            return
        self.audio_generation += 1
        self.audio.cancel()
        e = Evidence(kind="trainee_note" if self.teaching else "answer" if self.pending_question else "note", timestamp=self.session.duration,
                     text=text.strip()[:12000], question=self.pending_question, related_ids=self.pending_sources.copy())
        self.session.evidence.append(e)
        if not self.teaching:
            self.session.confirmed = False
        self.session.revision += 1
        self._invalidate()
        self._message(e.text, "user", [e.id])
        self.pending_question, self.pending_sources = "", []
        self.notice = "Context saved and linked to its source. Rebuild or review the map when ready."
        self._save()

    @Slot(str, int)
    def moveKnowledge(self, item_id, direction):
        if not self.session or self.recording:
            return
        ids = [k.id for k in self.session.knowledge]
        if item_id not in ids:
            return
        index = ids.index(item_id)
        destination = index + (1 if direction > 0 else -1)
        if not 0 <= destination < len(ids):
            return
        item = self.session.knowledge.pop(index)
        self.session.knowledge.insert(destination, item)
        self.session.revision += 1
        self.session.confirmed = False
        self._invalidate()
        self._save()

    @Slot(str, str)
    def addReference(self, name, text):
        if not self.session or self.off_record or self.paused or not text.strip():
            return
        e = Evidence(kind="reference", text=f"{name.strip()[:160]}\n{text.strip()[:30000]}", timestamp=self.session.duration)
        self.session.evidence.append(e)
        self.session.confirmed = False
        self.session.revision += 1
        self._invalidate()
        self.notice = "Reference excerpt saved. AI will treat it as source material, not instructions."
        self._save()

    @Slot()
    def debrief(self):
        if not self.session or self.recording:
            self._notify("Stop recording to begin the debrief.")
            return
        if not self.session.evidence:
            self._notify("Capture a screen or add an expert note first.")
            return
        self.session.phase = "debrief"
        if self.session.mode == "demo":
            self._ask("Does the EUR 5,000 boundary apply to other purchase types or currencies?", [self.session.evidence[1].id])
            return
        if self._can_cloud():
            snapshot = self.session.model_copy(deep=True)
            self._submit("debrief", lambda: self.interviewer.debrief(snapshot),
                lambda r: self._ask(r.question, r.evidence_ids) if r.question else self._notify("No further question proposed. Build and review the map."))

    @Slot()
    def buildMap(self):
        if not self.session or self.recording:
            self._notify("Stop recording before building the Work Map.")
            return
        if self.session.mode == "demo":
            self._notify("Demo rules are ready for review. Changes to demo notes do not generate new AI rules; use live mode for that.")
            self.navigate.emit("Work Map")
            return
        if not self.session.evidence:
            self._notify("Add evidence or expert notes before building a map.")
            return
        if not self._can_cloud():
            return
        snapshot = self.session.model_copy(deep=True)
        revision = self.session.revision

        def received(result):
            if self.session.revision != revision:
                self._notify("The map changed during generation. Retry to preserve your edits.")
                return
            items, teach_back, gaps = result
            self.session.knowledge = items
            self.session.confirmed = False
            self.session.phase = "review"
            self.session.revision += 1
            self._message(teach_back + ("\n\nNeeds clarification:\n" + "\n".join(gaps) if gaps else ""), sources=list(dict.fromkeys(e for item in items for e in item.evidence_ids)))
            self.notice = "Draft map ready. Inspect the evidence and exact checks, correct errors, then confirm."
            self._save()
            self.navigate.emit("Work Map")
        self._submit("map", lambda: self.builder.run(snapshot), received)

    @Slot(str, str)
    def editKnowledge(self, item_id, json_text):
        if not self.session or self.recording:
            return
        try:
            payload = json.loads(json_text)
            original = next(k for k in self.session.knowledge if k.id == item_id)
            allowed = {"title", "action", "decision", "reason", "rule", "exception", "guardrail", "escalation", "check"}
            values = {k: v for k, v in payload.items() if k in allowed}
            revised = Knowledge.model_validate({**original.model_dump(), **values, "status": "inferred"})
            self.session.knowledge = [revised if k.id == item_id else k for k in self.session.knowledge]
            self.session.confirmed = False
            self.session.revision += 1
            self._invalidate()
            self.notice = "Rule updated. Expert confirmation is required again."
            self._save()
        except (ValueError, StopIteration, TypeError):
            self._notify("Could not save. Check that the rule-check field contains valid JSON or null.")

    @Slot(str)
    def rejectKnowledge(self, item_id):
        if not self.session or self.recording:
            return
        for item in self.session.knowledge:
            if item.id == item_id:
                item.status = "rejected"
        self.session.confirmed = False
        self.session.revision += 1
        self._invalidate()
        self._save()

    @Slot()
    def confirmMap(self):
        if not self.session or self.recording:
            return
        active = [k for k in self.session.knowledge if k.status != "rejected"]
        if not active:
            self._notify("Build a map with at least one supported rule first.")
            return
        if any(k.status in ("needs_clarification", "conflicting") for k in active):
            self._notify("Resolve or reject items that need clarification before confirming the map.")
            return
        allowed = {e.id for e in self.session.evidence if not e.kind.startswith("trainee")}
        if any(not k.evidence_ids or not set(k.evidence_ids).issubset(allowed) for k in active):
            self._notify("Every rule must link to retained evidence.")
            return
        for item in active:
            item.status = "verified"
        self.session.confirmed = True
        self.session.phase = "teach"
        self.session.revision += 1
        self._invalidate()
        self.notice = "Work Map confirmed by you. The tutor can now use this version."
        self._save()

    @Slot(str)
    def forgetEvidence(self, evidence_id):
        if not self.session or self.recording:
            self._notify("Stop recording before deleting evidence.")
            return
        target = next((e for e in self.session.evidence if e.id == evidence_id), None)
        if not target:
            return
        self._invalidate()
        self.pending_question, self.pending_sources = "", []
        # Raw video can contain this moment even when its JPEG is deleted. Drop
        # all session videos rather than falsely claim frame-level video erasure.
        paths = [e.image for e in self.session.evidence if e.id == evidence_id and e.image] + self.session.recordings
        try:
            for relative in paths:
                self.store.media(self.session.id, relative).unlink(missing_ok=True)
        except OSError:
            self._notify("A recording is still in use. Close video players, wait for finalization, and retry deletion.")
            return
        forget(self.session, evidence_id)
        self.session.recordings = []
        self._reset_observation()
        self.notice = "Source removed; derived map and session videos discarded. Rebuild from retained evidence. Existing exports or provider copies are not recalled."
        self._save()

    @Slot(str)
    def openEvidence(self, evidence_id):
        if not self.session:
            return
        e = next((e for e in self.session.evidence if e.id == evidence_id), None)
        if e and e.image:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.media(self.session.id, e.image))))
        elif e:
            self._notify(e.text)

    @Slot()
    def exportMap(self):
        if not self.session or not self.session.knowledge:
            self._notify("Build a Work Map before exporting.")
            return
        try:
            folder = export_session(self.session, self.store, self.store.root / "exports")
            self._notify("Exported HTML, Markdown, JSON, and screenshots to " + str(folder))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except OSError:
            self._notify("Export failed. Check available disk space and data-folder permissions.")

    @Slot(str, result=str)
    def checkCase(self, case_json):
        if self.off_record or self.paused:
            return json.dumps({"verdict": "unknown", "explanation": "Resume observation before reviewing a case.", "knowledge_ids": []})
        if not self.session or not self.session.confirmed:
            return json.dumps({"verdict": "unknown", "explanation": "Confirm a Work Map first.", "knowledge_ids": []})
        try:
            case = TrainingCase.model_validate_json(case_json).model_dump(mode="json")
            result = evaluate(self.session.knowledge, case, required_fields={"category"})
            self._message("Training case: " + result.explanation, sources=list({e for k in self.session.knowledge if k.id in result.knowledge_ids for e in k.evidence_ids}))
            return result.model_dump_json()
        except (ValueError, TypeError):
            return json.dumps({"verdict": "unknown", "explanation": "Enter a valid case.", "knowledge_ids": []})

    @Slot(str, result=bool)
    def savePractice(self, case_json):
        # Always evaluate the actual case again at save time, never trust a UI
        # badge computed before the user edited a field or the expert map.
        if not self.session or not self.session.confirmed or self.off_record or self.paused:
            return False
        try:
            case = TrainingCase.model_validate_json(case_json).model_dump(mode="json")
            result = evaluate(self.session.knowledge, case, required_fields={"category"})
            if result.verdict != "ok":
                return False
            self.session.evidence.append(Evidence(kind="trainee_attempt", text=json.dumps(case, ensure_ascii=False), timestamp=self.session.duration,
                related_ids=list({e for k in self.session.knowledge if k.id in result.knowledge_ids for e in k.evidence_ids})))
            return self._save()
        except (ValueError, TypeError, AttributeError):
            return False

    @Slot(str)
    def askTutor(self, question):
        if not self.session or not self.session.confirmed or not question.strip():
            self._notify("Confirm the map before asking the tutor.")
            return
        if self.session.mode == "demo":
            self._message("Offline tutor: use the structured practice case to test the fictional rules. Open a rule's evidence to read the expert explanation. Free-form tutoring requires a live session and configured AI.")
            return
        if self._can_cloud():
            snapshot = self.session.model_copy(deep=True)
            self._message(question, "user")
            self._submit("tutor", lambda: self.tutor.explain(snapshot, question), lambda r: self._message(
                r.explanation, sources=list({e for k in snapshot.knowledge if k.id in r.knowledge_ids for e in k.evidence_ids})))

    @Slot(bool)
    def setCloud(self, enabled):
        if enabled and not self.settings.openai_key:
            self._notify("Add OPENAI_API_KEY to .env and restart first.")
            return
        if self.session and self.session.mode == "demo":
            self._notify("Demo sessions stay offline. Create a live session for cloud analysis.")
            return
        self._invalidate()
        self.cloud_enabled = enabled
        self._notify("Cloud analysis enabled: selected screenshots, notes and references may be sent to OpenAI." if enabled else "Cloud analysis disabled. Recording remains local.")

    @Slot(bool)
    def setPrompts(self, enabled):
        self.prompts = enabled
        if not enabled:
            self.audio_generation += 1
            self.audio.cancel()
        self.changed.emit()

    @Slot(bool)
    def setVoice(self, enabled):
        if enabled and not self.settings.eleven_key:
            self._notify("Add ELEVENLABS_API_KEY to .env and restart for speech. Text questions remain available.")
            return
        self.voice_enabled = enabled
        self.audio_generation += 1
        if not enabled:
            self.audio.cancel()
        self.changed.emit()

    @Slot()
    def toggleVoiceNote(self):
        if not self.session or self.off_record or self.paused:
            self._notify("Open a session and resume observation to add a voice note.")
            return
        if not self.settings.eleven_key:
            self._notify("Configure ELEVENLABS_API_KEY for transcription, or type a note.")
            return
        if self.audio.listening:
            self.audio.finish()
            return
        self._request_microphone()

    def _request_microphone(self):
        app = QGuiApplication.instance()
        permission = QMicrophonePermission()
        status = app.checkPermission(permission)
        if status == Qt.PermissionStatus.Granted:
            self.audio.listen()
        elif status == Qt.PermissionStatus.Denied:
            self._notify("Microphone permission is denied. Enable it in system settings.")
        else:
            generation = self.generation
            audio_generation = self.audio_generation
            app.requestPermission(permission, self, lambda result: self.audio.listen()
                if generation == self.generation and audio_generation == self.audio_generation
                and result.status() == Qt.PermissionStatus.Granted and not self.off_record and not self.paused
                else self._notify("Microphone permission was not granted or the session changed."))

    def _after_speech(self):
        if self.pending_question and self.voice_enabled and self.prompts and not self.off_record and not self.paused:
            self._request_microphone()

    def _transcribe(self, data):
        token = self.audio_generation
        self._submit("transcribe", lambda: self.voice.transcribe(data),
            lambda text: self.addNote(text) if token == self.audio_generation else None)

    @Slot()
    def openDataFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root)))

    @Slot()
    def reveal(self):
        self.showMain.emit()

    @Slot()
    def quit(self):
        self.stopRecording()
        self._invalidate()
        self._save()
        self.quitReady.emit()

    def shutdown(self):
        self.timer.stop()
        if self.recording:
            self.capture.stop()
        self._invalidate()
        self.jobs.shutdown()
        self._save()
        self.store.close()
