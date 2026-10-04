"""Explicit five-second local capture check. Never uploads screen content.

Run from the repository root with ``python tools/verify_capture.py``. The output
is kept in .artifacts/capture-check.mp4 so it is ignored by Git.
"""

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import cv2
from apprentice.capture import Capture


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    recorder = Capture(interval=1)
    samples, errors = [], []
    recorder.sampled.connect(lambda image, timestamp: samples.append(timestamp))
    recorder.failed.connect(errors.append)
    path = Path(".artifacts/capture-check.mp4").resolve()
    path.parent.mkdir(exist_ok=True)
    recorder.start(0, path, time.monotonic())
    QTimer.singleShot(5000, recorder.stop)
    QTimer.singleShot(6500, app.quit)
    app.exec()
    if errors:
        print("Capture errors:", errors)
        return 1
    video = cv2.VideoCapture(str(path))
    ok, _frame = video.read()
    duration = video.get(cv2.CAP_PROP_FRAME_COUNT) / max(1, video.get(cv2.CAP_PROP_FPS))
    video.release()
    print(f"Capture check: playable={ok}, samples={len(samples)}, duration={duration:.2f}s")
    return 0 if ok and samples and duration > 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
