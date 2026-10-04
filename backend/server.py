"""Authenticated loopback API. The Electron main process is its only client."""
import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from apprentice.config import Settings
from backend.service import Service
from backend.voice import ElevenVoice
from apprentice.exporting import export_session


class Command(BaseModel):
    name: str
    data: dict = Field(default_factory=dict)


def create_app(root, token, settings=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.service = Service(root, settings or Settings.load(Path.cwd()))
        yield
        await app.state.service.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        size = int(request.headers.get("content-length", "0"))
        if size > 16 * 1024 * 1024:
            return JSONResponse({"detail": "Payload too large"}, status_code=413)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({"detail": "Item not found"}, status_code=404)

    @app.get("/state")
    async def state():
        return await app.state.service.snapshot()

    @app.post("/command")
    async def command(body: Command):
        return await app.state.service.command(body.name, body.data)

    @app.post("/frame")
    async def frame(request: Request, duration: float = 0, idle: float = 0):
        await app.state.service.frame(await request.body(), duration, idle)
        return {}

    @app.post("/speech")
    async def speech(request: Request):
        body = await request.json()
        try:
            audio = await asyncio.to_thread(ElevenVoice(app.state.service.settings).speak, str(body["text"]))
            return Response(audio, media_type="audio/mpeg")
        except httpx.HTTPError:
            raise HTTPException(502, "ElevenLabs speech failed. Check your key, voice and connection.")

    @app.post("/transcribe")
    async def transcribe(request: Request):
        try:
            text = await asyncio.to_thread(ElevenVoice(app.state.service.settings).transcribe, await request.body())
            return {"text": text}
        except httpx.HTTPError:
            raise HTTPException(502, "ElevenLabs transcription failed. Your answer was not saved.")

    @app.post("/check-credentials")
    async def check(request: Request):
        provider = (await request.json())["provider"]
        settings = app.state.service.settings
        url, headers = (("https://api.openai.com/v1/models", {"Authorization": "Bearer " + settings.openai_key}) if provider == "openai"
                        else ("https://api.elevenlabs.io/v1/voices", {"xi-api-key": settings.eleven_key}))
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
            return {"ok": True}
        except httpx.HTTPError:
            raise HTTPException(502, "Connection check failed. Verify the key, its permissions, and your network.")

    @app.post("/import")
    async def import_legacy(request: Request):
        service = app.state.service
        async with service.lock:
            count = await service.repo.import_legacy((await request.json())["path"])
            await service.emit()
            return {"count": count}

    @app.post("/export")
    async def export(request: Request):
        service = app.state.service
        snapshot = service.require_session().model_copy(deep=True)
        folder = await service.repo.call(export_session, snapshot, service.repo.store, Path((await request.json())["path"]))
        return {"path": str(folder)}

    @app.websocket("/events")
    async def events(socket: WebSocket):
        if not hmac.compare_digest(socket.headers.get("authorization", ""), "Bearer " + token):
            await socket.close(code=1008)
            return
        await socket.accept()
        queue = asyncio.Queue(maxsize=100)
        service = app.state.service
        service.listeners.add(queue)
        try:
            await socket.send_json({"type": "resync", "sequence": service.sequence})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), 20)
                except asyncio.TimeoutError:
                    event = {"type": "heartbeat", "sequence": service.sequence}
                await socket.send_json(event)
        except Exception:
            pass
        finally:
            service.listeners.discard(queue)
    return app
