"""On-demand microphone capture and small ElevenLabs HTTP adapters.

No microphone opens at startup. PCM remains in memory until a user-approved
answer is transcribed; generated speech is played from a memory buffer.
"""

import io
import time
import wave

import httpx
import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioSource, QMediaDevices, QMediaPlayer


class ElevenVoice:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    def _client(self):
        if not self.settings.eleven_key:
            raise ValueError("Configure ELEVENLABS_API_KEY to use voice.")
        return httpx.Client(base_url="https://api.elevenlabs.io/v1/", timeout=30,
                            headers={"xi-api-key": self.settings.eleven_key}, transport=self.transport)

    def speak(self, text: str) -> bytes:
        from urllib.parse import quote
        with self._client() as client:
            response = client.post("text-to-speech/" + quote(self.settings.voice_id, safe=""),
                params={"output_format": "mp3_44100_128"},
                json={"text": text[:3000], "model_id": self.settings.speech_model})
            response.raise_for_status()
            return response.content

    def transcribe(self, wav: bytes) -> str:
        with self._client() as client:
            response = client.post("speech-to-text", data={"model_id": self.settings.transcription_model},
                                   files={"file": ("answer.wav", wav, "audio/wav")})
            response.raise_for_status()
            return str(response.json().get("text", "")).strip()


class Audio(QObject):
    captured = Signal(bytes)
    changed = Signal()
    failed = Signal(str)
    speechFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.source = None
        self.device = None
        self.pcm = bytearray()
        self.listening = False
        self.heard_speech = False
        self.started = self.last_sound = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._check_silence)
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(lambda _e, text: self.failed.emit(text))
        self.buffer = None

    @property
    def speaking(self):
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def listen(self):
        self.cancel()
        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            self.failed.emit("No microphone is available.")
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt):
            self.failed.emit("This microphone does not support 16 kHz mono PCM. Choose another input in system settings.")
            return
        self.source = QAudioSource(device, fmt, self)
        self.device = self.source.start()
        if self.device is None:
            self.failed.emit("Microphone access failed. Check system permission settings.")
            self.source.deleteLater()
            self.source = None
            return
        self.listening = True
        self.pcm = bytearray()
        self.heard_speech = False
        self.started = self.last_sound = time.monotonic()
        self.device.readyRead.connect(self._read)
        self.timer.start()
        self.changed.emit()

    def _read(self):
        if not self.listening or not self.device:
            return
        chunk = bytes(self.device.readAll())
        self.pcm.extend(chunk)
        usable = len(chunk) // 2 * 2
        if usable:
            samples = np.frombuffer(chunk[:usable], dtype=np.int16).astype(np.float32)
            if float(np.sqrt(np.mean(samples * samples))) > 450:
                self.heard_speech = True
                self.last_sound = time.monotonic()

    def _check_silence(self):
        now = time.monotonic()
        if now - self.started >= 30 or (self.heard_speech and now - self.last_sound >= 2):
            self.finish()

    def finish(self):
        if not self.listening:
            return
        self._read()
        data = bytes(self.pcm)
        heard = self.heard_speech
        self.cancel()
        if not heard:
            self.failed.emit("No speech detected. You can type the answer or try again.")
            return
        stream = io.BytesIO()
        with wave.open(stream, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(data)
        self.captured.emit(stream.getvalue())

    def play(self, mp3: bytes):
        self.cancel()
        self.buffer = QBuffer(self)
        self.buffer.setData(QByteArray(mp3))
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.player.setSourceDevice(self.buffer, QUrl("speech.mp3"))
        self.player.play()
        self.changed.emit()

    def _media_status(self, status):
        self.changed.emit()
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.speechFinished.emit()

    def cancel(self):
        self.timer.stop()
        self.player.stop()
        self.player.setSource(QUrl())
        if self.buffer:
            self.buffer.close()
            self.buffer.deleteLater()
            self.buffer = None
        if self.source:
            self.source.stop()
            self.source.deleteLater()
            self.source = None
        self.device = None
        self.listening = False
        self.pcm = bytearray()
        self.changed.emit()
