"""Qt-native screen recording with a low-rate sample stream for AI and preview.

Qt handles video timestamps and encoding. Pause finalizes a segment; resume opens
a new one, avoiding backend-dependent pause support and excluding private time.
"""

import time
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtMultimedia import QMediaCaptureSession, QMediaFormat, QMediaRecorder, QScreenCapture, QVideoSink
from PySide6.QtQuick import QQuickImageProvider


class PreviewProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self.image = QImage(1280, 720, QImage.Format.Format_RGB32)
        self.image.fill("#f3f4f6")

    def requestImage(self, image_id, size, requested_size):
        result = self.image.copy()
        if size:
            size.setWidth(result.width())
            size.setHeight(result.height())
        return result


class Capture(QObject):
    sampled = Signal(QImage, float)
    failed = Signal(str)
    finalized = Signal()

    def __init__(self, parent=None, interval=2.0):
        super().__init__(parent)
        self.interval = interval
        self.pipeline = QMediaCaptureSession(self)
        self.source = QScreenCapture(self)
        self.recorder = QMediaRecorder(self)
        self.sink = QVideoSink(self)
        self.pipeline.setScreenCapture(self.source)
        self.pipeline.setRecorder(self.recorder)
        self.pipeline.setVideoSink(self.sink)
        fmt = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
        fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
        self.recorder.setMediaFormat(fmt)
        self.recorder.setVideoFrameRate(10)
        self.recorder.setQuality(QMediaRecorder.Quality.NormalQuality)
        self.sink.videoFrameChanged.connect(self._frame)
        self.source.errorOccurred.connect(lambda _e, text: self.failed.emit(text))
        self.recorder.errorOccurred.connect(lambda _e, text: self.failed.emit(text))
        self.recorder.recorderStateChanged.connect(self._state)
        self.active = False
        self.last_sample = 0.0
        self.started = 0.0

    def start(self, monitor: int, destination: Path, session_started: float):
        if self.recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState:
            raise ValueError("The previous video segment is still finalizing. Try again in a moment.")
        screens = QGuiApplication.screens()
        if not 0 <= monitor < len(screens):
            raise ValueError("The selected screen is no longer connected.")
        self.source.setScreen(screens[monitor])
        self.recorder.setOutputLocation(QUrl.fromLocalFile(str(destination)))
        self.started = session_started
        self.last_sample = 0
        self.active = True
        self.source.start()
        self.recorder.record()

    def stop(self):
        self.active = False
        self.recorder.stop()
        self.source.stop()

    def _state(self, state):
        if state == QMediaRecorder.RecorderState.StoppedState:
            self.finalized.emit()

    def _frame(self, frame):
        now = time.monotonic()
        if not self.active or now - self.last_sample < self.interval or not frame.isValid():
            return
        self.last_sample = now
        image = frame.toImage()
        if image.isNull():
            return
        from PySide6.QtCore import Qt
        image = image.scaled(1280, 900, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.sampled.emit(image, now - self.started)
