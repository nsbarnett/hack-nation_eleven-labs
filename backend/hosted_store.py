"""Guest-scoped text persistence for Replit. No image, video, or audio bytes enter SQL.

Production uses PostgreSQL via DATABASE_URL. SQLite is an explicit local/test
option only. One worker owns the connection and transactions, so concurrent
requests cannot share a transaction or overspend a quota through a race.
"""
import asyncio
import json
import sqlite3
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apprentice.domain import Session, utc_now


class LimitError(ValueError):
    pass


class HostedDatabase:
    def __init__(self, url):
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hosted-db")
        self.postgres = url.startswith(("postgres://", "postgresql://"))
        self.worker.submit(self._connect, url).result()

    def _connect(self, url):
        if self.postgres:
            import psycopg
            self.db = psycopg.connect(url, autocommit=True, connect_timeout=10)
        else:
            filename = url.removeprefix("sqlite:///")
            if filename != ":memory:":
                Path(filename).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(filename, isolation_level=None)
        self.execute("""CREATE TABLE IF NOT EXISTS hosted_sessions (
            guest TEXT NOT NULL, id TEXT NOT NULL, updated TEXT NOT NULL,
            payload TEXT NOT NULL, runtime TEXT NOT NULL,
            PRIMARY KEY (guest, id))""")
        self.execute("""CREATE TABLE IF NOT EXISTS hosted_quotas (
            scope TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL,
            PRIMARY KEY(scope, day))""")

    def execute(self, query, args=()):
        return self.db.execute(query.replace("?", "%s") if self.postgres else query, args)

    async def call(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(self.worker, fn, *args)

    async def consume(self, guest, guest_limit, global_limit):
        """Charge before a provider request, including failures; limits survive restarts."""
        def charge():
            day = datetime.now(timezone.utc).date().isoformat()
            self.execute("BEGIN")
            try:
                for scope, limit in (("global", global_limit), (guest, guest_limit)):
                    # Global row first serializes concurrent PostgreSQL transactions too.
                    row = self.execute("""INSERT INTO hosted_quotas(scope,day,used) VALUES(?,?,1)
                        ON CONFLICT(scope,day) DO UPDATE SET used=hosted_quotas.used+1
                        WHERE hosted_quotas.used < ? RETURNING used""", (scope, day, limit)).fetchone()
                    if row is None:
                        raise LimitError("Today's hosted AI allowance is used. Your saved work is still available.")
                self.execute("COMMIT")
            except BaseException:
                self.execute("ROLLBACK")
                raise
        await self.call(charge)

    async def cleanup(self):
        def clean():
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            self.execute("DELETE FROM hosted_sessions WHERE updated < ?", (cutoff,))
            yesterday = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
            self.execute("DELETE FROM hosted_quotas WHERE day < ?", (yesterday,))
        await self.call(clean)

    async def close(self):
        await self.call(self.db.close)
        self.worker.shutdown(wait=True)


class GuestRepository:
    """A capability bound to one guest. Caller-supplied IDs never change its owner."""
    def __init__(self, database, guest):
        self.database, self.guest = database, guest
        self.frames = OrderedDict()

    async def call(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def save(self, session, runtime=None):
        payload = session.model_dump_json()
        if len(payload.encode()) > 2_000_000:
            raise LimitError("This workflow has reached its text storage limit. Export it and start another.")
        def write():
            self.database.execute("""INSERT INTO hosted_sessions VALUES(?,?,?,?,?)
                ON CONFLICT(guest,id) DO UPDATE SET updated=excluded.updated,
                payload=excluded.payload, runtime=excluded.runtime""",
                (self.guest, session.id, utc_now(), payload, json.dumps(runtime or {})))
        await self.database.call(write)

    async def load(self, sid):
        row = await self.database.call(lambda: self.database.execute(
            "SELECT payload FROM hosted_sessions WHERE guest=? AND id=?", (self.guest, sid)).fetchone())
        if not row:
            raise KeyError("Workflow not found")
        return Session.model_validate_json(row[0])

    async def runtime(self, sid):
        row = await self.database.call(lambda: self.database.execute(
            "SELECT runtime FROM hosted_sessions WHERE guest=? AND id=?", (self.guest, sid)).fetchone())
        return json.loads(row[0]) if row else {}

    async def list(self):
        rows = await self.database.call(lambda: self.database.execute(
            "SELECT id,updated,payload FROM hosted_sessions WHERE guest=? ORDER BY updated DESC", (self.guest,)).fetchall())
        result = []
        for sid, updated, payload in rows:
            item = Session.model_validate_json(payload)
            result.append({"id": sid, "updated": updated, "title": item.title,
                           "confirmed": item.confirmed, "steps": len(item.knowledge), "duration": item.duration})
        return result

    async def delete(self, sid):
        await self.database.call(lambda: self.database.execute(
            "DELETE FROM hosted_sessions WHERE guest=? AND id=?", (self.guest, sid)))
        for key in list(self.frames):
            if key[0] == sid:
                del self.frames[key]

    def clear_media_cache(self):
        self.frames.clear()

    async def save_frame(self, sid, filename, payload):
        self.frames[(sid, filename)] = payload
        while len(self.frames) > 3:
            self.frames.popitem(last=False)

    async def images(self, session, kind):
        # Immutable bytes are copied into the job's snapshot; clearing the cache
        # on a privacy action cannot make a worker reopen a deleted filesystem path.
        return [(e.id, self.frames[(session.id, e.image)]) for e in session.evidence
                if e.kind == kind and (session.id, e.image) in self.frames][-3:]

    async def remove_media(self, sid, paths):
        self.clear_media_cache()

    async def close(self):
        self.clear_media_cache()
