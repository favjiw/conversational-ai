"""Application configuration loaded from environment variables.

All config values come from .env (never hardcoded). See .env.example for the
full list of supported variables.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATHS = (
    str(_ROOT / ".env"),
    str(Path(".env").resolve()),
    ".env",
)


class Settings(BaseSettings):
    """Central settings read once at startup."""

    # --- Gemini API ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_PARSER: str = "gemini-flash-latest"
    GEMINI_MODEL_PERSONA: str = "gemini-flash-latest"
    GEMINI_MODEL_SUPERVISOR: str = "gemini-3.5-flash-lite"
    GEMINI_MODEL_EMOTION: str = "gemini-3.5-flash-lite"
    GEMINI_MODEL_JUDGE: str = "gemini-flash-latest"
    GEMINI_MODEL_TTS: str = "gemini-3.8-flash-tts"

    # --- TTS ---
    TTS_PROVIDER: Literal["gemini", "elevenlabs", "edge", "voicestudio"] = "edge"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"
    ELEVENLABS_VOICE_A: str = "JBFqnCBsd6RMkjVDRZzb"
    ELEVENLABS_VOICE_B: str = "EXAVITQu4vr4xnSDxMaL"
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"
    EDGE_VOICE_MALE: str = "id-ID-ArdiNeural"
    EDGE_VOICE_FEMALE: str = "su-ID-TutiNeural"
    EDGE_RATE_FEMALE: str = "+18%"
    EDGE_PITCH_FEMALE: str = "+1Hz"
    EDGE_RATE_MALE: str = "+0%"
    EDGE_PITCH_MALE: str = "+0Hz"
    VOICESTUDIO_URL: str = "http://127.0.0.1:3900"
    VOICESTUDIO_API_KEY: str = ""
    VOICESTUDIO_MODEL: str = "tts-1"

    # --- Modes ---
    LLM_MODE: Literal["live", "mock"] = "live"
    TTS_MODE: Literal["live", "mock"] = "live"
    MUSIC_PROVIDER: Literal["mock", "deezer"] = "deezer"

    # --- Testing ---
    FAIL_INJECT: str = ""  # llm | tts | music

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATA_DIR: str = "data"
    LOG_DIR: str = "logs"

    model_config = {
        "env_file": _ENV_PATHS,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()
