"""Tes urutan sumber lagu di ClockRunner: request penonton, mood Talk, Deezer per kategori."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.comments import queue as cq
from app.comments.queue import CommentQueue
from app.music.models import CatalogSong, MusicTrack, SongRecommendation
from app.orchestrator.clock_runner import ClockRunner
from app.schemas import Clock, PersonaCard, Slot, SlotSource, SlotType, Tema, TemaMode


def _persona(pid, name):
    return PersonaCard(id=pid, name=name, gender="male", voice="v", speaking_style="santai")


def _clock():
    return Clock(show="t", duration_min=1, slots=[
        Slot(id="t1", order=1, type=SlotType.TALK, source=SlotSource.LLM_CONVERSATION,
             tema=Tema(title="Serba-serbi Ospek", mode=TemaMode.IMPROV, content="Cerita ospek dan teman baru")),
        Slot(id="s1", order=2, type=SlotType.SONG, source=SlotSource.MUSIC_API, category="indo"),
        Slot(id="s2", order=3, type=SlotType.SONG, source=SlotSource.MUSIC_API, category="barat"),
        Slot(id="s3", order=4, type=SlotType.SONG, source=SlotSource.MUSIC_API, category="korea"),
    ])


class FakeRecommender:
    def __init__(self, audio=True, mood_status="ok"):
        self.ready = True
        self.status = "ready"
        self.audio = audio
        self.mood_status = mood_status
        self.mood_calls = []
        self.released = []
        self.played = []

    def status_info(self):
        return {"status": self.status}

    async def recommend_for_comment(self, username, text):
        title = text.split()[-1]
        return SongRecommendation(
            intent="explicit_song", username=username, comment=text,
            song=CatalogSong(song_id=f"id_{title}", title=title, artist="Tulus"),
            host_line=f"Ini {title} buat kamu!", note="request eksplisit ditemukan di katalog",
        )

    async def recommend_for_mood(self, mood_text, category):
        self.mood_calls.append((mood_text, category))
        if self.mood_status != "ok":
            return SongRecommendation(status=self.mood_status)
        return SongRecommendation(song=CatalogSong(song_id="id_mood", title="Laskar Pelangi", artist="Nidji"),
                                  host_line="semangat!", reason="cocok")

    async def resolve_audio(self, song, category=""):
        if not self.audio:
            return None
        return MusicTrack(id=f"dz_{song.song_id}", title=song.title, artist=song.artist,
                          preview_url="https://cdn/p.mp3", source="deezer", category=category,
                          catalog_song_id=song.song_id)

    def release(self, song_id):
        self.released.append(song_id)

    def mark_played(self, song_id):
        self.played.append(song_id)


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event_type, data, roles):
        self.events.append((event_type, data, roles))


def _runner(rec=None, queue=None, talk_mood=False, broadcast=None):
    music = AsyncMock()
    music.search.return_value = [MusicTrack(id="cat1", title="Lantas", artist="Juicy Luicy",
                                            preview_url="https://x/p.mp3", category="indo", source="deezer")]
    llm = AsyncMock()
    llm.generate.return_value = SimpleNamespace(raw="Kalimat penyiar yang cukup panjang.")
    tts = MagicMock()
    tts.synthesize_with_timings = AsyncMock(return_value=(b"\x00" * 12000, []))
    tts.provider_name = "mock"
    return ClockRunner(
        clock=_clock(), persona_a=_persona("persona_a", "Raka"), persona_b=_persona("persona_b", "Salsa"),
        llm_client=llm, tts_provider=tts, music_provider=music, broadcast_fn=broadcast, demo_music_sec=1,
        comment_queue=queue, recommender=rec, talk_mood=talk_mood,
    )


async def _queue_with(rec, *comments):
    recorder = Recorder()
    q = CommentQueue(rec, broadcast=recorder)
    entries = []
    for user, text in comments:
        entry, _ = await q.submit(user, text)
        entries.append(entry)
    await q.wait_idle()
    return q, recorder, entries


def _auto_ack(runner_ref, events):
    async def broadcast(event):
        events.append(event)
        if "playback_id" in event["data"]:
            runner_ref[0].playback_feedback({**event["data"], "state": "ended"})
    return broadcast


class TestPrefetch(unittest.IsolatedAsyncioTestCase):
    async def test_back_to_back_songs_prepared_together(self):
        runner = _runner()
        runner._schedule_song_prep(0)  # Talk mulai
        self.assertEqual(sorted(runner._song_prep), ["s1"])
        runner._schedule_song_prep(1)  # s1 mulai -> s2 ikut disiapkan
        self.assertEqual(sorted(runner._song_prep), ["s1", "s2"])
        runner._cancel_song_prep()


class TestRequestFirst(unittest.IsolatedAsyncioTestCase):
    async def test_request_used_and_marked_played(self):
        rec = FakeRecommender()
        q, recorder, (entry,) = await _queue_with(rec, ("andi", "puterin dong HatiHati"))
        events, ref = [], [None]
        runner = _runner(rec, q, broadcast=_auto_ack(ref, events))
        ref[0] = runner

        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        track = prepared.track
        self.assertEqual((track.rec_source, track.requested_by, track.title), ("comment", "andi", "HatiHati"))
        self.assertEqual(track.request_comment, "puterin dong HatiHati")
        self.assertEqual(entry.status, cq.SCHEDULED)
        self.assertEqual(entry.slot_id, "s1")
        scheduled = [d for t, d, r in recorder.events if t == "song_request_scheduled"]
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0]["slot_id"], "s1")
        self.assertEqual([r for t, d, r in recorder.events if t == "song_request_scheduled"], [("console",)])

        # Prompt intro menyebut username, isi komentar, dan host_line sebagai bahan.
        intro_prompt = runner.llm.generate.await_args_list[0].kwargs["prompt"]
        self.assertIn("andi", intro_prompt)
        self.assertIn("puterin dong HatiHati", intro_prompt)
        self.assertIn("jangan dibacakan mentah: Ini HatiHati buat kamu!", intro_prompt)
        runner.music.search.assert_not_awaited()  # Deezer per kategori tidak dipakai

        runner._song_prep["s1"] = asyncio.ensure_future(asyncio.sleep(0, result=prepared))
        await asyncio.wait_for(runner._handle_song_slot(runner.clock.slots[1], 1), timeout=2)
        self.assertEqual(entry.status, cq.PLAYED)
        self.assertEqual(rec.played, ["id_HatiHati"])
        music = [e for e in events if e["type"] == "clock_music"][0]
        self.assertEqual(music["data"]["track"]["requested_by"], "andi")

    async def test_request_ignores_category_but_not_korea(self):
        rec = FakeRecommender()
        q, _, (entry,) = await _queue_with(rec, ("andi", "puterin lagu Perfect"))
        runner = _runner(rec, q)
        korea = await runner._prepare_song(runner.clock.slots[3], 3)
        self.assertEqual(korea.track.rec_source, "category")
        self.assertEqual(entry.status, cq.WAITING)  # tetap menunggu slot berikutnya
        barat = await runner._prepare_song(runner.clock.slots[2], 2)
        self.assertEqual(barat.track.rec_source, "comment")

    async def test_audio_not_found_marks_unavailable_and_falls_back(self):
        rec = FakeRecommender(audio=False)
        q, _, (entry,) = await _queue_with(rec, ("andi", "puterin lagu X"))
        runner = _runner(rec, q)
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual(prepared.track.rec_source, "category")
        self.assertEqual(prepared.track.title, "Lantas")
        self.assertEqual(entry.status, cq.UNAVAILABLE)
        self.assertEqual(rec.released, ["id_X"])
        self.assertEqual(prepared.request_id, "")

    async def test_back_to_back_slots_take_different_requests(self):
        rec = FakeRecommender()
        q, _, (a, b) = await _queue_with(rec, ("andi", "puterin lagu A"), ("budi", "puterin lagu B"))
        runner = _runner(rec, q)
        runner._schedule_song_prep(1)
        p1, p2 = await asyncio.gather(runner._song_prep["s1"], runner._song_prep["s2"])
        self.assertEqual({p1.track.requested_by, p2.track.requested_by}, {"andi", "budi"})

    async def test_request_after_prep_started_goes_to_next_slot(self):
        rec = FakeRecommender()
        q = CommentQueue(rec)
        runner = _runner(rec, q)
        first = await runner._prepare_song(runner.clock.slots[1], 1)  # antrean masih kosong
        self.assertEqual(first.track.rec_source, "category")
        entry, _ = await q.submit("andi", "puterin lagu Late")
        await q.wait_idle()
        second = await runner._prepare_song(runner.clock.slots[2], 2)
        self.assertEqual(second.track.requested_by, "andi")
        self.assertEqual(entry.slot_id, "s2")

    async def test_no_recommender_keeps_old_behaviour(self):
        runner = _runner()
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual((prepared.track.title, prepared.track.rec_source), ("Lantas", "category"))

    async def test_deezer_empty_gives_fallback_source(self):
        runner = _runner()
        runner.music.search.return_value = []
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual((prepared.track.source, prepared.track.rec_source), ("fallback", "fallback"))


class TestSkipStop(unittest.IsolatedAsyncioTestCase):
    async def test_skip_before_on_air_returns_request(self):
        rec = FakeRecommender()
        q, _, (entry,) = await _queue_with(rec, ("andi", "puterin lagu A"))
        events = []

        async def broadcast(event):
            events.append(event)  # tidak ada ack: intro "menggantung" sampai di-skip

        runner = _runner(rec, q, broadcast=broadcast)
        runner._schedule_song_prep(1)
        handler = asyncio.create_task(runner._handle_song_slot(runner.clock.slots[1], 1))
        for _ in range(100):
            await asyncio.sleep(0.01)
            if any(e["type"] == "turn" for e in events):
                break
        self.assertEqual(entry.status, cq.SCHEDULED)
        handler.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await handler
        await asyncio.sleep(0.01)
        self.assertEqual(entry.status, cq.WAITING)
        self.assertEqual(rec.played, [])

    async def test_stop_during_prep_returns_request(self):
        rec = FakeRecommender()
        q, _, (entry,) = await _queue_with(rec, ("andi", "puterin lagu A"))
        runner = _runner(rec, q)
        gate = asyncio.Event()
        original = runner._generate_line

        async def slow_line(prompt, fallback):
            await gate.wait()
            return await original(prompt, fallback)

        runner._generate_line = slow_line
        runner._state = runner._state.RUNNING
        runner._schedule_song_prep(1)
        for _ in range(100):
            await asyncio.sleep(0.01)
            if entry.status == cq.SCHEDULED:
                break
        self.assertEqual(entry.status, cq.SCHEDULED)
        await runner.stop()
        await asyncio.sleep(0.02)
        self.assertEqual(entry.status, cq.WAITING)

    async def test_stop_after_prep_done_returns_request(self):
        rec = FakeRecommender()
        q, _, (entry,) = await _queue_with(rec, ("andi", "puterin lagu A"))
        runner = _runner(rec, q)
        runner._state = runner._state.RUNNING
        runner._schedule_song_prep(1)
        await runner._song_prep["s1"]
        self.assertEqual(entry.status, cq.SCHEDULED)
        await runner.stop()
        await asyncio.sleep(0.02)
        self.assertEqual(entry.status, cq.WAITING)


class TestTalkMood(unittest.IsolatedAsyncioTestCase):
    async def test_flag_off_skips_mood(self):
        rec = FakeRecommender()
        runner = _runner(rec, CommentQueue(rec), talk_mood=False)
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual(prepared.track.rec_source, "category")
        self.assertEqual(rec.mood_calls, [])

    async def test_flag_on_uses_previous_talk_topic(self):
        rec = FakeRecommender()
        events, ref = [], [None]
        runner = _runner(rec, CommentQueue(rec), talk_mood=True, broadcast=_auto_ack(ref, events))
        ref[0] = runner
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual((prepared.track.rec_source, prepared.track.title), ("talk_mood", "Laskar Pelangi"))
        self.assertEqual(rec.mood_calls, [("Serba-serbi Ospek. Cerita ospek dan teman baru", "indo")])
        runner._song_prep["s1"] = asyncio.ensure_future(asyncio.sleep(0, result=prepared))
        await asyncio.wait_for(runner._handle_song_slot(runner.clock.slots[1], 1), timeout=2)
        self.assertEqual(rec.played, ["id_mood"])

    async def test_mood_timeout_falls_back_to_category(self):
        rec = FakeRecommender(mood_status="timeout")
        runner = _runner(rec, CommentQueue(rec), talk_mood=True)
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual(prepared.track.rec_source, "category")

    async def test_mood_audio_missing_releases_reservation(self):
        rec = FakeRecommender(audio=False)
        runner = _runner(rec, CommentQueue(rec), talk_mood=True)
        prepared = await runner._prepare_song(runner.clock.slots[1], 1)
        self.assertEqual(prepared.track.rec_source, "category")
        self.assertEqual(rec.released, ["id_mood"])

    async def test_korea_slot_never_uses_mood(self):
        rec = FakeRecommender()
        runner = _runner(rec, CommentQueue(rec), talk_mood=True)
        prepared = await runner._prepare_song(runner.clock.slots[3], 3)
        self.assertEqual(prepared.track.rec_source, "category")
        self.assertEqual(rec.mood_calls, [])



class TestMusicEventLog(unittest.IsolatedAsyncioTestCase):
    async def test_comment_and_song_selection_logged(self):
        import json
        import tempfile
        from pathlib import Path

        from app.session_logging.music_log import MusicEventLogger

        with tempfile.TemporaryDirectory() as tmp:
            log = MusicEventLogger(tmp)
            log.set_session("clock_test")
            rec = FakeRecommender()
            q = CommentQueue(rec, event_log=log)
            await q.submit("andi", "puterin lagu A")
            await q.wait_idle()
            runner = _runner(rec, q)
            runner.event_log = log
            await runner._prepare_song(runner.clock.slots[1], 1)

            lines = [json.loads(x) for x in Path(tmp, "clock_test.music.jsonl").read_text(encoding="utf-8").splitlines()]
            events = [x["event"] for x in lines]
            self.assertEqual(events[0], "comment")
            self.assertEqual(lines[0]["intent"], "explicit_song")
            self.assertIn("request_status", events)
            selected = [x for x in lines if x["event"] == "song_selected"][0]
            self.assertEqual((selected["rec_source"], selected["requested_by"]), ("comment", "andi"))
            self.assertIn("audio_search_sec", selected["timings"])
            self.assertIn("prep_total_sec", selected["timings"])

    def test_offair_session_name(self):
        from app.session_logging.music_log import MusicEventLogger

        log = MusicEventLogger("logs")
        self.assertTrue(log.session_id.startswith("offair_"))
        log.set_session("clock_x")
        self.assertEqual(log.path().name, "clock_x.music.jsonl")
        log.end_session()
        self.assertTrue(log.session_id.startswith("offair_"))


if __name__ == "__main__":
    unittest.main()
