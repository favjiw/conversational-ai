"""ElevenLabs TTS with word timings (/with-timestamps) for avatar lip-sync."""

import base64
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tts.provider import ElevenLabsTTSProvider, alignment_to_word_timings


def _alignment(text: str, step: float = 0.1) -> dict:
    return {
        "characters": list(text),
        "character_start_times_seconds": [i * step for i in range(len(text))],
        "character_end_times_seconds": [(i + 1) * step for i in range(len(text))],
    }


class TestAlignment(unittest.TestCase):
    def test_groups_characters_into_words(self):
        words = alignment_to_word_timings(_alignment("Halo  sobat!"))
        self.assertEqual([w["text"] for w in words], ["Halo", "sobat!"])
        self.assertAlmostEqual(words[0]["offset_ms"], 0.0)
        self.assertAlmostEqual(words[0]["duration_ms"], 400.0)
        self.assertAlmostEqual(words[1]["offset_ms"], 600.0)
        self.assertAlmostEqual(words[1]["duration_ms"], 600.0)

    def test_missing_alignment_gives_no_timings(self):
        self.assertEqual(alignment_to_word_timings(None), [])


class TestElevenLabsTimings(unittest.IsolatedAsyncioTestCase):
    async def test_uses_with_timestamps_endpoint(self):
        body = {"audio_base64": base64.b64encode(b"ID3audio").decode(), "alignment": _alignment("Pagi HITS")}
        resp = MagicMock(status_code=200)
        resp.json.return_value = body
        post = AsyncMock(return_value=resp)
        with patch("httpx.AsyncClient.post", post):
            audio, timings = await ElevenLabsTTSProvider(api_key="k").synthesize_with_timings("Pagi / HITS", "male")
        self.assertEqual(audio, b"ID3audio")
        self.assertTrue(post.await_args.args[0].endswith("/with-timestamps"))
        # "/" pause marker becomes a comma before synthesis
        self.assertEqual(post.await_args.kwargs["json"]["text"], "Pagi ,  HITS")
        self.assertEqual([w["text"] for w in timings], ["Pagi", "HITS"])

    async def test_plain_synthesize_returns_audio_only(self):
        provider = ElevenLabsTTSProvider(api_key="k")
        with patch.object(provider, "synthesize_with_timings", AsyncMock(return_value=(b"mp3", []))):
            self.assertEqual(await provider.synthesize("hai", "female"), b"mp3")

    async def test_error_status_raises(self):
        resp = MagicMock(status_code=401, text="invalid key")
        with patch("httpx.AsyncClient.post", AsyncMock(return_value=resp)):
            with self.assertRaises(RuntimeError):
                await ElevenLabsTTSProvider(api_key="bad").synthesize_with_timings("hai", "JBFqnCBsd6RMkjVDRZzb")


if __name__ == "__main__":
    unittest.main()
