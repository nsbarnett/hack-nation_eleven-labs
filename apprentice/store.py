"""Single-writer SQLite repository and safe session-owned media paths.

The controller writes on the UI thread; workers receive immutable snapshots.
A transaction replaces one session snapshot, avoiding partially updated maps.
"""

from pathlib import Path
import sqlite3

from apprentice.domain import Session, utc_now


class SessionStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "apprentice.sqlite3")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, updated TEXT NOT NULL,
            payload TEXT NOT NULL)""")

    def directory(self, session_id: str) -> Path:
        if len(session_id) != 32 or any(c not in "0123456789abcdef" for c in session_id):
            raise ValueError("Invalid session identifier")
        folder = self.root / "sessions" / session_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def media(self, session_id: str, relative: str) -> Path:
        base = self.directory(session_id).resolve()
        path = (base / relative).resolve()
        if not relative or path == base or not path.is_relative_to(base):
            raise ValueError("Media path must stay inside its session")
        return path

    def save(self, session: Session) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "title=excluded.title, updated=excluded.updated, payload=excluded.payload",
                (session.id, session.title, utc_now(), session.model_dump_json()),
            )

    def load(self, session_id: str) -> Session:
        row = self.db.execute("SELECT payload FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise KeyError("Session not found")
        return Session.model_validate_json(row[0])

    def list(self) -> list[dict]:
        return [dict(id=r[0], title=r[1], updated=r[2]) for r in self.db.execute(
            "SELECT id,title,updated FROM sessions ORDER BY updated DESC"
        )]

    def close(self) -> None:
        self.db.close()
