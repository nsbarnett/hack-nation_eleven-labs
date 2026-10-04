"""Headless Qt fixtures: no desktop capture, microphone, or paid API calls."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def controller(qapp, tmp_path):
    from apprentice.config import Settings
    from apprentice.controller import Controller
    from apprentice.store import SessionStore
    obj = Controller(Settings(), SessionStore(tmp_path), timers=False)
    yield obj
    obj.shutdown()
