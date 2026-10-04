"""Serialize blocking SQLite and media operations on one dedicated worker thread."""
import asyncio
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from apprentice.store import SessionStore
from apprentice.domain import Session


class Repository:
    def __init__(self, root):
        self.root = Path(root)
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="repository")
        self.store = self.worker.submit(SessionStore, self.root).result()

    async def call(self, method, *args):
        return await asyncio.get_running_loop().run_in_executor(self.worker, method, *args)

    async def save(self, session):
        await self.call(self.store.save, session.model_copy(deep=True))

    async def load(self, sid):
        session = await self.call(self.store.load, sid)
        if session.mode != "live":
            raise ValueError("Only recorded live sessions can be opened.")
        return session

    async def list(self):
        def read():
            result = []
            for row in self.store.list():
                session = self.store.load(row["id"])
                if session.mode == "live":
                    result.append({**row, "confirmed": session.confirmed, "steps": len(session.knowledge), "duration": session.duration})
            return result
        return await self.call(read)

    async def import_legacy(self, root):
        def migrate():
            origin = Path(root).resolve()
            if origin == self.root.resolve() or not (origin / "apprentice.sqlite3").is_file():
                raise ValueError("Select the legacy folder containing apprentice.sqlite3.")
            source = sqlite3.connect((origin / "apprentice.sqlite3").as_uri() + "?mode=ro", uri=True)
            imported = 0
            try:
                existing = {r["id"] for r in self.store.list()}
                for (payload,) in source.execute("SELECT payload FROM sessions"):
                    session = Session.model_validate_json(payload)
                    if session.mode != "live" or session.id in existing:
                        continue
                    for relative in [e.image for e in session.evidence if e.image] + session.recordings:
                        if Path(relative).suffix.lower() not in {".jpg", ".jpeg", ".png", ".mp4", ".webm"}:
                            raise ValueError("Legacy session contains an unsupported media type.")
                        folder = (origin / "sessions" / session.id).resolve()
                        src = (folder / relative).resolve()
                        if not src.is_relative_to(folder) or not src.is_file():
                            raise ValueError("Legacy session has missing or unsafe media. Original data is unchanged.")
                        dest = self.store.media(session.id, relative)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, dest)
                    self.store.save(session)
                    imported += 1
                return imported
            finally:
                source.close()
        return await self.call(migrate)

    async def close(self):
        await self.call(self.store.close)
        self.worker.shutdown(wait=True)
