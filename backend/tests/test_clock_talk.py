"""Talk berbasis durasi slot di mode clock: anggaran waktu, giliran penutup, batas aman, pipelining."""

import asyncio
import time
import unittest
from unittest.mock import MagicMock

from app.conversation.engine import TALK_CLOSING_HINT, ConversationEngine
from app.llm.client import LLMResponse
from app.orchestrator.clock_runner import ClockRunner, PreparedLine, TalkBudget
from app.schemas import Clock, PersonaCard, Slot, SlotSource, SlotType, Tema, TemaMode


def _persona(pid, name):
    return PersonaCard(id=pid, name=name, gender="male", voice="v", speaking_style="santai")


class FakeLLM:
    """Persona LLM palsu: mencatat prompt dan waktu tiap panggilan."""

    def __init__(self, delay=0.0):
        self.prompts: list[str] = []
        self.call_times: list[float] = []
        self.delay = delay

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        self.call_times.append(time.perf_counter())
        if self.delay:
            await asyncio.sleep(self.delay)
        n = len(self.prompts)
        return LLMResponse(raw=f"Giliran {n}", parsed={"text": f"Giliran ke-{n} nih Sobat Hits.", "emotion": "neutral"},
                           model="fake")


_DEFAULT_TEMA = Tema(title="Serba-serbi Ospek", mode=TemaMode.IMPROV, content="Tips ospek")


def _runner(slot_sec, llm, line_sec=10.0, play_sec=0.0, talk_turns=None, slot_id="t1", tema=_DEFAULT_TEMA):
    slot = Slot(id=slot_id, order=1, type=SlotType.TALK, source=SlotSource.LLM_CONVERSATION, duration_sec=slot_sec,
                tema=tema)
    clock = Clock(show="t", duration_min=1, slots=[slot])
    tts = MagicMock()
    tts.provider_name = "mock"
    runner = ClockRunner(clock=clock, persona_a=_persona("persona_a", "Raka"), persona_b=_persona("persona_b", "Salsa"),
                         llm_client=llm, tts_provider=tts, music_provider=MagicMock(), talk_turns_per_slot=talk_turns)
    runner.played: list[tuple[str, float, float]] = []

    async def synth(speaker, text, emotion):
        return PreparedLine(speaker=speaker, text=text, emotion=emotion, audio_url=None, duration_sec=line_sec)

    async def play(slot_id, line, wait_spoken=True):
        start = time.perf_counter()
        await asyncio.sleep(play_sec)
        runner.played.append((line.text, start, time.perf_counter()))
        return line.duration_sec

    runner._synthesize_line = synth
    runner._play_line = play
    runner.events = []

    async def emit(event_type, data):
        runner.events.append((event_type, data))

    runner.emit_event = emit
    return runner, slot


class TestTalkBudget(unittest.TestCase):
    def test_stops_near_target_with_closing_turns(self):
        b = TalkBudget(60)
        flags = []
        while not (b.turns and b.should_stop()):
            flags.append(b.is_closing())
            b.add(10)
        self.assertEqual(b.turns, 6)
        self.assertEqual(b.spoken, 60)
        self.assertEqual(flags[-1], True)
        self.assertLessEqual(b.closing_turns, 2)
        self.assertFalse(any(flags[:4]))

    def test_short_slot_still_closes(self):
        b = TalkBudget(30)  # Ice Breaking
        flags = []
        while not (b.turns and b.should_stop()):
            flags.append(b.is_closing())
            b.add(10)
        self.assertEqual(flags, [False, False, True])

    def test_safety_limit_when_duration_unknown(self):
        b = TalkBudget(240)
        self.assertEqual(b.max_turns, 30)
        for _ in range(30):
            b.add(0)
        self.assertTrue(b.should_stop())


class TestDurationTalk(unittest.IsolatedAsyncioTestCase):
    async def test_talk_stops_by_duration_and_closes_with_wrap_up(self):
        llm = FakeLLM()
        runner, slot = _runner(slot_sec=60, llm=llm, line_sec=10)
        logs = []
        orig = ConversationEngine._run_single_turn

        async def spy(self_, *args, **kwargs):
            log = await orig(self_, *args, **kwargs)
            logs.append(log)
            return log

        ConversationEngine._run_single_turn = spy
        try:
            await asyncio.wait_for(runner._handle_talk_slot(slot), timeout=5)
        finally:
            ConversationEngine._run_single_turn = orig

        self.assertEqual(len(runner.played), 6)  # 6 x 10 s = durasi slot, bukan 2 giliran tetap
        self.assertEqual(logs[-1].dialog_act, "wrap_up")
        self.assertIn(TALK_CLOSING_HINT, llm.prompts[-1])
        self.assertNotIn(TALK_CLOSING_HINT, llm.prompts[0])
        self.assertTrue(all(lg.dialog_act is None for lg in logs[:4]))  # baseline: tanpa dialog act

    async def test_override_turns_keeps_old_behaviour(self):
        llm = FakeLLM()
        runner, slot = _runner(slot_sec=600, llm=llm, talk_turns=3)
        await asyncio.wait_for(runner._handle_talk_slot(slot), timeout=5)
        self.assertEqual(len(runner.played), 3)
        self.assertFalse(any(TALK_CLOSING_HINT in p for p in llm.prompts))

    async def test_safety_limit_when_audio_has_no_duration(self):
        llm = FakeLLM()
        runner, slot = _runner(slot_sec=40, llm=llm, line_sec=0)
        await asyncio.wait_for(runner._handle_talk_slot(slot), timeout=5)
        self.assertEqual(len(runner.played), 5)  # 40 // 8

    async def test_next_turn_generated_while_current_audio_plays(self):
        llm = FakeLLM()
        runner, slot = _runner(slot_sec=30, llm=llm, line_sec=10, play_sec=0.2)
        await asyncio.wait_for(runner._handle_talk_slot(slot), timeout=5)
        self.assertEqual(len(runner.played), 3)
        first_play_end = runner.played[0][2]
        self.assertLess(llm.call_times[1], first_play_end)  # pipelining
        # Audio tetap berurutan, tidak tumpang tindih.
        for (_, _, end), (_, start, _) in zip(runner.played, runner.played[1:]):
            self.assertGreaterEqual(start, end)

    async def test_skip_cancels_playing_audio(self):
        llm = FakeLLM()
        runner, slot = _runner(slot_sec=600, llm=llm, line_sec=10, play_sec=5)
        task = asyncio.create_task(runner._handle_talk_slot(slot))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(runner.played, [])  # audio yang berjalan dibatalkan



class TestTalkPoints(unittest.IsolatedAsyncioTestCase):
    def test_long_talk_slots_have_points_and_s21_ends_with_teaser(self):
        from app.orchestrator.clock_runner import load_tema_library, load_tema_points

        points = load_tema_points()
        for slot_id in ("s10", "s13", "s21", "s30", "s40", "s41"):
            self.assertGreaterEqual(len(points.get(slot_id, [])), 3, slot_id)
        self.assertIn("3M", points["s21"][-1]["title"])
        self.assertIn("Say Hi", load_tema_library()["s21"].title)

    async def test_points_follow_elapsed_time_without_wrapping(self):
        llm = FakeLLM()
        # s21: 5 poin, slot 120 s, giliran 10 s = 12 giliran
        runner, slot = _runner(slot_sec=120, llm=llm, line_sec=10, slot_id="s21", tema=None)
        await asyncio.wait_for(runner._handle_talk_slot(slot), timeout=5)
        changes = [d["point_index"] for t, d in runner.events if t == "theme_change"]
        self.assertEqual(changes, [0, 1, 2, 3, 4])  # berurutan, tanpa kembali ke awal
        self.assertIn("Teaser 3M", runner.events[-1][1]["title"])
        self.assertIn("Segmen 3M hadir sebentar lagi", llm.prompts[-1])  # poin terakhir = teaser
        self.assertNotIn("Segmen 3M hadir sebentar lagi", llm.prompts[0])

    async def test_slot_without_material_uses_logged_fallback(self):
        llm = FakeLLM()
        empty = Tema(title="Talk Kosong", mode=TemaMode.IMPROV, content=None)
        runner, slot = _runner(slot_sec=20, llm=llm, line_sec=10, slot_id="tanpa_materi", tema=empty)
        with self.assertLogs("app.orchestrator.clock_runner", level="WARNING") as logs:
            await asyncio.wait_for(runner._handle_talk_slot(slot), timeout=5)
        self.assertTrue(any("no Tema material" in m for m in logs.output))
        self.assertIn("Obrolan santai", llm.prompts[0])
        self.assertEqual([t for t, _ in runner.events if t == "theme_change"], [])


if __name__ == "__main__":
    unittest.main()
