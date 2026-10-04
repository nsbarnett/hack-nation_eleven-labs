"""Correlated operational logs without request bodies, credentials or provider text."""
import json
import logging
import re
import subprocess
import time
import traceback
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

VERSION = "0.5.0"
request_id = ContextVar("request_id", default="")
job_id = ContextVar("job_id", default="")
logger = logging.getLogger("uvicorn.error")


@lru_cache(maxsize=1)
def revision():
    try:
        value = subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).resolve().parents[1], stderr=subprocess.DEVNULL, timeout=2, text=True).strip()
        return value if re.fullmatch(r"[0-9a-f]{7,40}", value) else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def failure(error):
    status = getattr(error, "status_code", None) or getattr(getattr(error, "response", None), "status_code", None)
    return {"error_type": type(error).__name__,
            "cause_type": type(error.__cause__).__name__ if error.__cause__ else None,
            "provider_status": status if isinstance(status, int) else None,
            "trace": [{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                      for frame in traceback.extract_tb(error.__traceback__)[-8:]]}


def log(event, *, level=logging.INFO, **fields):
    logger.log(level, "apprentice %s", json.dumps({"timestamp": time.time(), "event": event,
        "request_id": request_id.get() or None, "job_id": job_id.get() or None, **fields}, separators=(",", ":")))
