"""TTS provider abstraction (FR-4).

Supports Gemini TTS, ElevenLabs, and Mock mode. Handles pause markers
(``/`` and ``//``), audio caching, and PCM→WAV conversion.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import struct
import time
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Pause processing ────────────────────────────────────────────────────────


SHORT_PAUSE_MS = 400
LONG_PAUSE_MS = 900
SAMPLE_RATE = 24000  # Typical for Gemini TTS


def generate_silence_wav(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Generate a WAV file of silence with the given duration."""
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def split_on_pauses(text: str) -> list[dict]:
    """Split text on pause markers into segments.

    ``//`` → long pause, ``/`` → short pause.
    Returns list of dicts: {"type": "text"|"pause", "value": str|int}
    """
    segments: list[dict] = []
    # Replace // first (longer match), then /
    # Split on // first
    parts = text.split("//")
    for i, part in enumerate(parts):
        # Within each part, split on /
        sub_parts = part.split("/")
        for j, sub in enumerate(sub_parts):
            sub = sub.strip()
            if sub:
                segments.append({"type": "text", "value": sub})
            if j < len(sub_parts) - 1:
                segments.append({"type": "pause", "value": SHORT_PAUSE_MS})
        if i < len(parts) - 1:
            segments.append({"type": "pause", "value": LONG_PAUSE_MS})

    return segments


# ── Audio cache ──────────────────────────────────────────────────────────────


class AudioCache:
    """File-based audio cache keyed by hash(text, voice, provider)."""

    def __init__(self, cache_dir: str | Path = "cache/tts"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, text: str, voice: str, provider: str) -> str:
        raw = f"{provider}:{voice}:{text}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, text: str, voice: str, provider: str) -> Optional[bytes]:
        """Return cached audio bytes or None."""
        key = self._key(text, voice, provider)
        path = self._cache_dir / f"{key}.wav"
        if path.exists():
            logger.debug("Cache hit: %s", key)
            return path.read_bytes()
        return None

    def put(self, text: str, voice: str, provider: str, audio: bytes) -> Path:
        """Store audio and return the file path."""
        key = self._key(text, voice, provider)
        path = self._cache_dir / f"{key}.wav"
        path.write_bytes(audio)
        logger.debug("Cached: %s (%d bytes)", key, len(audio))
        return path


# ── Provider interface ───────────────────────────────────────────────────────


class TTSProvider(ABC):
    """Abstract TTS provider interface."""

    @abstractmethod
    async def synthesize(self, text: str, voice: str) -> bytes:
        """Synthesize text to WAV audio bytes.

        Args:
            text: Text to speak (may contain / and // pause markers).
            voice: Voice identifier.

        Returns:
            WAV audio bytes.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


# ── Mock provider ────────────────────────────────────────────────────────────


class MockTTSProvider(TTSProvider):
    """Mock TTS that returns silence WAV files (``TTS_MODE=mock``)."""

    async def synthesize(self, text: str, voice: str) -> bytes:
        # Generate silence proportional to text length
        duration_ms = max(500, len(text) * 30)  # ~30ms per char
        await asyncio.sleep(0.05)  # Simulate latency
        return generate_silence_wav(duration_ms)

    @property
    def provider_name(self) -> str:
        return "mock"


# ── Gemini TTS provider ─────────────────────────────────────────────────────


class GeminiTTSProvider(TTSProvider):
    """Google Gemini TTS provider.

    Gemini TTS outputs raw PCM which must be wrapped in WAV headers.
    """

    def __init__(self, api_key: str, model: str = ""):
        self._api_key = api_key
        self._model = model

    async def synthesize(self, text: str, voice: str) -> bytes:
        # Process pause markers
        segments = split_on_pauses(text)
        audio_parts: list[bytes] = []

        for segment in segments:
            if segment["type"] == "pause":
                audio_parts.append(
                    generate_silence_wav(segment["value"])
                )
            else:
                pcm_data = await self._call_api(segment["value"], voice)
                wav_data = self._pcm_to_wav(pcm_data)
                audio_parts.append(wav_data)

        # Concatenate all WAV segments
        return self._concatenate_wavs(audio_parts)

    async def _call_api(self, text: str, voice: str) -> bytes:
        """Call Gemini TTS API and return raw PCM bytes."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self._model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )

        # Extract audio data from response
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    return part.inline_data.data

        raise RuntimeError("No audio data in Gemini TTS response")

    def _pcm_to_wav(
        self,
        pcm_data: bytes,
        sample_rate: int = SAMPLE_RATE,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """Wrap raw PCM data in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    def _concatenate_wavs(self, wav_list: list[bytes]) -> bytes:
        """Concatenate multiple WAV files into one."""
        if not wav_list:
            return generate_silence_wav(500)
        if len(wav_list) == 1:
            return wav_list[0]

        # Read all frames
        all_frames = b""
        params = None
        for wav_bytes in wav_list:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, "rb") as wf:
                if params is None:
                    params = wf.getparams()
                all_frames += wf.readframes(wf.getnframes())

        # Write combined
        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(all_frames)
        return out.getvalue()

    @property
    def provider_name(self) -> str:
        return "gemini"


# ── ElevenLabs TTS provider ──────────────────────────────────────────────────


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS provider using REST API with httpx."""

    DEFAULT_VOICE_MALE = "JBFqnCBsd6RMkjVDRZzb"  # George (Male premade voice)
    DEFAULT_VOICE_FEMALE = "EXAVITQu4vr4xnSDxMaL"  # Sarah (Female premade voice)

    def __init__(
        self,
        api_key: str,
        model_id: str = "eleven_flash_v2_5",
        default_voice: str = "EXAVITQu4vr4xnSDxMaL",
    ):
        self._api_key = api_key
        self._model_id = model_id
        self._default_voice = default_voice

    async def synthesize(self, text: str, voice: str) -> bytes:
        import httpx

        # Map generic voice names or use the provided voice ID
        voice_id = voice
        if not voice_id or voice_id in ("male_voice", "male"):
            voice_id = self.DEFAULT_VOICE_MALE
        elif voice_id in ("female_voice", "female"):
            voice_id = self.DEFAULT_VOICE_FEMALE or self._default_voice

        # Strip pause markers or replace them with ellipses/commas for natural pause in ElevenLabs
        cleaned_text = text.replace("//", "... ").replace("/", ", ")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": cleaned_text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (402, 404) and voice_id != self.DEFAULT_VOICE_MALE:
                logger.warning(
                    "ElevenLabs %d for voice '%s' (library voice requires paid tier), falling back to default voice '%s'",
                    resp.status_code,
                    voice_id,
                    self.DEFAULT_VOICE_MALE,
                )
                fallback_url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.DEFAULT_VOICE_MALE}"
                resp = await client.post(fallback_url, headers=headers, json=payload)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"ElevenLabs TTS failed ({resp.status_code}): {resp.text}"
                )
            return resp.content

    @property
    def provider_name(self) -> str:
        return "elevenlabs"


# ── Edge TTS provider ───────────────────────────────────────────────────────


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS provider using edge-tts (free, neural, unlimited)."""

    DEFAULT_VOICE_MALE = "id-ID-ArdiNeural"
    DEFAULT_VOICE_FEMALE = "id-ID-GadisNeural"

    def __init__(
        self,
        default_male: str = "id-ID-ArdiNeural",
        default_female: str = "id-ID-GadisNeural",
    ):
        self._default_male = default_male
        self._default_female = default_female

    async def synthesize(self, text: str, voice: str) -> bytes:
        import edge_tts

        voice_id = voice
        if not voice_id or voice_id in ("male_voice", "male", "persona_a"):
            voice_id = self._default_male
        elif voice_id in ("female_voice", "female", "persona_b"):
            voice_id = self._default_female
        elif not voice_id.startswith("id-"):
            if any(k in voice_id.lower() for k in ("salsa", "female", "exav", "kore", "gadis")):
                voice_id = self._default_female
            else:
                voice_id = self._default_male

        cleaned_text = text.replace("//", "... ").replace("/", ", ")
        communicate = edge_tts.Communicate(cleaned_text, voice_id)
        data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data.extend(chunk["data"])

        if not data:
            raise RuntimeError(f"Edge TTS produced empty audio for voice {voice_id}")
        return bytes(data)

    @property
    def provider_name(self) -> str:
        return "edge"


# ── Cached TTS wrapper ──────────────────────────────────────────────────────


class CachedTTSProvider(TTSProvider):
    """Wraps any TTSProvider with an AudioCache layer."""

    def __init__(self, inner: TTSProvider, cache: AudioCache):
        self._inner = inner
        self._cache = cache

    async def synthesize(self, text: str, voice: str) -> bytes:
        cached = self._cache.get(text, voice, self._inner.provider_name)
        if cached is not None:
            return cached

        audio = await self._inner.synthesize(text, voice)
        self._cache.put(text, voice, self._inner.provider_name, audio)
        return audio

    @property
    def provider_name(self) -> str:
        return f"cached_{self._inner.provider_name}"


# ── Factory ──────────────────────────────────────────────────────────────────


def create_tts_provider(
    mode: str,
    provider: str = "gemini",
    api_key: str = "",
    model: str = "",
    cache_dir: str = "cache/tts",
    enable_cache: bool = True,
    elevenlabs_model: str = "eleven_flash_v2_5",
) -> TTSProvider:
    """Create TTS provider based on config.

    Args:
        mode: "live" or "mock".
        provider: "gemini" or "elevenlabs".
        api_key: API key for the provider.
        model: Model ID for Gemini TTS.
        cache_dir: Directory for audio cache.
        enable_cache: Whether to wrap in cache layer.
        elevenlabs_model: Model ID for ElevenLabs TTS.

    Returns:
        A TTSProvider instance.
    """
    if mode == "mock":
        inner: TTSProvider = MockTTSProvider()
    elif provider == "gemini":
        if not api_key:
            raise ValueError("GEMINI_API_KEY required for TTS_MODE=live")
        inner = GeminiTTSProvider(api_key=api_key, model=model)
    elif provider == "elevenlabs":
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY required when TTS_PROVIDER=elevenlabs")
        inner = ElevenLabsTTSProvider(api_key=api_key, model_id=elevenlabs_model)
    elif provider in ("edge", "edge_tts", "edge-tts"):
        inner = EdgeTTSProvider()
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")

    if enable_cache:
        cache = AudioCache(cache_dir)
        return CachedTTSProvider(inner, cache)

    return inner
