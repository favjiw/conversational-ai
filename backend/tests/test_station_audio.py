"""Tests for pre-recorded station audio (jingles, bumpers, tapings) in the clock."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app.orchestrator.clock_runner as clock_runner
from app.main import app
from app.orchestrator.clock_runner import ClockRunner, resolve_station_audio
from app.schemas import Clock, PersonaCard, Slot, SlotSource, SlotType


def _persona(pid: str, name: str, gender: str) -> PersonaCard:
    return PersonaCard(id=pid, name=name, gender=gender, voice="v", speaking_style="santai")


def _runner(clock: Clock, broadcast) -> ClockRunner:
    tts = AsyncMock()
    return ClockRunner(
        clock=clock,
        persona_a=_persona("persona_a", "Raka", "male"),
        persona_b=_persona("persona_b", "Salsa", "female"),
        llm_client=AsyncMock(),
        tts_provider=tts,
        music_provider=AsyncMock(),
        broadcast_fn=broadcast,
    )


class TestStationAudio(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "jingle.mp3").write_bytes(b"ID3fake")
        (self.dir / "notes.md").write_text("not audio")
        patcher = patch.object(clock_runner, "STATION_AUDIO_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_resolve_only_plain_audio_filenames(self):
        self.assertEqual(resolve_station_audio("jingle.mp3"), self.dir / "jingle.mp3")
        self.assertIsNone(resolve_station_audio("missing.mp3"))
        self.assertIsNone(resolve_station_audio("notes.md"))
        self.assertIsNone(resolve_station_audio("../jingle.mp3"))
        self.assertIsNone(resolve_station_audio(None))

    def test_endpoint_serves_audio_and_rejects_others(self):
        client = TestClient(app)
        ok = client.get("/station-audio/jingle.mp3")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content, b"ID3fake")
        self.assertEqual(client.get("/station-audio/notes.md").status_code, 404)
        self.assertEqual(client.get("/station-audio/missing.mp3").status_code, 404)

    async def test_static_slot_plays_recording_without_tts(self):
        events = []

        async def broadcast(event):
            events.append(event)
            if event["type"] == "clock_audio":
                # Simulate the audio owner finishing playback.
                runner.playback_feedback({**event["data"], "state": "ended"})

        slot = Slot(id="s16", order=1, type=SlotType.JINGLE, label="Jingle HITS",
                    source=SlotSource.STATIC_AUDIO, asset="jingle.mp3")
        runner = _runner(Clock(show="t", duration_min=1, slots=[slot]), broadcast)
        runner._session_id = "sess"

        await asyncio.wait_for(runner._dispatch_slot(slot, 0), timeout=2)

        audio = [e for e in events if e["type"] == "clock_audio"]
        self.assertEqual(len(audio), 1)
        self.assertEqual(audio[0]["data"]["audio_url"], "/station-audio/jingle.mp3")
        self.assertFalse(any(e["type"] == "turn" for e in events))
        runner.tts.synthesize.assert_not_called()

    async def test_missing_recording_is_skipped_silently(self):
        events = []

        async def broadcast(event):
            events.append(event)

        slot = Slot(id="s01", order=1, type=SlotType.SMASH, source=SlotSource.STATIC_AUDIO)
        runner = _runner(Clock(show="t", duration_min=1, slots=[slot]), broadcast)

        await asyncio.wait_for(runner._dispatch_slot(slot, 0), timeout=2)

        self.assertEqual([e["type"] for e in events], ["clock_cue"])
        self.assertTrue(events[0]["data"]["skipped"])
        runner.tts.synthesize.assert_not_called()

    async def test_time_marker_is_not_voiced(self):
        events = []

        async def broadcast(event):
            events.append(event)

        slot = Slot(id="s12", order=1, type=SlotType.TIME_MARKER, label="07.15",
                    source=SlotSource.NONE, target_min=15)
        runner = _runner(Clock(show="t", duration_min=1, slots=[slot]), broadcast)

        await asyncio.wait_for(runner._dispatch_slot(slot, 0), timeout=2)

        self.assertEqual([e["type"] for e in events], ["clock_time_marker"])
        runner.tts.synthesize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
