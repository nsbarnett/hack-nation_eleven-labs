"""ElevenLabs transport independent of any desktop or audio framework."""
from urllib.parse import quote
import httpx


class ElevenVoice:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    def client(self):
        if not self.settings.eleven_key:
            raise ValueError("Add an ElevenLabs API key in Settings to use voice.")
        return httpx.Client(base_url="https://api.elevenlabs.io/v1/", timeout=30,
                            headers={"xi-api-key": self.settings.eleven_key}, transport=self.transport)

    def speak(self, text):
        with self.client() as client:
            response = client.post("text-to-speech/" + quote(self.settings.voice_id, safe=""),
                params={"output_format": "mp3_44100_128"},
                json={"text": text[:3000], "model_id": self.settings.speech_model})
            response.raise_for_status()
            return response.content

    def transcribe(self, audio):
        with self.client() as client:
            response = client.post("speech-to-text", data={"model_id": self.settings.transcription_model},
                                   files={"file": ("answer.webm", audio, "audio/webm")})
            response.raise_for_status()
            return str(response.json().get("text", "")).strip()
