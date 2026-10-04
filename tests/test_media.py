"""Real Qt/FFmpeg encoding test using generated frames, not the user's screen."""

import time

import cv2
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QColor
from PySide6.QtMultimedia import QMediaCaptureSession, QMediaFormat, QMediaRecorder, QVideoFrame, QVideoFrameInput
from PySide6.QtTest import QTest


def test_real_mp4_encoding_and_finalization(qapp, tmp_path):
    pipeline = QMediaCaptureSession()
    source = QVideoFrameInput()
    recorder = QMediaRecorder()
    pipeline.setVideoFrameInput(source)
    pipeline.setRecorder(recorder)
    fmt = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
    fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
    recorder.setMediaFormat(fmt)
    recorder.setVideoFrameRate(10)
    recorder.setVideoResolution(320, 180)
    path = tmp_path / "synthetic.mp4"
    recorder.setOutputLocation(QUrl.fromLocalFile(str(path)))
    errors = []
    recorder.errorOccurred.connect(lambda _code, text: errors.append(text))
    recorder.record()
    sent = 0
    deadline = time.monotonic() + 8
    while sent < 15 and time.monotonic() < deadline:
        image = QImage(320, 180, QImage.Format.Format_RGBA8888)
        image.fill(QColor.fromHsv(sent * 20, 150, 200))
        frame = QVideoFrame(image)
        frame.setStartTime(sent * 100_000)
        frame.setEndTime((sent + 1) * 100_000)
        if source.sendVideoFrame(frame):
            sent += 1
        QTest.qWait(30)
    recorder.stop()
    deadline = time.monotonic() + 5
    while recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState and time.monotonic() < deadline:
        QTest.qWait(50)
    assert not errors, errors
    assert sent == 15 and path.is_file()
    video = cv2.VideoCapture(str(path))
    ok, frame = video.read()
    video.release()
    assert ok and frame.shape[:2] == (180, 320)
