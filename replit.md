# AI Apprentice

Existing application, not a new scaffold. Keep the shared React UI and Python domain logic.

- Web entry point: `.venv/bin/python -m backend.web`, port 3000. Production: one Reserved VM worker.
- Build: `python -m venv .venv && PIP_USER=0 .venv/bin/python -m pip install -r requirements-web.txt`, then `cd app && ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm ci && npm run build:web`.
- Required production configuration: PostgreSQL `DATABASE_URL` and stable random `GUEST_SECRET` (32+ characters), or Replit's existing `SESSION_SECRET`. Provider Secrets: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`. Never expose keys to the renderer or commit them.
- Read `docs/REPLIT.md` for setup, data boundaries, module responsibilities and acceptance.
- No seeded or fallback workflows, conversations, exercises or AI results. Test fixtures under `tests/` are never a runtime entry point.
- Browser media stays in IndexedDB; only approved redacted frames after Analyze and explicit voice answers reach providers. Text/maps use guest-scoped PostgreSQL. AI has no separate activation switch.
- `/healthz` reports running version/revision. Server logs contain correlated request/provider/job IDs, status, timing, and sanitized traceback locations. Never log bodies, notes, media, cookies, keys, or raw provider exceptions. Browser Settings exports a bounded diagnostic log.
- Preserve the Electron edition. Do not run the desktop `main.py` or install Qt for the hosted backend.
