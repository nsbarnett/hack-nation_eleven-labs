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
# Hosted browser validation

On October 3, 2026: all 72 Python tests, four renderer tests, and three Edge browser acceptance tests passed. Both web and Electron TypeScript builds passed. The hosted suite adds guest isolation, origin/cookie checks, durable quotas, privacy invalidation, reload recovery and sanitized provider failures. Browser acceptance covers permission denial, capture/navigation/pause/resume, local video playback, debrief, map review/confirmation, teaching, reload and deletion.

The browser suite uses a test-only model adapter and a canvas capture stream, with the real API, MediaRecorder and IndexedDB. It is not evidence of live provider success or published Replit acceptance. See [REPLIT.md](REPLIT.md) for commands and the remaining production checklist. Historical desktop results follow; the packaged 0.2.0 executable was not rebuilt as part of the hosted change.

