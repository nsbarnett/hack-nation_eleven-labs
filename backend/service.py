"""Single async state owner; AI workers operate on snapshots and never write state.

Generation counters invalidate pending responses after privacy/session changes.
SQLite and images use the repository worker, keeping the API event loop responsive.
"""
import asyncio
import base64
import io
import inspect
import time
from dataclasses import replace
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from apprentice.agents.gateway import Gateway
from apprentice.agents.observer import Observer
from apprentice.agents.interviewer import Interviewer
from apprentice.agents.assessor import Assessor
from apprentice.agents.knowledge import KnowledgeBuilder
from apprentice.agents.tutor import Tutor
from apprentice.domain import Session, Evidence, Message, Knowledge, GapReview, new_id
from apprentice.evidence import forget, require_sources
from apprentice import evaluation
from apprentice.exporting import export_session
from backend.repository import Repository
from backend.voice import ElevenVoice
from backend.training import generate, evaluate_exercise


class Service:
    def __init__(self, root, settings, *, repository=None, work_runner=None):
        self.repo = repository or Repository(root)
        self.work_runner = work_runner or (lambda role, work: asyncio.to_thread(work))
        self.settings = settings
        self.session = None
        self.generation = 0
        self.sequence = 0
        self.epoch = new_id()
        self.cloud = False
        self.recording = "idle"
        self.assistant = "idle"
        self.question = None
        self.practice = {"items": [], "answers": {}}
        self.jobs = set()
        self.tasks = set()
        self.listeners = set()
        self.previous_image = None
        self.stable_since = time.monotonic()
        self.last_analysis = 0
        self.coaching = False
        self.observed_at = {}
        self.lock = asyncio.Lock()

    async def snapshot(self):
        assessment = evaluation.summary(self.session) if self.session else None
        return {"session": self.session.model_dump() if self.session else None,
                "sessions": await self.repo.list(), "cloud": self.cloud,
                "recording": self.recording, "assistant": self.assistant,
                "question": self.question, "practice": self.practice, "coaching": self.coaching,
                "credentials": {"openai": bool(self.settings.openai_key), "elevenlabs": bool(self.settings.eleven_key),
                                "voiceId": self.settings.voice_id, "model": self.settings.model},
                "sequence": self.sequence, "epoch": self.epoch, "busy": sorted(self.jobs), "evaluation": assessment}

    async def emit(self, kind="state", **data):
        self.sequence += 1
        event = {"type": kind, "sequence": self.sequence,
                 "sessionId": self.session.id if self.session else None,
                 "revision": self.session.revision if self.session else 0, **data}
        for queue in list(self.listeners):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    async def persist(self):
        if self.session:
            evaluation.refresh(self.session)
            self.session.revision += 1
            await self.repo.save(self.session)
        await self.emit()

    def invalidate(self, *, preserve_question=False):
        self.generation += 1
        if self.session and not preserve_question:
            for attempt in self.session.evaluation.attempts:
                if attempt.state == "asking":
                    attempt.state = "cancelled"
        self.question = None
        self.assistant = "idle"
        self.repo.clear_media_cache()

    def require_session(self):
        if not self.session:
            raise ValueError("Create or open a workflow first.")
        return self.session

    async def launch(self, role, work, apply):
        if not self.cloud or not self.settings.openai_key:
            raise ValueError("Enable cloud analysis and configure OpenAI in Settings first.")
        if role in self.jobs or len(self.jobs) >= 3:
            raise ValueError("This assistant task is already running. Please wait.")
        evaluation_roles = {"knowledge", "interviewer", "observer"}
        if role in evaluation_roles and self.jobs & evaluation_roles:
            raise ValueError("Wait for the current evidence evaluation to finish.")
        generation = self.generation
        self.jobs.add(role)
        self.assistant = "thinking"
        await self.emit()

        async def run():
            try:
                async def invoke(step, callback):
                    if generation != self.generation:
                        raise asyncio.CancelledError()
                    return await self.work_runner(step, callback)
                # Each stage goes through the hosted quota runner separately.
                result = await work(invoke) if inspect.iscoroutinefunction(work) else await invoke(role, work)
                async with self.lock:
                    if generation == self.generation:
                        apply(result)
                        if self.question:
                            self.assistant = "question"
                        elif self.assistant == "thinking":
                            self.assistant = "watching" if self.recording == "recording" else "idle"
                        await self.persist()
            except Exception as error:
                if generation == self.generation:
                    # Provider exceptions can include request headers or sensitive content.
                    message = str(error) if isinstance(error, ValueError) else "The AI request failed. Check your connection and credentials, then retry."
                    await self.emit("error", message=message)
            finally:
                self.jobs.discard(role)
                if generation == self.generation and self.assistant == "thinking":
                    self.assistant = "watching" if self.recording == "recording" else "idle"
                await self.emit()
        task = asyncio.create_task(run())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def command(self, name, data):
        async with self.lock:
            return await self._command(name, data)

    async def _command(self, name, data):
        if name == "credentials":
            self.invalidate()
            allowed = {k: str(v) for k, v in data.items() if k in {"openai_key", "eleven_key", "voice_id", "model"}}
            self.settings = replace(self.settings, **allowed)
            await self.emit()
            return {}
        if name == "new":
            if self.recording != "idle":
                raise ValueError("Stop recording before starting another workflow.")
            title = str(data.get("title", "")).strip()
            if not title or len(title) > 200:
                raise ValueError("Give this workflow a title of 1–200 characters.")
            self.invalidate()
            self.session = Session(title=title, context=str(data.get("context", ""))[:12000])
            self.cloud = bool(data.get("cloud", False))
            self.practice = {"items": [], "answers": {}}
            self.observed_at = {}
            self.previous_image = None
            self.coaching = False
        elif name == "open":
            if self.recording != "idle":
                raise ValueError("Stop recording before opening another workflow.")
            loaded = await self.repo.load(data["id"])
            self.invalidate()
            self.session = loaded
            self.cloud = False
            self.coaching = False
            self.practice = {"items": [], "answers": {}}
            self.observed_at = {}
            self.restore_question()
        elif name == "cloud":
            self.cloud = bool(data["enabled"])
            if not self.cloud:
                self.invalidate()
        elif name == "recording":
            session = self.require_session()
            state = data["state"]
            if state not in {"idle", "paused", "recording"}:
                raise ValueError("Invalid recording state.")
            self.recording = state
            session.duration = max(session.duration, float(data.get("duration", session.duration)))
            self.invalidate()
            self.previous_image = None
            self.stable_since = time.monotonic()
            self.assistant = "watching" if state == "recording" and self.cloud else "idle"
        elif name == "segment":
            session = self.require_session()
            filename = data["filename"]
            if not filename.endswith(".webm") or "/" in filename or "\\" in filename:
                raise ValueError("Invalid recording filename.")
            if not await self.repo.has_recording(session.id, filename):
                raise ValueError("Recording file is missing.")
            if filename not in session.recordings:
                session.recordings.append(filename)
        elif name == "note":
            session = self.require_session()
            text = str(data.get("text", "")).strip()[:12000]
            if not text:
                raise ValueError("Enter a note or answer.")
            if self.recording == "paused":
                raise ValueError("Resume recording before adding evidence.")
            kind = data.get("kind", "note")
            if kind not in {"note", "reference", "answer", "trainee_note"}:
                raise ValueError("Invalid note type.")
            question = self.question
            if self.coaching:
                kind = "trainee_note"
            evidence = Evidence(kind=kind, text=text, timestamp=session.duration,
                                question=question["text"] if question else "",
                                related_ids=question["evidence_ids"] if question else [],
                                gap_id=question.get("gap_id", "") if question and not self.coaching and kind != "reference" else "")
            session.evidence.append(evidence)
            session.messages.append(Message(role="user", text=text, evidence_ids=[evidence.id]))
            if evidence.gap_id:
                for attempt in session.evaluation.attempts:
                    if attempt.id == question["id"]:
                        attempt.state, attempt.answer_id = "answered", evidence.id
                evaluation.trace(session, "ANSWER_SAVED", "Answer saved; sufficiency has not yet been assessed.", evidence.gap_id)
            self.invalidate()
            if not kind.startswith("trainee"):
                session.confirmed = False
                self.practice = {"items": [], "answers": {}}
                # A new statement may change applicability or contradict a compiled rule.
                # Unprompted text has no reliable dependency scope, so invalidate conservatively.
                for item in session.knowledge:
                    if item.status != "rejected":
                        item.status = "needs_clarification"
                        item.check, item.check_verified = None, False
        elif name == "defer":
            for attempt in self.require_session().evaluation.attempts:
                if attempt.state == "asking":
                    attempt.state = "deferred"
                    evaluation.trace(self.session, "DEFER", "Question retained for debrief.", attempt.gap_id)
            self.invalidate()
        elif name == "question-ready":
            session = self.require_session()
            if self.recording != "recording" or self.question or self.jobs:
                raise ValueError("Wait until recording is active and the assistant is available.")
            asked = [a.timestamp for a in session.evaluation.attempts if a.phase == "live"]
            if ((asked and session.duration - max(asked) < evaluation.CONFIG.live_cooldown_s)
                    or sum(session.duration - t < 600 for t in asked) >= evaluation.CONFIG.live_budget_per_10min):
                raise ValueError("The live question cooldown or budget is still active. Continue in Debrief after recording.")
            gap = evaluation.next_gap(session, "live")
            if gap:
                sources = evaluation.expert_sources(session)
                age = session.duration - max(sources[i].timestamp for i in gap.evidence_ids)
                if age <= evaluation.CONFIG.max_live_evidence_age_s:
                    self.ask_evaluated(gap, phase="live")
        elif name == "review-gap":
            session = self.require_session()
            if self.recording != "idle":
                raise ValueError("Stop recording before reviewing knowledge gaps.")
            evaluation.refresh(session)
            gap = next((g for g in session.evaluation.gaps if g.id == data.get("id")), None)
            text = str(data.get("text", "")).strip()[:12000]
            outcome = data.get("outcome", "verified")
            if not gap or not evaluation.established(text) or evaluation.UNCERTAIN.search(text) or outcome not in {"verified", "not_applicable"}:
                raise ValueError("Provide an explicit expert clarification or explain why this field does not apply.")
            evidence = Evidence(kind="answer", text=text, gap_id=gap.id, timestamp=session.duration,
                                question=evaluation.question_for(session, gap), related_ids=gap.evidence_ids)
            session.evidence.append(evidence)
            session.evaluation.reviews.append(GapReview(gap_id=gap.id, evidence_id=evidence.id, outcome=outcome))
            session.evaluation.assessed_evidence_ids.append(evidence.id)
            session.messages.append(Message(role="user", text=text, evidence_ids=[evidence.id]))
            session.confirmed = False
            self.practice = {"items": [], "answers": {}}
            for item in session.knowledge:
                if gap.decision_id in item.decision_ids and item.status != "rejected":
                    item.status = "needs_clarification"
                    item.check, item.check_verified = None, False
            self.invalidate()
        elif name == "build-map":
            evaluation.refresh(self.require_session())
            session = self.require_session().model_copy(deep=True)
            if not session.evidence:
                raise ValueError("Record or add expert notes before building a Work Map.")
            def apply(result):
                assessed, (items, teach_back, gaps) = result
                self.session.evaluation = assessed
                self.session.knowledge = items
                self.session.confirmed = False
                self.session.phase = "review"
                self.practice = {"items": [], "answers": {}}
                self.session.messages.append(Message(role="assistant", text=teach_back + ("\n\nUnresolved: " + "; ".join(gaps) if gaps else "")))
            async def build(run):
                if evaluation.pending_sources(session):
                    session.evaluation = await run("assessment", lambda: Assessor(Gateway(self.settings)).run(session))
                evaluation.refresh(session)
                result = await run("knowledge", lambda: KnowledgeBuilder(Gateway(self.settings)).run(session))
                return session.evaluation, result
            await self.launch("knowledge", build, apply)
            return {}
        elif name == "debrief":
            if self.question:
                return {}
            evaluation.refresh(self.require_session())
            session = self.require_session().model_copy(deep=True)
            self.session.phase = "debrief"
            def apply(result):
                assessed, gap_id, wording = result
                self.session.evaluation = assessed
                gap = next((g for g in assessed.gaps if g.id == gap_id), None)
                if gap:
                    self.ask_evaluated(gap, text=wording)
                else:
                    complete = evaluation.summary(self.session)["debrief_complete"]
                    self.session.messages.append(Message(role="assistant", text="No unresolved applicable gaps remain. Review your Work Map before teaching." if complete else "Evidence still needs assessment. Open gaps remain listed."))
            async def debrief(run):
                if evaluation.pending_sources(session):
                    session.evaluation = await run("assessment", lambda: Assessor(Gateway(self.settings)).run(session))
                gap = evaluation.next_gap(session)
                wording = None
                # Fixed questions cover specific fields. Contextualize only broad rule gaps.
                if gap and gap.field == "rule":
                    result = await run("interviewer", lambda: Interviewer(Gateway(self.settings)).debrief(session, gap))
                    wording = result.question
                return session.evaluation, gap.id if gap else None, wording
            gap = evaluation.next_gap(session)
            if not evaluation.pending_sources(session) and (not gap or gap.field != "rule"):
                apply((session.evaluation, gap.id if gap else None, None))
                await self.persist()
                return {}
            await self.launch("interviewer", debrief, apply)
            return {}
        elif name == "edit-knowledge":
            session = self.require_session()
            current = next(k for k in session.knowledge if k.id == data["id"])
            patch = data["patch"]
            allowed = {"title", "action", "decision", "reason", "rule", "exception", "guardrail", "escalation", "status", "check_verified"}
            if not set(patch) <= allowed:
                raise ValueError("Unsupported knowledge fields.")
            updated = Knowledge.model_validate({**current.model_dump(), **patch})
            changed = any(getattr(current, key) != value for key, value in patch.items() if key not in {"status", "check_verified"})
            if changed:
                updated.check, updated.check_verified = None, False
                if "status" not in patch:
                    updated.status = "needs_clarification"
            if updated.status != "verified":
                updated.check_verified = False
            if updated.check_verified and updated.check is None:
                raise ValueError("There is no executable check to verify. Rebuild the map after editing its rule.")
            if updated.status == "verified":
                require_sources(updated.evidence_ids, {e.id for e in session.evidence if not e.kind.startswith("trainee")})
                session.evaluation.assessed_evidence_ids = list(dict.fromkeys(session.evaluation.assessed_evidence_ids + updated.evidence_ids))
            session.knowledge[session.knowledge.index(current)] = updated
            session.confirmed = False
            self.invalidate()
            self.practice = {"items": [], "answers": {}}
        elif name == "confirm":
            session = self.require_session()
            active = [k for k in session.knowledge if k.status != "rejected"]
            if not active or any(k.status != "verified" for k in active):
                raise ValueError("Review and verify every retained step before confirming the map.")
            for item in active:
                require_sources(item.evidence_ids, {e.id for e in session.evidence if not e.kind.startswith("trainee")})
            report = evaluation.summary(session)
            active_decisions = {d for item in active for d in item.decision_ids}
            blockers = [g for g in session.evaluation.gaps if g.decision_id in active_decisions
                        and (g.status == "disputed" or (g.status in evaluation.OPEN and evaluation.PRIORITY[g.field] == 0))]
            if blockers:
                raise ValueError("Resolve the retained map's critical gaps and contradictions before confirming it.")
            if report["dimensions"]["answer_sufficiency"]["pending_evidence"]:
                raise ValueError("Assess new expert evidence in Debrief or rebuild the map before confirming it.")
            session.confirmed = True
            self.invalidate()
        elif name == "forget":
            session = self.require_session()
            if self.recording != "idle":
                raise ValueError("Stop recording before forgetting evidence.")
            self.invalidate()
            before = list(session.evidence)
            removed = forget(session, data["id"])
            paths = [e.image for e in before if e.id in removed and e.image] + session.recordings
            await self.repo.remove_media(session.id, paths)
            session.recordings = []
            self.practice = {"items": [], "answers": {}}
        elif name == "practice":
            session = self.require_session().model_copy(deep=True)
            def apply(result):
                self.practice = {**result, "answers": {}}
            await self.launch("practice", lambda: generate(Gateway(self.settings), session), apply)
            return {}
        elif name == "tutor":
            session = self.require_session().model_copy(deep=True)
            if not session.confirmed:
                raise ValueError("Confirm a Work Map before teaching.")
            text = str(data.get("text", ""))[:12000]
            index = data.get("index")
            if index is not None:
                index = int(index)
                if not 0 <= index < len(self.practice["items"]):
                    raise ValueError("Exercise no longer exists.")
                prompt = self.practice["items"][index]["question"] + "\nTrainee answer: " + text
            else:
                prompt = text
            def apply(result):
                self.session.evidence.append(Evidence(kind="trainee_attempt", text=text, question=prompt))
                self.session.messages.extend([Message(role="user", text=text), Message(role="assistant", text=result.verdict.upper() + ": " + result.explanation)])
                if index is not None:
                    self.practice["answers"][str(index)] = result.model_dump()
            if index is not None and self.practice["items"][index].get("answer_fields"):
                result = evaluate_exercise(session, self.practice["items"][index], data.get("values", {}))
                text = "\n".join(f"{field}: {value if value is not None else '[absent]'}" for field, value in data.get("values", {}).items())
                apply(result)
                await self.persist()
                return {}
            await self.launch("tutor", lambda: Tutor(Gateway(self.settings)).explain(session, prompt), apply)
            return {}
        elif name == "coaching":
            if data["enabled"] and not self.require_session().confirmed:
                raise ValueError("Confirm a Work Map before live coaching.")
            self.coaching = bool(data["enabled"])
            self.invalidate()
        else:
            raise ValueError("Unknown command.")
        await self.persist()
        return {}

    def ask(self, text, evidence_ids):
        self.question = {"id": new_id(), "text": text, "evidence_ids": evidence_ids}
        self.session.messages.append(Message(role="assistant", text=text, evidence_ids=evidence_ids))
        self.assistant = "question"

    def ask_evaluated(self, gap, *, phase="debrief", text=None):
        attempt = evaluation.ask_gap(self.session, gap, phase, text)
        self.question = {"id": attempt.id, "text": attempt.text, "evidence_ids": attempt.evidence_ids, "gap_id": attempt.gap_id}
        self.session.messages.append(Message(role="assistant", text=attempt.text, evidence_ids=attempt.evidence_ids))
        self.assistant = "question"

    def restore_question(self):
        evaluation.refresh(self.session)
        attempt = next((a for a in self.session.evaluation.attempts if a.state == "asking"), None)
        if attempt:
            self.question = {"id": attempt.id, "text": attempt.text, "evidence_ids": attempt.evidence_ids, "gap_id": attempt.gap_id}
            self.assistant = "question"

    async def frame(self, payload, duration, idle, evidence_id=None):
        async with self.lock:
            if self.recording != "recording":
                return
            session = self.require_session()
            session.duration = max(session.duration, duration)
            def decode():
                image = Image.open(io.BytesIO(payload))
                if image.width * image.height > 16_000_000:
                    raise ValueError("Screen image is too large.")
                image.thumbnail((1280, 900))
                image = image.convert("RGB")
                thumb = image.resize((32, 24))
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=75)
                return thumb, output.getvalue()
            thumb, jpeg = await self.repo.call(decode)
            now = time.monotonic()
            if self.previous_image is None or sum(ImageStat.Stat(ImageChops.difference(thumb, self.previous_image)).mean) / 3 > 5:
                self.stable_since = now
            self.previous_image = thumb
            evidence = Evidence(kind="trainee_screen" if self.coaching else "screen", timestamp=duration)
            if evidence_id is not None:
                evidence.id = evidence_id
            evidence.image = evidence.id + ".jpg"
            await self.repo.save_frame(session.id, evidence.image, jpeg)
            session.evidence.append(evidence)
            if self.cloud and self.settings.openai_key:
                if now - self.last_analysis >= self.settings.analysis_seconds and not self.jobs:
                    self.last_analysis = now
                    snapshot = session.model_copy(deep=True)
                    images = await self.repo.images(session, evidence.kind)
                    if self.coaching:
                        def apply(result):
                            if result.verdict == "warn":
                                self.session.messages.append(Message(role="assistant", text=result.explanation))
                        await self.launch("coach", lambda: Tutor(Gateway(self.settings)).observe(snapshot, images), apply)
                    else:
                        def apply_observations(result):
                            self.session.observations.extend(result)
                            self.observed_at.update({item.id: time.monotonic() for item in result})
                            if result:
                                self.assistant = "detected"
                        await self.launch("observer", lambda: Observer(Gateway(self.settings)).run(snapshot, images), apply_observations)
                # Automatic silence-based interruptions are intentionally disabled.
                # The desktop Ready button explicitly requests a supported gap.
                if not self.coaching and not self.question and evaluation.next_gap(session, "live"):
                    self.assistant = "waiting"
            await self.persist()

    async def close(self):
        self.invalidate()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.repo.close()
