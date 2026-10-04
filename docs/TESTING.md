# Hosted browser validation

## Request diagnostics (0.5.0, October 4, 2026)

144 Python tests, 16 renderer tests, and 17 Edge browser acceptance cases passed.
The production browser/extension build and TypeScript checks passed. New cases
cover request-ID correlation on successful, rejected and unexpected server
responses; safe traceback locations and provider HTTP status; correlation from
an asynchronous model failure back to its initiating command; network loss,
offline state, 60-second timeouts, interrupted response bodies, malformed JSON,
HTML proxy errors, and a diagnostic download that excludes private notes/titles.
Failed mutations are sent once, without an automatic retry. Tests use fixture
providers and simulated network failures; they do not identify the cause of a
previous failure in another browser session.

## Core AI and workflow deletion (0.5.0, October 4, 2026)

Local Windows results:

- 141 Python tests passed (`tests` and `EvalTest`). Coverage includes provider availability after creation/reopen/recovery, note-only live interjections, score/age/cooldown eligibility, provider failure backoff, one automatic question per approved revision, unsupported observations, ownership, inactive-workflow isolation, deletion retry, and late AI results after deletion.
- 11 renderer tests passed, including before/after selection within the existing upload budget, the 30-frame cap, and sensitivity to small field changes.
- 16 browser acceptance cases passed in Edge. They use the actual browser build, API, MediaRecorder, IndexedDB, local OCR and video workers, with deterministic provider responses. A real eleven-second canvas capture produces two approved-frame uploads and one persistent change question; repeating analysis neither reuploads nor duplicates the question. Short routine capture produces the explicit no-question notice.
- Browser cases verify Text only / Voice only / Text and voice, preference persistence, no live screen uploads, text fallback on speech failure, context/Work Map/frame progress across navigation, and Home/Workflows/Settings deletion controls. Named confirmation can be canceled; local cleanup failure remains retryable after server deletion. Deleting a pending local render drains processing and leaves no assets, chunks or review draft after the delayed work would have finished.
- TypeScript, extension type checks, and the production browser/companion build passed. Vite still reports its existing bundle-size and mixed static/dynamic-import advisories.
- The companion extension acceptance case passed in Edge: stable mounting, controls, dragging, status updates and reconnect.

Speech requests/playback failure are simulated in these browser tests; live ElevenLabs audio, microphone hardware, independently labeled model quality, production PostgreSQL and the current Replit deployment were not validated in this revision. See [brief alignment](BRIEF_ALIGNMENT.md) for challenge criteria that the selected notes-during-recording privacy flow does not meet.

Build the UI, start the test-only fixture server on port 3001, then run `npm run test:web` from `app/`. Never publish `tests.web_fixture:app`.

## Privacy review and extension (0.4.0, October 4, 2026)

Local results on Windows:

- 73 Python tests passed, including approved-revision uploads, guest isolation, stale-result cancellation, provider failures, quota persistence and evidence invalidation.
- 7 renderer/unit tests passed, including identifier patterns, keyframe geometry, cut rejection and typed extension-message validation.
- 7 browser acceptance cases passed in Edge and Chrome for Testing 153. These exercise the real API, MediaRecorder, IndexedDB, packaged Tesseract OCR and WebCodecs/Mediabunny. The draft test was corrected to scroll the video into view before drawing.
- The extension interaction case passed in both browsers: rapid toggles preserve the orb's bounds/iframe identity; drag and keyboard positioning persist across reload; notes/record/stop synchronize with the app; ordinary page clicks still work; reconnect uses current state.
- Production browser build and separate extension TypeScript checks passed. The build produces the ZIP, unpacked folder, download asset and local OCR dependencies.

The video test decodes the rendered WebM at moments before, during and after timed masks and checks actual pixel values, including moving keyframes. It also forces a full derivative budget, damaged input, and an unavailable WebCodecs encoder: none returns a successful unredacted export. The draft test delays render dispatch to verify cancellation through the real worker/IndexedDB cleanup path. Browser requests are checked for local OCR asset loading and absence of raw media uploads; the app flow uploads through the reviewed-frame route only after approval. Manual masks/markers survive reload and cancellation, and unapproved recordings have no Library download control.

Provider responses and capture contents are test-only fixtures. Extension tests use a test-only manifest with pregranted host permission to avoid an interactive installation prompt; the shipped manifest requests optional access in Options. No fixture entry point or pregranted test manifest is included in release artifacts.

Commands (build first, then start `python -m uvicorn tests.web_fixture:app --host 127.0.0.1 --port 3001` in another terminal):

```text
python -m pytest -q
cd app
npm test
npm run test:web
npm run test:extension
```

For Chrome for Testing, install Playwright Chromium and set `WEB_TEST_CHANNEL=chromium` / `EXTENSION_CHANNEL=chromium`. `PLAYWRIGHT_BROWSERS_PATH` can point at an isolated test-browser folder. Edge is the default. Do not publish `tests.web_fixture`.

Still requires real-environment acceptance: retail Chrome installation/permission prompts, mixed-DPI physical monitors and OS capture permissions, long recordings on lower-memory hardware, real ElevenLabs/OpenAI in the approved-frame flow, and the published Replit URL/production database. OCR misses, false positives, and missed cuts remain possible; manual review is always required. No public deployment or store listing was performed by these checks.

## Historical hosted checks (0.3.0)

On October 3, 2026: all 72 Python tests, four renderer tests, and four Edge browser acceptance tests passed. Both web and Electron TypeScript builds passed. The hosted suite adds guest isolation, origin/cookie checks, durable quotas, privacy invalidation, reload recovery and sanitized provider failures. Browser acceptance covers permission denial, capture/navigation/pause/resume, local video playback, debrief, map review/confirmation, teaching, reload and deletion.

The browser suite uses a test-only model adapter and a canvas capture stream, with the real API, MediaRecorder and IndexedDB. A separate paid-provider check (`python tools/check_hosted_live.py`) passed with the configured OpenAI key: a real debrief question, five evidence-linked map steps, and practice from confirmed synthetic test evidence. This opt-in script sends only disposable notes and removes its temporary database. ElevenLabs, production PostgreSQL and the published Replit URL still need acceptance.

See [REPLIT.md](REPLIT.md) for commands and the production checklist. Historical desktop results follow; the packaged 0.2.0 executable was not rebuilt as part of the hosted change.

Replit workspace build passed. `tools/check_hosted_database.py` passed against its actual development PostgreSQL: save/load, cross-guest denial, and reconnect persistence. The fourth browser test deliberately loses the stop HTTP request during a WebSocket disconnect and verifies that reconnection recovers an idle, consent-off state and permits a new recording.

# Validation — Electron migration

Verified locally on Windows on October 3, 2026. The desktop tests used isolated temporary sessions and disabled provider credentials. Test data was not seeded into the installed application.

## Passed

| Check | Result |
| --- | --- |
| Python regression suite | 60 passed, including 12 new headless backend tests and the existing domain/Qt regression tests. |
| Renderer state and voice cancellation | 4 passed across 2 Vitest files. |
| TypeScript and Vite production build | Passed for renderer, preload and Electron main process. |
| Frozen Python service | Authenticated empty startup passed from its packaged executable with no source environment or .env. |
| Packaged Windows desktop suite | 2 passed against release/electron/win-unpacked/AI Apprentice.exe. |
| Windows installer | AI Apprentice Setup 0.2.0.exe built successfully; approximately 141 MB decimal. Unsigned. |
| Runtime dependency audit | npm audit --omit=dev reported zero vulnerabilities. Electron was separately upgraded to 44.5.1 after reviewing the full audit. |
| Release content inspection | No tests, .env, legacy Python UI source or packaging tools in app.asar; no Qt or apprentice.demo in the frozen Python module archive. |
| Visual review | White Home interface and expanded floating toolbar inspected from actual Electron screenshots. |

The packaged desktop suite covers an empty first launch, user-created notes, note persistence in Library, settings without credentials, expanded overlay controls, Context focusing the main input, genuine screen capture, capture across page navigation and minimization, pause/resume, two saved video segments, and stop. A launch-order test issue was corrected by identifying the main window by its URL rather than assuming the first reported window is the main window.

Backend tests cover authentication, monotonic events and revisions, no-credential local notes, pause privacy, secret omission from state/storage, evidence deletion and invalidation, confirmation requirements, non-destructive legacy import, stale-result rejection, unsupported practice citations, sanitized provider failures, and the full debrief → map → review → practice/coaching contract with deterministic test-only provider responses. ElevenLabs HTTP request formats are tested with a mock transport. Renderer tests additionally verify that late microphone permission and late speech responses cannot restart capture/playback after cancellation.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/check_packaged_backend.py
cd app
npm run build
npm test
npm run test:desktop
```

For the packaged executable, set APPRENTICE_EXECUTABLE to the absolute path of release/electron/win-unpacked/AI Apprentice.exe before running npm run test:desktop. The test suite briefly records the actual display and deletes its temporary data after closing the app.

## Remaining release checks

- macOS DMGs are configured in the build and CI matrix but were not built or tested on this Windows host. Validate Intel/Apple Silicon builds, microphone/screen permissions, overlay transparency, click passthrough, display scaling and signing/notarization on Macs.
- Live ElevenLabs speech/transcription and a complete paid-provider workflow were not run as part of this migration. Enter credentials in Settings, check connections, and perform a real expert-to-trainee session before presenting those integrations as live-verified.
- Physical microphone/device variations, multi-monitor mixed-DPI dragging, screen-permission denial/revocation and simulated disk-full recovery still need broader hardware acceptance testing. Single-host automated capture does not establish those guarantees.
- The full npm audit reports eight high-severity entries in the build-only electron-builder → @electron/get → got/http-cache-semantics dependency chain. They are not part of the installed application's production dependencies. npm's suggested older builder introduced additional advisories, so the current builder was retained. Review a patched packaging dependency chain before public release.
- Vite reports a renderer chunk slightly above its 500 kB advisory threshold. It is a bundled local asset, not a network dependency; further route splitting is an optimization, not a completed performance benchmark.

## Fixes found during validation

A chat effect returned the new Chromium scrolling result instead of a cleanup function, causing a render failure after saving a note. The effect now explicitly returns nothing. Context focus now follows component mounting rather than an arbitrary timer. Microphone/speech generations reject late responses, and overlapping stop/close requests wait for the same recording flush.

## Evaluation integration checks (2026-10-04)

The evaluation implementation is specified in [EVALUATION.md](EVALUATION.md).
Local validation includes 133 Python tests (`tests` plus the separate `EvalTest`
sandbox), 7 renderer tests, a successful browser/extension build, and the browser
flow in `app/tests/web/evaluation.spec.ts`. The latter covers dimension visibility,
an explicit gap review, executable-check approval, incorrect/correct threshold
answers, and feedback persistence after reload. The existing browser capture,
privacy review, debrief, map, teaching, guest isolation and recovery flows are
also exercised in `app/tests/web/app.spec.ts`.

`tools/evaluate_logic.py tests/fixtures/evaluation_replays.json` matched all 13
synthetic reference decisions, with zero false gap closures among 6 unresolved
cases and zero incorrect learner passes among 4 non-pass cases. These fixtures
replay model proposals; they do not establish live-model semantic accuracy or
calibrate the confidence thresholds. Independent expert labeling and held-out
workflow evaluation remain necessary before making such claims.
