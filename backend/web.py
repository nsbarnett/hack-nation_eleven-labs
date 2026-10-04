"""Public web entry point: same-origin React UI + guest-authenticated FastAPI.

Run one worker on a Replit Reserved VM. Guest-scoped service instances keep the
existing asynchronous pipeline, while PostgreSQL stores text snapshots. This API
deliberately has no filesystem, credentials, import, or video-upload endpoint.
"""
import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from apprentice.config import Settings
from backend.hosted_service import HostedService, IDENTIFIER, ALLOWED
from backend import diagnostics
from backend.hosted_store import HostedDatabase, GuestRepository, LimitError
from backend.voice import ElevenVoice

COOKIE = "apprentice_guest"
WEEK = 7 * 86400


@dataclass
class Guest:
    service: HostedService
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    seen: float = field(default_factory=time.monotonic)
    requests: deque = field(default_factory=deque)
    last_frame: float = 0


class Command(BaseModel):
    name: str = Field(max_length=40)
    data: dict = Field(default_factory=dict)
    sessionId: str | None = None


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    sessionId: str


class HostedRuntime:
    def __init__(self, database, settings, *, guest_limit=100, global_limit=1000):
        self.database, self.settings = database, settings
        self.guest_limit, self.global_limit = guest_limit, global_limit
        self.guests = OrderedDict()
        self.lock = asyncio.Lock()
        self.providers = asyncio.Semaphore(4)

    async def provider(self, guest, role, work):
        began = time.monotonic()
        diagnostics.log("provider_started", operation=role)
        try:
            if self.providers.locked():
                raise LimitError("The hosted assistant is busy. Try again shortly.")
            async with self.providers:
                await self.database.consume(guest, self.guest_limit, self.global_limit)
                result = await asyncio.to_thread(work)
            diagnostics.log("provider_completed", operation=role, elapsed_ms=round((time.monotonic() - began) * 1000))
            return result
        except Exception as error:
            diagnostics.log("provider_failed", level=logging.ERROR, operation=role,
                elapsed_ms=round((time.monotonic() - began) * 1000), **diagnostics.failure(error))
            raise

    async def get(self, identifier):
        async with self.lock:
            if identifier not in self.guests:
                # A hard ceiling bounds live workers and image buffers. Evicted
                # work is reloaded from PostgreSQL, never another guest's cache.
                if len(self.guests) >= 32:
                    for key, candidate in list(self.guests.items()):
                        if not candidate.service.tasks and time.monotonic() - candidate.seen > 90:
                            await candidate.service.close()
                            self.guests.pop(key)
                            break
                    else:
                        raise LimitError("All hosted workspaces are busy. Please try again shortly.")
                service = HostedService(None, self.settings,
                    repository=GuestRepository(self.database, identifier),
                    work_runner=lambda role, work: self.provider(identifier, role, work))
                await service.restore()
                self.guests[identifier] = Guest(service)
            item = self.guests[identifier]
            item.seen = time.monotonic()
            self.guests.move_to_end(identifier)
            return item

    async def tidy(self):
        while True:
            await asyncio.sleep(60)
            async with self.lock:
                for identifier, guest in list(self.guests.items()):
                    if time.monotonic() - guest.seen > 90 and not guest.service.tasks:
                        await guest.service.close()
                        self.guests.pop(identifier)
            await self.database.cleanup()

    async def close(self):
        await asyncio.gather(*(g.service.close() for g in self.guests.values()))
        await self.database.close()


def create_web_app(database_url=None, secret=None, settings=None, *, production=None, static_dir=None,
                   guest_limit=100, global_limit=1000):
    settings = settings or Settings.load(Path.cwd())
    production = os.getenv("APP_ENV", "production") == "production" if production is None else production
    database_url = database_url or os.getenv("DATABASE_URL")
    # Replit can provision SESSION_SECRET on import. Reuse that stable secret
    # when the owner has not supplied an application-specific override.
    secret = secret or os.getenv("GUEST_SECRET") or os.getenv("SESSION_SECRET")
    if production and (not database_url or not database_url.startswith(("postgresql://", "postgres://")) or not secret or len(secret) < 32):
        raise RuntimeError("Production requires a PostgreSQL DATABASE_URL and a GUEST_SECRET (or SESSION_SECRET) of at least 32 characters.")
    database_url = database_url or "sqlite:///.artifacts/web-data.sqlite3"
    secret = secret or "local-development-only-guest-secret"
    if guest_limit < 1 or global_limit < 1:
        raise RuntimeError("Hosted AI limits must be positive integers.")
    static_dir = Path(static_dir or Path(__file__).resolve().parents[1] / "app" / "dist")

    def sign(guest):
        message = guest + "." + str(int(time.time()) + WEEK)
        return message + "." + hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def identity(value):
        try:
            guest, expires, signature = (value or "").split(".")
            message = guest + "." + expires
            expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
            if IDENTIFIER.fullmatch(guest) and int(expires) > time.time() and hmac.compare_digest(signature, expected):
                return guest
        except (ValueError, TypeError):
            pass
        return None

    @asynccontextmanager
    async def lifespan(app):
        runtime = HostedRuntime(HostedDatabase(database_url), settings, guest_limit=guest_limit, global_limit=global_limit)
        app.state.runtime = runtime
        await runtime.database.cleanup()
        cleanup = asyncio.create_task(runtime.tidy())
        diagnostics.log("server_started", version=diagnostics.VERSION, revision=diagnostics.revision(),
            production=production, openai_configured=bool(settings.openai_key), elevenlabs_configured=bool(settings.eleven_key))
        yield
        cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)
        await runtime.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def same_origin(request):
        expected = os.getenv("PUBLIC_ORIGIN", f"{'https' if production else request.url.scheme}://{request.headers.get('host', '')}").rstrip("/")
        return request.headers.get("origin", "").rstrip("/") == expected

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            if request.method not in {"GET", "HEAD"}:
                if not same_origin(request) or request.headers.get("x-apprentice-client") != "web":
                    return JSONResponse({"detail": "Same-origin browser request required."}, 403)
                limit = 2_000_000 if request.url.path.endswith("/transcribe") else 1_000_000 if request.url.path.endswith(("/frame", "/reviewed-frame")) else 65_536
                parts, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > limit:
                        return JSONResponse({"detail": "This upload exceeds the hosted size limit."}, 413)
                    parts.append(chunk)
                request._body = b"".join(parts)
            guest = identity(request.cookies.get(COOKIE))
            fresh = guest is None
            if fresh and request.url.path != "/api/state":
                return JSONResponse({"detail": "Open the app to start a browser workspace."}, 401)
            request.state.guest = guest or secrets.token_hex(16)
            try:
                entry = await app.state.runtime.get(request.state.guest)
                now = time.monotonic()
                while entry.requests and entry.requests[0] < now - 60:
                    entry.requests.popleft()
                if len(entry.requests) >= 180:
                    raise LimitError("Too many requests. Wait a moment and try again.")
                entry.requests.append(now)
                request.state.entry = entry
                response = await call_next(request)
            except LimitError as error:
                return JSONResponse({"detail": str(error)}, 429)
            if fresh:
                response.set_cookie(COOKIE, sign(request.state.guest), max_age=WEEK,
                                    httponly=True, secure=production, samesite="strict")
            response.headers["Cache-Control"] = "no-store"
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), display-capture=(self)"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.middleware("http")
    async def request_diagnostics(request: Request, call_next):
        supplied = request.headers.get("x-apprentice-request-id", "")
        identifier = supplied if IDENTIFIER.fullmatch(supplied) else secrets.token_hex(16)
        token = diagnostics.request_id.set(identifier)
        request.state.request_id = identifier
        began = time.monotonic()
        known = {"/api/state", "/api/command", "/api/frame", "/api/reviewed-frame", "/api/speech", "/api/transcribe", "/healthz", "/"}
        path = request.url.path if request.url.path in known else "static_or_unknown"
        try:
            try:
                response = await call_next(request)
            except Exception as error:
                diagnostics.log("request_exception", level=logging.ERROR, method=request.method, endpoint=path,
                    operation=getattr(request.state, "operation", None), **diagnostics.failure(error))
                response = JSONResponse({"detail": "The app server could not complete this request. Use its request ID to check the server logs."}, 500)
            response.headers["X-Apprentice-Request-ID"] = identifier
            response.headers["X-Apprentice-Version"] = diagnostics.VERSION
            if request.url.path.startswith("/api/") or path in {"/", "/healthz"}:
                response.headers["Cache-Control"] = "no-store"
            if path != "static_or_unknown" or response.status_code >= 400:
                diagnostics.log("request_completed", level=logging.WARNING if response.status_code >= 400 else logging.INFO,
                    method=request.method, endpoint=path, operation=getattr(request.state, "operation", None),
                    status=response.status_code, elapsed_ms=round((time.monotonic() - began) * 1000))
            return response
        finally:
            diagnostics.request_id.reset(token)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({"detail": "Invalid request fields. Refresh the app and retry."}, 422)

    @app.exception_handler(LimitError)
    async def limited(request, error):
        return JSONResponse({"detail": str(error)}, 429)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        # Pydantic errors can echo user input; do not return the full validation dump.
        return JSONResponse({"detail": "Invalid command data." if isinstance(error, ValidationError) else str(error)}, 400)

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({"detail": "Workflow or source not found."}, 404)

    @app.get("/healthz")
    async def health():
        await app.state.runtime.database.call(lambda: app.state.runtime.database.execute("SELECT 1").fetchone())
        return {"ok": True, "version": diagnostics.VERSION, "revision": diagnostics.revision()}

    @app.get("/api/state")
    async def state(request: Request):
        entry = request.state.entry
        async with entry.service.lock:
            state = await entry.service.snapshot()
        return {**state, "version": diagnostics.VERSION, "revision": diagnostics.revision(), "hosted": True, "guest": request.state.guest,
                "limits": {"recordingSeconds": 300, "mediaBytes": 100_000_000, "dailyAiCalls": guest_limit},
                "media": {"state": "idle", "muted": True, "voice": "idle", "duration": 0}}

    @app.post("/api/command")
    async def command(request: Request, body: Command):
        request.state.operation = body.name if body.name in ALLOWED else "unsupported_command"
        async with request.state.entry.lock:
            try:
                return await request.state.entry.service.hosted_command(body.name, body.data, body.sessionId)
            except (TypeError, StopIteration, OverflowError):
                raise ValueError("Invalid command data.")

    @app.post("/api/frame")
    async def frame(request: Request, sessionId: str, id: str, duration: float = 0, idle: float = 0):
        entry = request.state.entry
        async with entry.lock:
            if time.monotonic() - entry.last_frame < 1.5:
                raise LimitError("Screen sampling is limited to one frame every two seconds.")
            entry.last_frame = time.monotonic()
            try:
                await entry.service.hosted_frame(await request.body(), duration, idle, sessionId, id)
            except (OSError, ImageError):
                raise ValueError("This screenshot could not be read.")
        return {}

    @app.post("/api/reviewed-frame")
    async def reviewed_frame(request: Request, sessionId: str, id: str, revision: int, duration: float = 0):
        entry = request.state.entry
        async with entry.lock:
            if time.monotonic() - entry.last_frame < 1.5:
                raise LimitError("Wait two seconds before submitting another reviewed frame.")
            try:
                await entry.service.reviewed_frame(await request.body(), duration, sessionId, id, revision)
                entry.last_frame = time.monotonic()
            except (OSError, ImageError):
                raise ValueError("This reviewed screenshot could not be read.")
        return {}

    @app.post("/api/speech")
    async def speech(request: Request, body: SpeechRequest):
        service = request.state.entry.service
        session = service.require_session()
        text = body.text
        if body.sessionId != session.id or not any(m.role == "assistant" and m.text == text for m in session.messages):
            raise ValueError("Speech is available for this workflow's assistant messages only.")
        if not settings.eleven_key:
            raise ValueError("Hosted voice is unavailable. The app owner must configure ElevenLabs; text answers still work.")
        try:
            audio = await app.state.runtime.provider(request.state.guest, "speech", lambda: ElevenVoice(settings).speak(text))
            return Response(audio, media_type="audio/mpeg")
        except httpx.HTTPError:
            raise HTTPException(502, "Assistant speech is unavailable. The question is still available as text.")

    @app.post("/api/transcribe")
    async def transcribe(request: Request, sessionId: str):
        service = request.state.entry.service
        if service.require_session().id != sessionId or service.recording == "paused":
            raise ValueError("This workflow is not accepting a voice answer.")
        audio = await request.body()
        if not audio:
            raise ValueError("The voice answer was empty.")
        if not settings.eleven_key:
            raise ValueError("Hosted voice is unavailable. The app owner must configure ElevenLabs; text answers still work.")
        try:
            text = await app.state.runtime.provider(request.state.guest, "transcribe", lambda: ElevenVoice(settings).transcribe(audio))
            return {"text": text}
        except httpx.HTTPError:
            raise HTTPException(502, "Voice transcription failed. Try again or type your answer.")

    @app.websocket("/api/events")
    async def events(socket: WebSocket):
        # Browser WebSockets cannot set Authorization headers. Use the same
        # HttpOnly guest cookie and validate Origin before accepting a connection.
        guest = identity(socket.cookies.get(COOKIE))
        expected = os.getenv("PUBLIC_ORIGIN", f"{'https' if production else 'http'}://{socket.headers.get('host', '')}").rstrip("/")
        if not guest or socket.headers.get("origin", "").rstrip("/") != expected:
            diagnostics.log("websocket_rejected", level=logging.WARNING, code=1008)
            await socket.close(code=1008)
            return
        entry = await app.state.runtime.get(guest)
        if len(entry.service.listeners) >= 3:
            diagnostics.log("websocket_rejected", level=logging.WARNING, code=1013)
            await socket.close(code=1013)
            return
        await socket.accept()
        diagnostics.log("websocket_opened")
        queue = asyncio.Queue(maxsize=50)
        entry.service.listeners.add(queue)
        try:
            await socket.send_json({"type": "resync", "epoch": entry.service.epoch})
            while True:
                entry.seen = time.monotonic()
                try:
                    event = await asyncio.wait_for(queue.get(), 20)
                except asyncio.TimeoutError:
                    event = {"type": "heartbeat"}
                await socket.send_json(event)
        except WebSocketDisconnect as error:
            diagnostics.log("websocket_closed", code=error.code)
        except Exception as error:
            diagnostics.log("websocket_failed", level=logging.WARNING, **diagnostics.failure(error))
        finally:
            entry.service.listeners.discard(queue)

    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    for folder in ("ocr", "downloads"):
        if (static_dir / folder).is_dir():
            app.mount("/" + folder, StaticFiles(directory=static_dir / folder), name=folder)

    @app.get("/")
    async def index():
        if not (static_dir / "index.html").is_file():
            raise HTTPException(503, "Build the React application before starting the web server.")
        return FileResponse(static_dir / "index.html")

    return app


# Pillow's bomb check is separate from ordinary image decoding errors.
from PIL.Image import DecompressionBombError as ImageError


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_web_app(guest_limit=int(os.getenv("HOSTED_GUEST_AI_CALLS", "100")),
                              global_limit=int(os.getenv("HOSTED_DAILY_AI_CALLS", "1000"))),
                host="0.0.0.0", port=int(os.getenv("PORT", "3000")), workers=1)
