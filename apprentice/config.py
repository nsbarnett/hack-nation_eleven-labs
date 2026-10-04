"""Load credentials locally; never serialize them into session records."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_key: str = ""
    model: str = "gpt-4.1"
    eleven_key: str = ""
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    speech_model: str = "eleven_flash_v2_5"
    transcription_model: str = "scribe_v1"
    sample_seconds: float = 2.0
    analysis_seconds: float = 10.0

    @classmethod
    def load(cls, project: Path) -> "Settings":
        load_dotenv(project / ".env", override=False)
        return cls(
            openai_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
            eleven_key=os.getenv("ELEVENLABS_API_KEY", ""),
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
            speech_model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"),
            transcription_model=os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1"),
        )
