"""Verify guest isolation and restart persistence against DATABASE_URL.

Creates one disposable session under a fresh random guest, then removes only that
session. Run in the Replit development workspace before publishing.
"""
import asyncio
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apprentice.domain import Session
from backend.hosted_store import HostedDatabase, GuestRepository


async def main():
    url = os.environ["DATABASE_URL"]
    guest = secrets.token_hex(16)
    session = Session(title="Disposable PostgreSQL verification")
    database = HostedDatabase(url)
    try:
        owner = GuestRepository(database, guest)
        await owner.save(session)
        assert (await owner.load(session.id)).title == session.title
        other = GuestRepository(database, secrets.token_hex(16))
        try:
            await other.load(session.id)
            raise AssertionError("Cross-guest access must fail")
        except KeyError:
            pass
        await database.close()
        database = HostedDatabase(url)
        owner = GuestRepository(database, guest)
        assert (await owner.load(session.id)).id == session.id
        print("PASS: database write/read, guest isolation, and reconnect persistence", flush=True)
    finally:
        await GuestRepository(database, guest).delete(session.id)
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
