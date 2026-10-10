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
    DEFAULT_VOICE_FEMALE = "su-ID-TutiNeural"

    def __init__(
        self,
        default_male: str = "id-ID-ArdiNeural",
        default_female: str = "su-ID-TutiNeural",
        female_rate: str = "+18%",
        female_pitch: str = "+1Hz",
        male_rate: str = "+0%",
        male_pitch: str = "+0Hz",
        elevenlabs_fallback_key: str = "",
        elevenlabs_fallback_model: str = "eleven_flash_v2_5",
    ):
        self._default_male = default_male
        self._default_female = default_female
        self._female_rate = female_rate
        self._female_pitch = female_pitch
        self._male_rate = male_rate
        self._male_pitch = male_pitch
        self._elevenlabs_key = elevenlabs_fallback_key
        self._elevenlabs_model = elevenlabs_fallback_model

    async def synthesize(self, text: str, voice: str) -> bytes:
        import edge_tts

        voice_id = (voice or "").strip()
        is_female = False

        # Support direct ElevenLabs voice ID if user configures one
        if len(voice_id) >= 18 and voice_id.isalnum() and "-" not in voice_id and self._elevenlabs_key:
            try:
                el_provider = ElevenLabsTTSProvider(api_key=self._elevenlabs_key, model_id=self._elevenlabs_model)
                return await el_provider.synthesize(text, voice_id)
            except Exception as e:
                logger.warning("ElevenLabs fallback failed for voice '%s', falling back to Edge TTS: %s", voice_id, e)

        if not voice_id or voice_id in ("male_voice", "male", "persona_a", "raka"):
            voice_id = self._default_male
        elif voice_id in ("female_voice", "female", "persona_b", "salsa"):
            voice_id = self._default_female
            is_female = True
        elif any(k in voice_id.lower() for k in ("salsa", "female", "gadis", "tuti", "siti", "yasmin", "exav", "kore", "sarah")):
            is_female = True
            # If not an explicit Edge TTS voice model tag (e.g. su-ID-TutiNeural), default to female
            if not ("-" in voice_id and "Neural" in voice_id):
                voice_id = self._default_female
        elif not ("-" in voice_id and "Neural" in voice_id):
            voice_id = self._default_male

        # Check gender by voice identifier if not already flagged
        if any(female_kw in voice_id.lower() for female_kw in ("tuti", "gadis", "siti", "yasmin", "female")):
            is_female = True

        rate = self._female_rate if is_female else self._male_rate
        pitch = self._female_pitch if is_female else self._male_pitch

        cleaned_text = text.replace("//", "... ").replace("/", ", ")
        communicate = edge_tts.Communicate(cleaned_text, voice_id, rate=rate, pitch=pitch)
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



class VoiceStudioTTSProvider(TTSProvider):
    """VoiceStudio local TTS provider using OpenAI-compatible HTTP endpoint.

    Connects to VoiceStudio server running on localhost (default :3900).
    Endpoint: POST /v1/audio/speech
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:3900",
        api_key: str = "",
        model: str = "tts-1",
        timeout_s: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s

    async def synthesize(self, text: str, voice: str) -> bytes:
        import httpx

        cleaned_text = text.replace("//", "... ").replace("/", ", ")
        voice_id = voice if voice else "default"

        payload = {
            "model": self._model,
            "input": cleaned_text,
            "voice": voice_id,
            "response_format": "wav",
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        url = f"{self._base_url}/v1/audio/speech"

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code != 200:
                    raise RuntimeError(
                        f"VoiceStudio TTS error {res.status_code}: {res.text}"
                    )
                audio_bytes = res.content
                if not audio_bytes:
                    raise RuntimeError("VoiceStudio returned empty audio")
                return audio_bytes
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to VoiceStudio at {self._base_url}. "
                f"Ensure VoiceStudio is running: {e}"
            ) from e

    @property
    def provider_name(self) -> str:
        return "voicestudio"

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
    voicestudio_url: str = "http://127.0.0.1:3900",
    voicestudio_api_key: str = "",
    voicestudio_model: str = "tts-1",
    edge_voice_male: str = "id-ID-ArdiNeural",
    edge_voice_female: str = "su-ID-TutiNeural",
    edge_rate_female: str = "+18%",
    edge_pitch_female: str = "+1Hz",
    edge_rate_male: str = "+0%",
    edge_pitch_male: str = "+0Hz",
) -> TTSProvider:
    """Create TTS provider based on config.

    Args:
        mode: "live" or "mock".
        provider: "gemini", "elevenlabs", "edge", or "voicestudio".
        api_key: API key for the provider.
        model: Model ID for Gemini TTS.
        cache_dir: Directory for audio cache.
        enable_cache: Whether to wrap in cache layer.
        elevenlabs_model: Model ID for ElevenLabs TTS.
        voicestudio_url: Base URL of local VoiceStudio server.
        voicestudio_api_key: Optional Bearer token for VoiceStudio.
        voicestudio_model: Model/engine identifier for VoiceStudio.
        edge_voice_male: Voice identifier for Edge TTS male speaker.
        edge_voice_female: Voice identifier for Edge TTS female speaker.
        edge_rate_female: Rate modifier for Edge TTS female speaker.
        edge_pitch_female: Pitch modifier for Edge TTS female speaker.
        edge_rate_male: Rate modifier for Edge TTS male speaker.
        edge_pitch_male: Pitch modifier for Edge TTS male speaker.

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
        inner = EdgeTTSProvider(
            default_male=edge_voice_male,
            default_female=edge_voice_female,
            female_rate=edge_rate_female,
            female_pitch=edge_pitch_female,
            male_rate=edge_rate_male,
            male_pitch=edge_pitch_male,
            elevenlabs_fallback_key=api_key or "",
            elevenlabs_fallback_model=elevenlabs_model,
        )
    elif provider in ("voicestudio", "voice_studio", "omni", "omnivoice"):
        inner = VoiceStudioTTSProvider(
            base_url=voicestudio_url,
            api_key=voicestudio_api_key,
            model=voicestudio_model,
        )
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")

    if enable_cache:
        cache = AudioCache(cache_dir)
        return CachedTTSProvider(inner, cache)

    return inner
