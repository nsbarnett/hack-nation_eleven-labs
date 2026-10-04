# User guide

## Browser edition 0.4.0

The current path is Record → Privacy Review → Approve → Analyze → Work Map → Teach. Record normally; local OCR suggests sensitive moments after/during capture. In Privacy Review, choose a segment, seek to a marker, accept/dismiss it, or draw your own solid cover. Edit each cover's start/end times. Moving/resizing at another time adds a position keyframe; split covers at screen cuts. The numeric percentage fields also provide keyboard editing.

Render the separate redacted copy, preview it, acknowledge reviewing all segments/gaps, then approve. No findings still requires approval. With cloud analysis enabled, Analyze approved frames sends selected redacted images and allows screen-based questions. Recording/manual notes require no provider keys. Notes and explicit voice answers are disclosed separately from visual redaction.

Library playback/download uses the approved copy. To edit an original, return to Privacy Review; edits revoke approval and rebuild screen-derived knowledge after another approval. Originals are retained until you explicitly delete them. If a scan fails, review its gaps manually or rerun it. Failed rendering never falls back to raw exports.

To delete the open workflow and its data, stop recording and choose **Settings → Delete open workflow & media**. Review the workflow name, type `confirm delete` exactly, then choose **Delete permanently**. Cancel keeps the workflow and media; reopening the dialog requires typing the phrase again.

Install the optional orb through Settings using [these steps](EXTENSION.md). Keep the app tab open. See [privacy limits](PRIVACY.md). The remainder of this guide describes the older Electron backup; desktop import and live-screen coaching are not browser controls.

## Start with your own work

The application starts empty. Home offers recording, saved workflows and teaching. No sample names, example business processes or prefilled exercises are installed. To bring work from the old Qt application, use Settings > Import legacy recordings and select the folder containing apprentice.sqlite3. Live sessions are copied without changing originals; demo sessions and duplicates are skipped.

## Recording

Give the workflow a title, optionally explain your intent, select a real screen/window, and choose whether to enable cloud analysis. Without cloud analysis the application records locally and accepts typed notes. A full-display preview is intentionally hidden while the app is visible to avoid a recursive screen mirror; a selected external-window preview can remain visible.

Pause stops screen and microphone tracks, rather than merely hiding activity. Resume starts a separate video segment. Stop saves the final segment. Navigating between pages or minimizing the main window does not stop recording. Closing the application flushes recording before exit.

The floating orb is an independent desktop window. Drag it by the orb; click to expand/collapse the toolbar. Actions are Record/Stop, Context, Voice, Mute/Unmute and Open App. Hover for labels. Ctrl+Shift+Space on Windows or Cmd+Shift+Space on macOS focuses the orb for keyboard navigation. Voice can be finished by clicking it again; microphone capture is capped at 30 seconds.

## Questions and voice

The observer can propose questions only from actual evidence. The scheduler waits for eight seconds without input and a stable screen, with rate limits. It cannot infer that you are reading or talking while the microphone is off. Old observation questions expire rather than being delivered long after their context.

Spoken questions start muted. Unmuting enables ElevenLabs speech, but never opens the microphone automatically. Choose Voice/Answer to record an answer, or type in the conversation field. Voice requires an ElevenLabs key. Missing keys and provider failures produce messages rather than simulated speech or transcripts. Defer dismisses a question. Muting cancels queued/playing speech and any in-progress microphone answer.

## Work Maps and debrief

Open a workflow and enable cloud analysis if it is off. Build from evidence produces a draft. Each retained step includes action, decision, reason, rule, exception, guardrail, escalation and source links. Review a step, correct it against the evidence, and mark it verified. Resolve or reject unclear/conflicting steps. Only then confirm the whole map.

Debrief requests one useful gap-closing question at a time. There is no fictional question count. The model may report no further supported questions. More expert notes or changes to a step revoke confirmation until reviewed again.

## Teach Mode

Choose a confirmed workflow. Guided practice generates clearly labeled hypothetical questions based on its verified steps. Submit a written answer for advisory feedback; the counter measures answered exercises, not certified proficiency. If evidence cannot support a question, none is invented.

Live coaching observes the screen/window you explicitly select. Advice is grounded in the confirmed map, does not control another app, and cannot prevent a save. Trainee screenshots and attempts are kept distinct from expert evidence and are never silently promoted into policy. New edge cases require an expert to update the map.

## Library, exports and deletion

Library shows the current workflow's notes, reference text, screenshots and recordings. Videos open with your system video player. Export produces Markdown with assets, JSON, and a standalone HTML Work Map in a destination you select.

Forgetting evidence requires a native confirmation. It removes dependent answers, all derived observations/knowledge, and all raw videos for that session because forgotten content can remain in those videos. Stop recording before forgetting evidence. Exported or shared copies cannot be recalled.

## Privacy and setup

Settings stores credentials with OS-backed encryption. Connection checks contact the selected provider. Development .env keys are supported; installed builds do not include .env. Screen and microphone permissions belong to the operating system. System audio is not captured. There is no automatic sensitive-data redaction; choose your source and cloud setting appropriately.
