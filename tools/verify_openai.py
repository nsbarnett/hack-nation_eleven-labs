"""Explicit, billable provider check using only a synthetic screenshot fixture.

No desktop image, session evidence, or personal context is sent. Credentials are
loaded normally but never printed. This script is NOT part of the default tests.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QImage, QColor
from apprentice.agents.observer import Observer
from apprentice.agents.gateway import Gateway
from apprentice.config import Settings
from apprentice.domain import Evidence, Session


def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings.load(root)
    if not settings.openai_key:
        print("SKIP: OPENAI_API_KEY is not configured")
        return 2
    image = QImage(320, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("#dae7d1"))
    path = root / ".artifacts" / "synthetic-ai-check.jpg"
    path.parent.mkdir(exist_ok=True)
    image.save(str(path))
    evidence = Evidence(kind="screen", text="Synthetic uniform-color test image; no application action occurred.")
    session = Session(title="Transport validation", context="A synthetic blank screen; return no actions unless actual evidence supports them.", evidence=[evidence])
    try:
        result = Observer(Gateway(settings)).run(session, [(evidence.id, path)])
        print(f"PASS: live structured response validated; actions={len(result)}")
        return 0
    except Exception as exc:
        print(f"Provider validation failed: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
