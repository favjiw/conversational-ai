"""Tests for the 1-hour rundown (docs/RUNDOWN-LIVE-1-JAM-DRAF.md) and its Tema library."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.clock.parser import load_pagi_bener_clock
from app.orchestrator.clock_runner import ClockRunner, load_tema_library
from app.schemas import PersonaCard, SlotSource, SlotType


class TestRundownDraft(unittest.TestCase):
    def setUp(self):
        self.clock = load_pagi_bener_clock()

    def test_talk_order_follows_draft(self):
        talks = [s.label for s in self.clock.slots if s.source == SlotSource.LLM_CONVERSATION]
        self.assertEqual(talks, [
            "Ice Breaking", "Talk 1 - Opening", "Talk 2 - Say Hi!", "Talk 3 - Teaser 3M",
            "Talk 4 - 3M", "Talk 5 - Konten / SKEMA", "Closing",
        ])

    def test_quarters_and_song_count(self):
        markers = [s.target_min for s in self.clock.slots if s.type == SlotType.TIME_MARKER]
        self.assertEqual(markers, [15, 30, 45])
        self.assertEqual(sum(s.type == SlotType.SONG for s in self.clock.slots), 11)

    def test_news_and_traffic_not_in_rundown(self):
        labels = " ".join(s.label or "" for s in self.clock.slots)
        self.assertNotIn("News", labels)
        self.assertNotIn("Traffic", labels)

    def test_every_llm_slot_has_tema_content(self):
        library = load_tema_library()
        for slot in self.clock.slots:
            if slot.source == SlotSource.LLM_CONVERSATION:
                self.assertIn(slot.id, library, slot.label)
                self.assertTrue(library[slot.id].content, slot.label)

    def test_library_skips_comment_keys(self):
        self.assertNotIn("_note", load_tema_library())


class TestIceBreakingDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_ice_breaking_goes_to_conversation(self):
        clock = load_pagi_bener_clock()
        persona = PersonaCard(id="persona_a", name="Raka", gender="male", voice="v", speaking_style="santai")
        runner = ClockRunner(clock=clock, persona_a=persona, persona_b=persona.model_copy(update={"id": "persona_b"}),
                             llm_client=AsyncMock(), tts_provider=AsyncMock(), music_provider=AsyncMock())
        ice = next(s for s in clock.slots if s.type == SlotType.ICE_BREAKING)
        with patch.object(runner, "_handle_talk_slot", AsyncMock()) as talk:
            await asyncio.wait_for(runner._dispatch_slot(ice, clock.slots.index(ice)), timeout=2)
        talk.assert_awaited_once_with(ice)


if __name__ == "__main__":
    unittest.main()
