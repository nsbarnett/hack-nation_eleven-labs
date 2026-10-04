# Architecture and file guide

## Hosted browser architecture

The supported browser entry point is `backend/web.py`. It serves React through `app/src/web/bridge.ts`, with guest-scoped PostgreSQL text and browser IndexedDB media. The Electron backup retains its earlier capture path. See [hosted setup](REPLIT.md), [privacy contracts](PRIVACY.md), and [extension setup](EXTENSION.md).

### Browser privacy modules (0.4.0)

| Module | Responsibility |
| --- | --- |
| `app/src/privacy/types.ts` | Normalized regions, timed segments, local markers/keyframes, approval revision and derivative identity. |
| `app/src/privacy/detect.ts` | Deterministic local pattern suggestions; returns categories/bounds without recognized text. |
| `app/src/privacy/geometry.ts` | Region clamping, keyframe interpolation, cut validation and opaque pixel painting. |
| `app/src/privacy/processor.worker.ts` | Sequential local decode/OCR, scene comparisons, sampled progress, WebCodecs encoding with Mediabunny, and JPEG extraction from rendered copies. |
| `app/src/privacy/service.ts` | Bounded jobs independent of navigation; serialized draft writes, editing/invalidation, quota checks, cancellation, rendering, approval and revision-bound uploads. |
| `app/src/pages/PrivacyReview.tsx` | Labeled original editor, segment/timeline/finding controls, cover editing/keyframes/splits, render preview and explicit approval. |
| `app/src/web/localMedia.ts` | IndexedDB v2 migration, chunk backpressure, separate source/derivative budgets and persistent review drafts. |
| `app/src/web/bridge.ts` | No live screen uploads; guarded approved playback/download and typed reviewed-frame requests. |
| `backend/hosted_service.py` | Idle-session/revision approval checks; cancellation and invalidation of screen-derived state; actual post-record observation/questions. |
| `app/extension/protocol.ts` | Validated, bounded command/snapshot contracts shared with the app. |
| `app/extension/background.ts` | Single app connection, exact configured origin, deduplication, snapshot fanout and tab reuse. |
| `app/extension/content.ts` | Isolated relay on the app origin; stable bounded iframe geometry on other permitted pages; click-through and drag handoff. |
| `app/extension/surface.ts` | Permanently mounted orb/controls, accessible tooltips, keyboard actions and synchronized real state. |
| `app/extension/options.ts` | Exact-origin configuration and optional website permission request. |
| `app/src/web/extensionBridge.ts` | Revalidates command/session/question identity; dispatches only explicit app capabilities. |
| `app/scripts/build-companion.mjs` | Packages the unpacked extension, ZIP/download endpoint, local OCR worker/WASM/language assets and notices. |

Capture bytes never enter Zustand or extension messages. Original video is reachable only from the local editor. Derived video is encoded into new pixels before approval; selected cloud frames are decoded from that derivative. Committed edits invalidate the server generation and privacy revision so old jobs cannot repopulate screen knowledge. Explicit text/voice inputs retain their separate disclosure path.

The following sections describe the historical Electron edition.

## Authority and data flow

The desktop has three process boundaries: sandboxed React renderers, the privileged Electron main process, and a headless Python service. The main window and overlay use the same narrow preload API. Renderer code cannot access Node, provider keys, arbitrary files, or the backend token. Navigation and new windows are denied; production assets are local and protected by a Content Security Policy.

Electron launches Python with an ephemeral localhost port and a random per-launch token. Configuration arrives on stdin, not the command line. Main-process HTTP requests and WebSocket connections carry authentication. Provider keys are encrypted with Electron safeStorage and passed only to backend memory. The service binds to 127.0.0.1, not the network.

Session commands update one async state owner under a lock. A dedicated repository thread owns SQLite. Provider calls run as bounded background jobs on deep snapshots. A generation counter rejects results after session switches, privacy changes, or edits. WebSocket events carry sequence, session ID, and revision. Renderers reconcile current snapshots and reject older responses. Video frames and recording chunks are not Zustand state.

## Desktop files

| File / directory | Responsibility |
| --- | --- |
| `app/electron/main.ts` | Native window creation, validated IPC, permissions, capture source selection, recording file writes, import/export dialogs, shutdown, application-wide keyboard shortcut. |
| `app/electron/backend.ts` | Starts and monitors Python; authenticates service requests; forwards events and reconnects the WebSocket. |
| `app/electron/preload.ts` | Explicit renderer capabilities. No generic IPC or arbitrary path access. |
| `app/electron/credentials.ts` | Atomic encrypted credential persistence using the OS key store. |
| `app/electron/overlayWindow.ts` | Transparent always-on-top window and clamped display-coordinate geometry. |
| `app/src/main.tsx` | Renderer bootstrap, event subscription, snapshot synchronization, question-triggered speech. |
| `app/src/App.tsx` | Fixed navigation, native-window shell, page selection and overlay action routing. |
| `app/src/media.ts` | Persistent screen/microphone streams, MediaRecorder, bounded chunk writes, screenshot sampling, voice playback, pause/stop cleanup. |
| `app/src/stores.ts`, `types.ts` | Renderer state, asynchronous command/error handling, typed cross-process contracts. |
| `app/src/animations.ts`, `style.css` | Shared transitions, design tokens, layout, native-shell colors and reduced motion. |
| `app/src/components/Controls.tsx` | Shared accessible Radix dialogs, switches and tooltips; shadcn button wrapper. |
| `app/src/components/ui/button.tsx`, `lib/utils.ts` | Locally owned shadcn button source and class composition. |
| `app/src/components/VoiceOrb.tsx`, `FloatingAssistant.tsx` | Orb appearance, drag gestures, expanding toolbar, contextual question card. |
| `app/src/components/RecordingSetup.tsx` | Explicit source selection, session title/context and cloud consent. |
| `app/src/components/AssistantPanel.tsx` | Actual conversation history, typed notes, voice controls and assistant preferences. |
| `app/src/pages/Home.tsx` | Actions and recent persisted workflows; no seeded records. |
| `app/src/pages/Record.tsx` | Recording controls, safe preview and evidence-linked observation timeline. |
| `app/src/pages/Workflows.tsx` | Search and open saved sessions. |
| `app/src/pages/WorkMap.tsx` | Build, edit, verify, confirm and export knowledge; inspect source screenshots. |
| `app/src/pages/Debrief.tsx` | Request one evidence-grounded question at a time. |
| `app/src/pages/Teach.tsx` | Generated practice, advisory feedback and live coaching based on a confirmed map. |
| `app/src/pages/Library.tsx` | Notes, references, local screenshots, video opening and evidence exclusion. |
| `app/src/pages/Settings.tsx` | Credential setup/check/removal, model/voice selection and legacy import. |

## Python files

| File / directory | Responsibility |
| --- | --- |
| `backend/__main__.py` | Receives private startup configuration, binds a free localhost port, starts Uvicorn. |
| `backend/server.py` | Authenticated commands, state snapshots, frames, speech/transcription, export/import and event endpoints. |
| `backend/service.py` | Session owner, bounded AI jobs, question delivery, map review, coaching, stale-result rejection and privacy lifecycle. |
| `backend/repository.py` | Single SQLite worker, media operations and non-destructive legacy import. |
| `backend/voice.py` | Pure ElevenLabs HTTP adapter with no Qt/audio-device dependency. |
| `backend/training.py` | Structured, cited exercises derived from confirmed workflow knowledge. |
| `apprentice/domain.py` | Evidence, observations, knowledge and persisted session contracts. Version 1 remains readable; WebM paths use the existing recording-path field. |
| `apprentice/agents/gateway.py` | Structured OpenAI responses, bounded image inputs, untrusted-evidence boundary and provider timeouts. |
| `apprentice/agents/observer.py` | Identifies visible actions and useful uncertainties, with source validation. |
| `apprentice/agents/interviewer.py` | Resolves knowledge gaps one question at a time. |
| `apprentice/agents/knowledge.py` | Builds editable Work Maps without preset business-domain fields. |
| `apprentice/agents/tutor.py` | Advisory explanations and trainee observation using confirmed knowledge only. |
| `apprentice/context.py`, `evidence.py` | Bounded expert context, provenance validation and cascading evidence exclusion. |
| `apprentice/scoring.py`, `rules.py` | Deterministic question timing/scoring and inspectable rule evaluation. No generated executable code. |
| `apprentice/store.py`, `exporting.py`, `config.py` | SQLite snapshot format, session-owned paths, portable exports and development configuration. |

The old Qt application, controller, capture, audio device code, QML and demo modules remain in the repository solely for historical reference and regression tests. They are not imported by the Electron service and are excluded from its executable. `TrainingCase` remains a legacy contract; the new interface and teaching flow do not use the purchase form.

## Recording and overlay lifecycle

1. The user selects a real source and opts into cloud analysis if desired.
2. Electron permits the selected source; a persistent renderer service acquires the stream.
3. MediaRecorder produces WebM chunks. Electron writes them sequentially, acknowledging each write. A 32 MiB pending-data ceiling stops capture on storage backpressure.
4. Every two seconds, the service saves a resized JPEG. Cloud observation runs no more often than every ten seconds by default.
5. Question policy requires eight seconds of input inactivity, three seconds of screen stability, a ninety-second cooldown and at most three questions per ten minutes. Speaking/listening suppresses pause eligibility.
6. Pause stops camera-capture and microphone tracks and finalizes a segment. Resume starts a fresh segment. Stop flushes the final video chunk before closing the file.
7. The overlay resizes its native bounds before an expansion and shrinks after the exit animation. The orb stays anchored. Transparent areas explicitly pass pointer input through; keyboard focus is opt-in through Ctrl/Cmd+Shift+Space.

Whole-display previews are hidden to avoid recursion. Electron content protection is best effort; modern macOS screen-capture APIs may still capture the overlay. No cross-platform exclusion guarantee is made.

## Knowledge boundaries

Drafts cite retained expert evidence. Users review and verify every retained step before confirming a map. Additional expert context or edits revoke confirmation and invalidate affected executable checks. Trainee notes, screenshots and attempts do not enter expert context. Practice questions are explicitly hypothetical. Structured answers are graded with separately reviewed rule checks; written explanations receive advisory feedback. Unsupported or conflicting cases remain unknown. Forgetting evidence clears derived knowledge, evaluation state and observations, dependent answers and session videos. Exports are user-owned copies and cannot be recalled.

`Session.evaluation` persists decisions, field assessments, source-linked gaps, question attempts, expert reviews and decision traces. `apprentice/agents/assessor.py` proposes quoted assessments; `apprentice/evaluation.py` validates them and controls transitions. Debrief and Work Map display six independent evaluation dimensions. Full parameters, decision rationale and replay instructions are in [EVALUATION.md](EVALUATION.md).

## Build and validation support files

| File | Responsibility |
| --- | --- |
| `app/package.json`, `package-lock.json` | Desktop scripts, pinned dependency graph, installer metadata and per-platform packaging configuration. |
| `app/tsconfig.json`, `tsconfig.electron.json`, `vite.config.ts` | Separate renderer/main-process compilation and local asset bundling. |
| `app/components.json` | shadcn source aliases and component configuration. |
| `app/playwright.config.ts`, `vitest.config.ts` | Native desktop and isolated renderer test runners. |
| `app/tests/desktop/app.spec.ts` | Real Electron UI/capture acceptance, also runnable against the packaged executable. |
| `app/tests/stores.test.ts`, `media.test.ts` | Snapshot ordering, error honesty and late voice-response cancellation. |
| `tests/test_backend.py` | API, privacy, migration, provider contract and teaching-flow regressions. |
| `tools/build_backend.py`, `backend_entry.py` | Portable PyInstaller sidecar build and frozen entry point. |
| `tools/check_packaged_backend.py` | Starts the real frozen service with isolated data and checks authentication/empty startup. |
| `tools/make_desktop_icons.py`, `app/assets/` | Reproducible original waveform icon and generated Windows/macOS installer assets. |
| `.github/workflows/desktop.yml` | Windows and macOS build/test/package matrix; requires an actual CI run to produce remote artifacts. |
| `main.py`, `pyproject.toml`, `requirements*.txt` | Electron compatibility launcher, Python package metadata and separated current/legacy development dependencies. |
