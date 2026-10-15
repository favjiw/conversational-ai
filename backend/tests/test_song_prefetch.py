"""Tests for preparing song slots ahead of air time, and TTS/music fallbacks."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.music.models import MusicTrack
from app.music.provider import DeezerMusicProvider
from app.orchestrator.clock_runner import ClockRunner
from app.schemas import Clock, PersonaCard, Slot, SlotSource, SlotType
from app.tts.provider import EdgeTTSProvider


def _persona(pid: str, name: str) -> PersonaCard:
    return PersonaCard(id=pid, name=name, gender="male", voice="v", speaking_style="santai")


def _clock() -> Clock:
    return Clock(show="t", duration_min=1, slots=[
        Slot(id="j1", order=1, type=SlotType.JINGLE, source=SlotSource.STATIC_AUDIO),
        Slot(id="s1", order=2, type=SlotType.SONG, source=SlotSource.MUSIC_API, category="indo"),
        Slot(id="s2", order=3, type=SlotType.SONG, source=SlotSource.MUSIC_API, category="barat"),
    ])


def _runner(broadcast=None) -> ClockRunner:
    music = AsyncMock()
    music.search.return_value = [MusicTrack(
        id="1", title="Lantas", artist="Juicy Luicy", preview_url="https://x/p.mp3", category="indo",
    )]
    llm = AsyncMock()
    llm.generate.return_value = SimpleNamespace(raw="Kalimat penyiar yang cukup panjang.")
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"\x00" * 12000)
    tts.provider_name = "mock"
    return ClockRunner(
        clock=_clock(),
        persona_a=_persona("persona_a", "Raka"),
        persona_b=_persona("persona_b", "Salsa"),
        llm_client=llm,
        tts_provider=tts,
        music_provider=music,
        broadcast_fn=broadcast,
        demo_music_sec=1,
    )


class TestSongPrefetch(unittest.IsolatedAsyncioTestCase):
    async def test_schedules_only_the_next_song(self):
        runner = _runner()
        runner._schedule_song_prep(0)
        self.assertEqual(list(runner._song_prep), ["s1"])
        runner._schedule_song_prep(0)  # idempotent
        self.assertEqual(list(runner._song_prep), ["s1"])
        runner._cancel_song_prep()

    async def test_prepared_song_has_intro_and_outro_audio(self):
        runner = _runner()
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual(prepared.track.title, "Lantas")
        self.assertIsNotNone(prepared.intro.audio_url)
        self.assertIsNotNone(prepared.outro.audio_url)
        self.assertNotEqual(prepared.intro.speaker.id, prepared.outro.speaker.id)
        self.assertEqual(runner.tts.synthesize.await_count, 2)

    async def test_song_slot_uses_prepared_result_without_new_work(self):
        events = []

        async def broadcast(event):
            events.append(event)
            if "playback_id" in event["data"]:
                runner.playback_feedback({**event["data"], "state": "ended"})

        runner = _runner(broadcast)
        slot = runner.clock.slots[1]
        runner._schedule_song_prep(1)
        await runner._song_prep["s1"]
        searches = runner.music.search.await_count

        await asyncio.wait_for(runner._handle_song_slot(slot, 1), timeout=2)

        self.assertEqual(runner.music.search.await_count, searches)
        self.assertEqual([e["type"] for e in events], ["turn", "clock_music", "turn"])
        self.assertNotIn("s1", runner._song_prep)

    async def test_stop_cancels_preparation(self):
        runner = _runner()
        runner._state = runner._state.RUNNING
        runner._schedule_song_prep(0)
        task = runner._song_prep["s1"]
        await runner.stop()
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled() or task.done())
        self.assertEqual(runner._song_prep, {})


class TestElevenLabsBreaker(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_key_is_not_retried(self):
        provider = EdgeTTSProvider(elevenlabs_fallback_key="bad")
        failing = AsyncMock(side_effect=RuntimeError("ElevenLabs TTS failed (401): Invalid API key"))
        edge_audio = AsyncMock(return_value=b"edge")

        class FakeCommunicate:
            def __init__(self, *args, **kwargs):
                pass

            async def stream(self):
                yield {"type": "audio", "data": await edge_audio()}

        with patch("app.tts.provider.ElevenLabsTTSProvider.synthesize", failing), \
             patch("edge_tts.Communicate", FakeCommunicate):
            self.assertEqual(await provider.synthesize("halo", "JBFqnCBsd6RMkjVDRZzb"), b"edge")
            self.assertEqual(await provider.synthesize("halo", "JBFqnCBsd6RMkjVDRZzb"), b"edge")
        self.assertEqual(failing.await_count, 1)


class TestDeezerEmptyRetry(unittest.IsolatedAsyncioTestCase):
    async def test_empty_query_retries_another_category_query(self):
        provider = DeezerMusicProvider()
        item = {"id": 1, "title": "Lagu", "preview": "https://x/p.mp3", "artist": {"name": "A"}, "album": {}}
        with patch.object(provider, "_call_api", AsyncMock(side_effect=[[], [item]])) as call:
            tracks = await provider.search(category="indo", limit=1)
        self.assertEqual(call.await_count, 2)
        self.assertEqual(tracks[0].title, "Lagu")


if __name__ == "__main__":
    unittest.main()
