"""Unit tests for TTS provider and pause markers."""

import unittest
from pathlib import Path
import tempfile

from unittest.mock import AsyncMock, patch, MagicMock
from app.tts.provider import (
    MockTTSProvider,
    AudioCache,
    split_on_pauses,
    VoiceStudioTTSProvider,
    create_tts_provider,
)


class TestTTS(unittest.IsolatedAsyncioTestCase):
    def test_split_on_pauses(self):
        text = "Halo pendengar! / Selamat datang di HITS Radio. // Kita ada info seru nih."
        segments = split_on_pauses(text)

        self.assertEqual(len(segments), 5)
        self.assertEqual(segments[0], {"type": "text", "value": "Halo pendengar!"})
        self.assertEqual(segments[1], {"type": "pause", "value": 400})
        self.assertEqual(segments[2], {"type": "text", "value": "Selamat datang di HITS Radio."})
        self.assertEqual(segments[3], {"type": "pause", "value": 900})
        self.assertEqual(segments[4], {"type": "text", "value": "Kita ada info seru nih."})

    async def test_mock_tts_synthesize(self):
        provider = MockTTSProvider()
        text = "Halo selamat pagi! / Semangat ya!"
        voice = "male_voice"

        audio_bytes = await provider.synthesize(text, voice)
        self.assertIsInstance(audio_bytes, bytes)
        self.assertTrue(len(audio_bytes) > 0)
        self.assertTrue(audio_bytes.startswith(b"RIFF"))  # Valid WAV header

    def test_audio_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = AudioCache(cache_dir=temp_dir)
            text = "Halo selamat pagi!"
            voice = "male_voice"
            provider = "mock"
            fake_audio = b"RIFFfakeaudio"

            # Cache miss initially
            self.assertIsNone(cache.get(text, voice, provider))

            # Store in cache
            saved_path = cache.put(text, voice, provider, fake_audio)
            self.assertTrue(saved_path.exists())

            # Cache hit
            cached = cache.get(text, voice, provider)
            self.assertEqual(cached, fake_audio)

    async def test_voicestudio_tts_synthesize_mock_http(self):
        provider = VoiceStudioTTSProvider(
            base_url="http://127.0.0.1:3900",
            api_key="test_key",
            model="tts-1",
        )
        fake_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_wav

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            audio = await provider.synthesize("Halo / dunia", "female_voice")
            self.assertEqual(audio, fake_wav)
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["voice"], "female_voice")
            self.assertEqual(call_kwargs["json"]["input"], "Halo ,  dunia")
            self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer test_key")

    def test_create_tts_provider_voicestudio(self):
        p = create_tts_provider(
            mode="live",
            provider="voicestudio",
            voicestudio_url="http://localhost:3900",
            voicestudio_model="tts-1",
            enable_cache=False,
        )
        self.assertIsInstance(p, VoiceStudioTTSProvider)
        self.assertEqual(p.provider_name, "voicestudio")


if __name__ == "__main__":
    unittest.main()
