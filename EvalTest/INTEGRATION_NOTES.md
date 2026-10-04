# Integration notes for the other files

Our side: `confidence.py`, `question_controller.py`, `apprentice_bridge.py` (+ tests).
Copy the three modules into the app as a package, e.g. `apprentice/asking/` (imports work as a package or as loose files).
Everything below is a change **for the file's owner**. Nothing here is required for a first smoke test except
patches 1-5; the observer changes (section B) make the questions much better.

All times passed to the engine are the **session clock** (`self.session.duration`), not `time.monotonic()`.

---

## A. `controller.py`

The old flow was: observer proposes a question -> `QuestionPolicy` picks one -> `_ask`.
The new flow: observer proposes only *events* -> `QuestionEngine` decides whether/when/what -> `_ask`.
Question wording now comes from the 26-question library, never from the vision model.

**1. Create the engine (replaces `QuestionPolicy`).**
```python
from apprentice.asking.apprentice_bridge import QuestionEngine
# __init__:      self.qe = QuestionEngine()          # instead of self.policy = QuestionPolicy()
# _reset_observation():   self.qe = QuestionEngine() # instead of self.policy = QuestionPolicy()
# _begin_recording(): after self.recording = True, only when not teaching:  self.qe.begin_capture()
```

**2. Feed observations in (`analyzeLatest` -> `received`).** Pass only the observations actually appended.
```python
def received(actions):
    self.last_analyzed_ids.update(e.id for e in screens)
    summaries = {o.summary.casefold() for o in self.session.observations}
    new = [a for a in actions if a.summary.casefold() not in summaries]
    self.session.observations.extend(new)
    times = {e.id: e.timestamp for e in self.session.evidence}
    self.qe.on_observations(new, self.session.duration, times)
    ...
```

**3. Replace the ask block in `_tick`.** Delete the `self.policy.eligible(...)` / `choose(...)` block and use:
```python
if self.prompts and not self.pending_question:
    plan = self.qe.poll(
        self.session.duration,
        input_idle_s=idle_seconds(),                 # real OS input idle (desktop only)
        screen_stable_s=now - self.last_change,
        user_speaking=self.audio.listening,
        agent_speaking=self.audio.speaking or "speak" in self.jobs.active,
        paused=self.paused, off_record=self.off_record)
    if plan:
        self._ask(plan.text, plan.evidence_ids)
```
(`plan.text` already carries a "Going back to inv-4471 (cost_center):" lead-in when the case is no longer on screen.)

**4. Route every saved expert note/answer (`addNote`).** Right after `self.session.evidence.append(e)`:
```python
answering = bool(self.pending_question)
if not self.teaching:
    self.qe.on_note(e.text, self.session.duration, e.id, answering)   # e.id = utterance id (provenance + revocation)
```
Then at the very end of `addNote`, so the debrief proceeds one question at a time:
```python
if self.qe.in_debrief and not self.recording:
    QTimer.singleShot(1500, self._ask_next_debrief)
```

**5. Defer / cancel.**
```python
# deferQuestion(): first line  ->  self.qe.on_defer()        # question returns in the debrief only
# offRecord():     after clearing pending_question  ->  self.qe.release_active()
```

**6. Debrief without an LLM-written question** (`debrief()` slot). Replace the `interviewer.debrief` branch:
```python
self.session.phase = "debrief"
if self.session.mode == "demo": ...            # unchanged
self.qe.begin_debrief(self.session.duration)
self._ask_next_debrief()

def _ask_next_debrief(self):
    plan = self.qe.poll(self.session.duration, input_idle_s=999, screen_stable_s=999,
                        user_speaking=self.audio.listening,
                        agent_speaking=self.audio.speaking or "speak" in self.jobs.active)
    if plan:
        self._ask(plan.text, plan.evidence_ids)
    else:
        done = self.qe.status()["debrief"]["complete"]
        self._notify("Debrief complete. Build the Work Map." if done else
                     "No further question right now. Build the map; open gaps stay listed.")
```
(No cloud is needed for the debrief any more. `Interviewer` can stay for free-form use.)

**7. Keep the engine's gap tracking in sync with the Work Map.**
```python
# buildMap -> received:         after self.session.knowledge = items   ->  self.qe.sync_knowledge(items, self.session.evidence)
# confirmMap:                   after statuses set to "verified"       ->  self.qe.sync_knowledge(active, self.session.evidence)
# editKnowledge / rejectKnowledge: after saving                         ->  self.qe.sync_knowledge(self.session.knowledge, self.session.evidence)
```
Model-inferred text does NOT close a gap; only verified items or items backed by an answer/note do.

**8. Deleting evidence (`forgetEvidence`).** Before `forget(self.session, evidence_id)`:
```python
self.qe.revoke_evidence(evidence_id)    # cancels related questions, marks derived records revoked
self.qe.release_active()
```

**9. Ready button (explicit permission to ask).**
```python
@Slot()
def questionReady(self):
    if self.session: self.qe.signal_ready(self.session.duration)
```
Add a "Ready for a question" button to the minimized recording controls. Not mandatory on desktop (we have real
input idle), but it is the spec's fallback and useful for the demo.

**10. Show the reasoning (optional, great for the judges).** In the `state` property add:
```python
"questionStatus": self.qe.status(),     # queued items, debrief progress, acceptance checks
"questionTrace": self.qe.trace[-30:],   # why it asked / stayed quiet
```

**11. Tutor (optional).** In `_watch_trainee.received`, when `result.verdict == "warn"`, use the spec's wording:
```python
k = next((k for k in snapshot.knowledge if k.id in result.knowledge_ids), None)
plan = self.qe.intervention(k, paused=self.paused, off_record=self.off_record) if k else None
text = plan.text if plan else result.explanation
```

**12. Restoring a session (`openSession`).** Engine state is in memory. To rebuild it:
```python
self.qe = QuestionEngine()
times = {e.id: e.timestamp for e in session.evidence}
self.qe.on_observations(session.observations, session.duration, times)
```

## B. Observer prompt + `domain.py` (biggest quality gain)

Today the vision model writes the question and 0..3 scores. We want it to report **events only** and never guess intent.
The bridge reads the new fields if present and falls back to regex on `summary` if not, so this can land any time.

**`SeenAction`** (provider contract; keep every field required for strict structured output):
```python
event_type: Literal["field_changed","record_opened","records_compared","case_held","action_reversed",
                    "dependency_step","step_completed","navigation","other"]
case_id: str                       # visible invoice/ticket number, "" if none
field_name: str                    # e.g. "cost_center", "" if none
before: str
after: str
before_readable: bool
after_readable: bool
before_was_default: bool           # earlier value looks system pre-filled, not typed
fields_answered_on_screen: list[Literal["reason","guardrail","escalation_authority","threshold","exception"]]
confidence: float = Field(ge=0, le=1)
# remove: question, novelty, ambiguity, significance, guardrail
```
**`Observation`**: add the same fields **with defaults**, and keep `question/novelty/ambiguity/significance/guardrail`
with their defaults so previously saved sessions still load (`extra="forbid"` would otherwise reject them).

**`Observer.run` prompt** (replaces the current string; keep everything else in the method):
```
Compare these chronological screenshots. Return at most three NEW meaningful actions, excluding the
recorder's own UI and duplicates of recent observations. Empty actions is valid. Describe only visible state
changes, never imagined clicks, and never infer why the user acted.
For each action set event_type: field_changed, record_opened, records_compared, case_held, action_reversed,
dependency_step, step_completed, navigation, or other. Copy case_id (the visible invoice or ticket number),
field_name, before and after exactly as displayed; set before_readable/after_readable to false if a value is
blurry or cut off. Set before_was_default to true only if the earlier value looks pre-filled by the system
rather than typed by the user. List in fields_answered_on_screen any of reason, guardrail,
escalation_authority, threshold, exception that the screen itself already states (for example a hold banner
naming the missing document). confidence is 0..1: how sure you are of the event type and the values.
```
Also add to `context_for(session)` the known `case_id`s so the model reuses the same identifiers.

## C. `scoring.py`
`QuestionPolicy`, `question_score` and `choose` are no longer called. Leave them or delete them.
`completeness()` stays: it is an honest coverage metric for the UI. Debrief completion is decided by
`qe.status()["debrief"]` (>=3 follow-ups answered, no open critical gap, contradictions resolved), not by a percentage.

## D. Things to decide (we implemented the spec defaults)
* Cooldown 45 s / 5 questions per 10 min (spec) vs 90 s / 3 (current `QuestionPolicy`). One line in `TimingConfig`.
* Step boundary = the expert moved on (navigation/next case) or pressed Ready. Idle-only boundary is available
  (`EngineConfig(allow_idle_boundary=True)`) but the spec says silence alone is not evidence the expert is available.
* Observer latency: batched analysis is slow, so staleness limit is 20 s (`EngineConfig.max_vision_latency_s`).
* Voice: the app already speaks questions with ElevenLabs TTS and transcribes answers separately, so timing stays
  fully under our control. The challenge brief asks for an ElevenAgents voice agent; if judges expect that
  specifically, the same `Plan.text` can be spoken by an agent (see the earlier discussion), the controller does not change.

## E. If the team moves to a web app
`QuestionEngine` has no Qt/pydantic dependency. Wrap it in a small server:
`POST /observations` -> `on_observations` (wrap each vision JSON dict as `SimpleNamespace(id=..., evidence_ids=[...], **fields)`;
the bridge reads attributes by name), `POST /note` -> `on_note`, `POST /poll` -> `poll` (browser can't read global input idle, so send
`input_idle_s` from the bubble's own text box and rely on Ready + step boundary), `POST /finish` -> `begin_debrief`.
