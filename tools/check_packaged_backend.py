"""Smoke-test the real frozen service without importing the source backend."""
import json
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
import sys
import httpx

root = Path(__file__).resolve().parents[1]
executable = root / "dist" / "backend" / ("apprentice-backend.exe" if sys.platform == "win32" else "apprentice-backend")
with tempfile.TemporaryDirectory(prefix="apprentice-sidecar-") as data:
    token = secrets.token_hex(32)
    process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, cwd=data)
    try:
        process.stdin.write(json.dumps({"token": token, "root": data}) + "\n")
        process.stdin.close()
        line = process.stdout.readline()
        if not line:
            raise RuntimeError(process.stderr.read())
        port = json.loads(line)["port"]
        for attempt in range(80):
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/state", headers={"Authorization": f"Bearer {token}"}, timeout=2)
                response.raise_for_status()
                assert response.json()["sessions"] == []
                assert not response.json()["credentials"]["openai"]
                print("Frozen backend: authenticated empty startup passed; no source environment or credentials required.")
                break
            except httpx.ConnectError:
                time.sleep(.1)
        else:
            raise RuntimeError("Frozen service did not become ready")
    finally:
        process.terminate()
        process.wait(timeout=10)
