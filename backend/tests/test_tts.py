"""Unit tests for TTS provider and pause markers."""

import unittest
from pathlib import Path
import tempfile

from app.tts.provider import MockTTSProvider, AudioCache, split_on_pauses


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


if __name__ == "__main__":
    unittest.main()
