# Development and packaging

## Local setup

Python 3.12 and Node.js 22+ are required for development. Create .venv at the repository root, install requirements.txt, then run npm ci in app. The Electron main process locates .venv/Scripts/python.exe on Windows and .venv/bin/python on macOS. APPRENTICE_PYTHON can override this executable. APPRENTICE_DATA_DIR can isolate test or development data.

Run npm run dev inside app to compile and launch, or npm run build followed by npm start. There is no public dev server and no runtime CDN. main.py forwards to Electron. The old Qt entry point remains available only as historical source; it is not the supported product.

## Work on the application

- UI: React pages and shared components in app/src. Use the central tokens and animation presets. Do not add demo fallback responses, sample sessions, preset practice cases, or fake metrics.
- Native capabilities: extend app/electron/preload.ts with a specific typed capability, validate its sender and data in main.ts, and update src/types.ts. Never expose generic IPC, shell execution, tokens or unrestricted paths.
- Backend: add validated commands/services behind backend/server.py. Provider jobs receive snapshots and must go through Service.launch so cancellation/privacy generations are enforced.
- Tests: synthetic examples belong under tests or app/tests. Domain tests may retain legacy fixtures, which are excluded from the bundle.

Before submitting changes, run TypeScript/Vite compilation, Python headless tests, renderer tests and the relevant desktop acceptance tests. Run npm audit; runtime and build-time advisories should be reported separately. Format TypeScript/TSX/CSS with the included Prettier executable.

## Build installers

Install requirements-build.txt and run python tools/build_backend.py from the root. It bundles the backend and dependencies into dist/backend, explicitly excluding Qt, the demo module and old capture dependencies. It never copies .env or test directories. Then run npm run package inside app. Outputs live under release/electron, separate from historical dist/AI-Apprentice builds.

Build each platform/architecture on its corresponding host. The GitHub Actions workflow creates Windows, Apple Silicon and Intel macOS packages. The workflow must actually run before those artifacts exist. Local Windows validation cannot establish macOS permission or transparency behavior. Signing/notarization is intentionally dependent on release-owner credentials. Configure electron-builder signing secrets for public distribution; do not commit certificates.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Green or old Qt window | Close the legacy executable. Launch app with npm start or use release/electron. |
| Python service cannot start | Confirm .venv dependencies, or rebuild the sidecar. Check APPRENTICE_PYTHON. Installed apps require resources/backend beside their resources. |
| Empty source list / denied capture | Grant Screen Recording permission in macOS System Settings or Windows privacy settings, then restart the app. |
| Display preview hidden | Intentional recursion prevention. Select an external application window for a live preview. |
| No AI observations | Enable cloud analysis for this session and configure OpenAI. Analyze real screen activity; empty observations are valid. |
| Voice fails | Check ElevenLabs key permissions, voice ID, microphone permission and selected system microphone. Click Voice explicitly. |
| Map cannot be confirmed | Review and verify every retained step; reject unsupported/conflicting items or add expert context. |
| Recording stops on disk error | Free space or resolve folder access. Completed chunks remain in the partial segment; do not treat it as a complete recording. |
| macOS overlay appears in recording | Modern ScreenCaptureKit may ignore content protection. Capture an external window or position the overlay away from the target. |
| Overlay moved off a disconnected monitor | Display changes clamp it back into an available work area. |
| A packaged binary is locked during rebuild | Close that application before replacing the generated output. Never overwrite an active installation. |

## Known release checks

The current Windows implementation is exercised locally. macOS signing, native permissions, mixed-display positioning and transparent-window hit testing require Mac hardware. Production runtime dependencies and packaging-only dependencies have separate audit reports. See TESTING.md for actual verification results; configuration alone is not a successful platform test.
