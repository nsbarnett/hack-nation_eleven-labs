"""Exercise real QML bindings and user-action handlers against the controller."""

from pathlib import Path

from PySide6.QtCore import QObject, QMetaObject, QPoint, QUrl, Qt
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest


def test_qml_pages_and_practice_flow(qapp, controller):
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
    engine.rootContext().setContextProperty("backend", controller)
    engine.addImageProvider("screen", controller.preview)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "apprentice/ui/Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    controller.loadDemo()
    for page in ("Overview", "Capture", "Work Map", "Evidence", "Library", "Settings", "Teach"):
        window.setProperty("page", page)
        QTest.qWait(30)
    controller.confirmMap()
    review = window.findChild(QObject, "reviewCaseButton")
    save = window.findChild(QObject, "savePracticeButton")
    assert review.property("enabled")
    QMetaObject.invokeMethod(review, "clicked", Qt.ConnectionType.DirectConnection)
    QTest.qWait(30)
    assert not save.property("enabled")
    window.findChild(QObject, "caseCategory").setProperty("currentIndex", 1)
    window.findChild(QObject, "caseAsset").setProperty("text", "ASSET-200")
    QMetaObject.invokeMethod(review, "clicked", Qt.ConnectionType.DirectConnection)
    QTest.qWait(30)
    assert save.property("enabled")
    QMetaObject.invokeMethod(save, "clicked", Qt.ConnectionType.DirectConnection)
    assert controller.session.evidence[-1].kind == "trainee_attempt"
    # Changing a value clears the previous acceptance immediately.
    window.findChild(QObject, "caseCategory").setProperty("currentIndex", 0)
    QTest.qWait(30)
    assert not save.property("enabled")
    assert not warnings, warnings
    window.hide()
    del engine


def test_companion_expansion_and_actions(qapp, controller, monkeypatch):
    """The orb remains anchored; its controls still operate the shared session."""
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
    engine.rootContext().setContextProperty("backend", controller)
    engine.addImageProvider("screen", controller.preview)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "apprentice/ui/Main.qml")))
    window = engine.rootObjects()[0]
    controller.newSession("Companion test", "", 0, False)
    bubble = window.findChild(QObject, "bubbleWindow")
    orb = bubble.findChild(QObject, "companionOrb")
    bubble.setProperty("dockX", 400)
    bubble.setProperty("y", 50)
    bubble.setProperty("visible", True)
    QTest.qWait(50)
    before = bubble.x() + orb.x()
    QTest.mouseClick(bubble, Qt.MouseButton.LeftButton, pos=QPoint(int(orb.x()+34), 80))
    QTest.qWait(300)
    assert bubble.property("expanded") and bubble.width() > 300
    assert abs(bubble.x() + orb.x() - before) < 2
    dock_before = bubble.property("dockX")
    start = QPoint(int(orb.x()+34), 80)
    QTest.mousePress(bubble, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(bubble, start + QPoint(20, 10), delay=20)
    QTest.mouseRelease(bubble, Qt.MouseButton.LeftButton, pos=start + QPoint(20, 10))
    assert bubble.property("dockX") > dock_before
    assert bubble.property("expanded")  # Dragging must not collapse the bar.
    mute = bubble.findChild(QObject, "companionMute")
    QMetaObject.invokeMethod(mute, "clicked", Qt.ConnectionType.DirectConnection)
    assert not controller.prompts
    QMetaObject.invokeMethod(mute, "clicked", Qt.ConnectionType.DirectConnection)
    assert controller.prompts
    monkeypatch.setattr(controller.capture, "start", lambda *args: None)
    monkeypatch.setattr(controller.capture, "stop", lambda: None)
    record = bubble.findChild(QObject, "companionRecord")
    QMetaObject.invokeMethod(record, "clicked", Qt.ConnectionType.DirectConnection)
    assert controller.recording
    QMetaObject.invokeMethod(record, "clicked", Qt.ConnectionType.DirectConnection)
    assert not controller.recording
    # Near the left edge, controls expand to the right instead of leaving screen.
    bubble.setProperty("expanded", False)
    QTest.qWait(300)
    bubble.setProperty("dockX", 10)
    QMetaObject.invokeMethod(bubble, "toggleExpanded", Qt.ConnectionType.DirectConnection)
    QTest.qWait(300)
    assert not bubble.property("expandLeft") and bubble.x() == 10
    assert not warnings, warnings
    window.hide()
    bubble.hide()
    del engine


def test_themed_dialog_standard_buttons_still_close(qapp, controller):
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", controller)
    engine.addImageProvider("screen", controller.preview)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "apprentice/ui/Main.qml")))
    window = engine.rootObjects()[0]
    dialog = window.findChild(QObject, "newSessionDialog")
    QMetaObject.invokeMethod(dialog, "open", Qt.ConnectionType.DirectConnection)
    QTest.qWait(180)
    assert dialog.property("visible")
    # The customized DialogButtonBox must preserve standard reject behavior.
    cancel = next(o for o in dialog.findChildren(QObject) if o.property("text") == "Cancel" and o.inherits("QQuickAbstractButton"))
    QMetaObject.invokeMethod(cancel, "clicked", Qt.ConnectionType.DirectConnection)
    QTest.qWait(180)
    assert not dialog.property("visible")
    window.hide()
    del engine
