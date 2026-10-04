"""Bootstrap Qt, persistent storage, the controller, and the QML scene.

Run ``python main.py --demo`` for the fictional offline learning loop. The
``--smoke`` and ``--snapshot`` switches validate/render our own UI without
recording the desktop, enabling repeatable checks without provider calls.
"""

import argparse
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Apprentice desktop application")
    parser.add_argument("--demo", action="store_true", help="Open a fictional offline Work Map")
    parser.add_argument("--data-dir", type=Path, help="Override the OS application-data directory")
    parser.add_argument("--smoke", action="store_true", help="Load the QML scene and exit after validation; no recording")
    parser.add_argument("--snapshot", type=Path, help="Save a screenshot of this application's UI and exit")
    parser.add_argument("--page", choices=["Overview", "Capture", "Work Map", "Teach", "Evidence", "Library", "Settings"], help="Initial page")
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PySide6.QtCore import QStandardPaths, QTimer, QUrl, Qt
    from PySide6.QtGui import QColor, QFontDatabase, QIcon, QPainter, QPen, QPixmap
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    from apprentice.config import Settings
    from apprentice.controller import Controller
    from apprentice.platforms import exclude_window
    from apprentice.store import SessionStore

    app = QApplication([sys.argv[0]])
    app.setApplicationName("AI Apprentice")
    app.setOrganizationName("AI Apprentice")
    app.setQuitOnLastWindowClosed(False)
    # The headless Windows platform has no system font discovery. Register fonts
    # explicitly for reproducible UI screenshots; normal desktop rendering uses
    # the operating system's font database.
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" and sys.platform == "win32":
        for filename in ("segoeui.ttf", "seguisb.ttf", "seguisym.ttf", "consola.ttf"):
            font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
            if font_path.is_file():
                QFontDatabase.addApplicationFont(str(font_path))
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    data = args.data_dir or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    backend = Controller(Settings.load(root), SessionStore(data))
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda messages: errors.extend(str(m.toString()) for m in messages))
    engine.rootContext().setContextProperty("backend", backend)
    engine.addImageProvider("screen", backend.preview)
    qml = Path(__file__).parent / "ui" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        backend.shutdown()
        print("QML startup failed:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    window = engine.rootObjects()[0]
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#191a1d"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(3, 3, 58, 58)
    pen = QPen(QColor("white"), 3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for x, top, bottom in ((17,28,36),(24,21,43),(32,16,48),(40,24,40),(47,29,35)):
        painter.drawLine(x, top, x, bottom)
    painter.end()
    app.setWindowIcon(QIcon(pixmap))
    tray = QSystemTrayIcon(QIcon(pixmap), app)
    tray.setToolTip("AI Apprentice")
    menu = QMenu()
    menu.addAction("Open AI Apprentice", backend.reveal)
    menu.addAction("Stop recording", backend.stopRecording)
    menu.addSeparator()
    menu.addAction("Quit", backend.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda _reason: backend.reveal())
    if QSystemTrayIcon.isSystemTrayAvailable() and not (args.smoke or args.snapshot):
        tray.show()
    if args.demo:
        backend.loadDemo()
    if args.page:
        window.setProperty("page", args.page)

    def protect_windows():
        for w in app.allWindows():
            exclude_window(int(w.winId()))
    QTimer.singleShot(500, protect_windows)
    exit_code = [0]

    def validate():
        if args.snapshot:
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grabWindow().save(str(args.snapshot)):
                errors.append("Could not save the UI screenshot")
        if errors:
            print("\n".join(errors), file=sys.stderr)
            exit_code[0] = 1
        else:
            print("PASS: QML scene loaded without warnings; no recording or API calls performed.")
        app.quit()
    if args.smoke or args.snapshot:
        QTimer.singleShot(1600, validate)
    try:
        app.exec()
    finally:
        tray.hide()
        del engine
        backend.shutdown()
    return exit_code[0]
