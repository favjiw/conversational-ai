"""Tes adapter rekomendasi lagu tanpa API dan tanpa memuat hits_rec/model embedding."""

import asyncio
import threading
import unittest
from types import SimpleNamespace

from app.music.models import CatalogSong, MusicTrack
from app.music.recommender import (
    ReservingHistory,
    SongRecommenderService,
    artists_match,
    titles_match,
)


def _settings(**overrides):
    values = dict(
        RECOMMENDER_ENABLED=True,
        RECOMMENDER_LLM_API_KEY="test-key",
        RECOMMENDER_LLM_BASE_URL="https://example.invalid/v1",
        RECOMMENDER_LLM_MODEL="test-model",
        RECOMMENDER_LLM_REASONING_EFFORT="",
        RECOMMENDER_TIMEOUT_SEC=2.0,
        RECOMMENDER_MAX_PENDING=5,
        RECOMMENDER_TALK_MOOD=False,
        LLM_MODE="live",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _song(song_id="s1", title="Hati-Hati di Jalan", artist="Tulus", language="id"):
    return SimpleNamespace(
        song_id=song_id, title=title, artist=artist, language=language, genre="pop", year=2022,
        moods=["sedih", "ikhlas"], energy="rendah", valence="netral",
    )


def _result(song=None, intent_type="explicit_song", moderation=False, note="ok"):
    rec = SimpleNamespace(song=song, reason="cocok", host_line="Ini dia lagunya!") if song else None
    return SimpleNamespace(
        intent=SimpleNamespace(type=intent_type, needs_moderation=moderation),
        recommendation=rec,
        note=note,
        timings={"intent": 0.5, "retrieval": 0.01, "rerank": 0.3, "total": 0.81},
    )


class FakeBackend:
    def __init__(self, settings, history, result=None, delay=0.0):
        self.history = history
        self.result = result if result is not None else _result(_song())
        self.delay = delay
        self.release_gate = threading.Event()
        self.mood_calls = []

    def recommend(self, comment):
        if self.delay:
            self.release_gate.wait(self.delay)
        if self.result.recommendation:
            self.history.add(self.result.recommendation.song.song_id)
        return self.result

    def recommend_mood(self, mood_text, language):
        self.mood_calls.append((mood_text, language))
        return self.result


class FakeMusic:
    def __init__(self, tracks=None, fail=False):
        self.tracks = tracks or []
        self.fail = fail
        self.queries = []

    async def search(self, category="", query="", limit=5):
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("network down")
        return self.tracks


def _service(settings=None, backend=None, music=None):
    holder = {}

    def factory(s, history):
        b = backend(s, history) if callable(backend) else FakeBackend(s, history)
        holder["backend"] = b
        return b

    svc = SongRecommenderService(settings or _settings(), music or FakeMusic(), backend_factory=factory)
    return svc, holder


class TestDisabledModes(unittest.IsolatedAsyncioTestCase):
    async def _assert_disabled(self, settings, reason_part):
        svc, holder = _service(settings)
        svc.load_now()
        self.assertEqual(svc.status, "disabled")
        self.assertIn(reason_part, svc.reason)
        self.assertNotIn("backend", holder)  # hits_rec tidak pernah dimuat
        res = await svc.recommend_for_comment("andi", "puterin tulus dong")
        self.assertEqual(res.status, "disabled")
        self.assertIsNone(res.song)

    async def test_flag_off(self):
        await self._assert_disabled(_settings(RECOMMENDER_ENABLED=False), "RECOMMENDER_ENABLED")

    async def test_llm_mock_mode(self):
        await self._assert_disabled(_settings(LLM_MODE="mock"), "LLM_MODE=mock")

    async def test_empty_key(self):
        await self._assert_disabled(_settings(RECOMMENDER_LLM_API_KEY=""), "kosong")

    async def test_package_missing(self):
        def factory(s, h):
            raise ImportError("No module named 'hits_rec'")

        svc = SongRecommenderService(_settings(), FakeMusic(), backend_factory=factory)
        svc.load_now()
        self.assertEqual(svc.status, "disabled")
        self.assertIn("belum terinstal", svc.reason)
        res = await svc.recommend_for_comment("andi", "halo")
        self.assertEqual(res.status, "disabled")

    async def test_load_error(self):
        def factory(s, h):
            raise RuntimeError("indeks chroma tidak ada")

        svc = SongRecommenderService(_settings(), FakeMusic(), backend_factory=factory)
        svc.load_now()
        self.assertEqual(svc.status, "error")
        res = await svc.recommend_for_comment("andi", "halo")
        self.assertEqual(res.status, "disabled")

    def test_background_loading_reaches_ready(self):
        svc, _ = _service()
        self.assertEqual(svc.status, "loading")
        svc.start_loading()
        svc._loader.join(timeout=5)
        self.assertEqual(svc.status, "ready")
        self.assertEqual(svc.status_info()["status"], "ready")
        svc.shutdown()


class TestRecommend(unittest.IsolatedAsyncioTestCase):
    async def test_comment_converted(self):
        svc, _ = _service()
        svc.load_now()
        res = await svc.recommend_for_comment("andi", "kak puterin hati2 dijalan tulus")
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.intent, "explicit_song")
        self.assertEqual(res.username, "andi")
        self.assertEqual(res.song.title, "Hati-Hati di Jalan")
        self.assertEqual(res.song.moods, ["sedih", "ikhlas"])
        self.assertEqual(res.host_line, "Ini dia lagunya!")
        self.assertAlmostEqual(res.timings["total"], 0.81)
        svc.shutdown()

    async def test_moderation_has_no_song(self):
        svc, _ = _service(backend=lambda s, h: FakeBackend(
            s, h, result=_result(None, "not_a_request", moderation=True, note="perlu moderasi")))
        svc.load_now()
        res = await svc.recommend_for_comment("x", "kata kasar")
        self.assertEqual(res.status, "ok")
        self.assertTrue(res.needs_moderation)
        self.assertIsNone(res.song)
        svc.shutdown()

    async def test_timeout_returns_and_releases_late_reservation(self):
        svc, holder = _service(_settings(RECOMMENDER_TIMEOUT_SEC=0.05),
                               backend=lambda s, h: FakeBackend(s, h, delay=5))
        svc.load_now()
        res = await svc.recommend_for_comment("andi", "tulus dong")
        self.assertEqual(res.status, "timeout")
        self.assertIsNone(res.song)
        # Hasil terlambat datang: lagunya dipesan lalu dilepas lagi oleh callback.
        holder["backend"].release_gate.set()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if "s1" not in svc._history and len(svc._history) == 0:
                break
        self.assertNotIn("s1", svc._history)
        svc.shutdown()

    async def test_mood_uses_category_language(self):
        svc, holder = _service()
        svc.load_now()
        res = await svc.recommend_for_mood("ospek dan teman baru", "barat")
        self.assertEqual(res.status, "ok")
        self.assertEqual(holder["backend"].mood_calls, [("ospek dan teman baru", "en")])
        korea = await svc.recommend_for_mood("ospek", "korea")
        self.assertEqual(korea.status, "disabled")
        self.assertEqual(len(holder["backend"].mood_calls), 1)
        svc.shutdown()


class TestReservingHistory(unittest.TestCase):
    def test_reserve_play_release(self):
        h = ReservingHistory(size=2)
        self.assertTrue(bool(h))  # kosong pun tidak boleh falsy
        h.add("a")
        self.assertIn("a", h)
        h.release("a")
        self.assertNotIn("a", h)
        h.add("b")
        h.mark_played("b")
        self.assertIn("b", h)
        self.assertEqual(len(h), 1)
        h.mark_played("c")
        h.mark_played("d")
        self.assertNotIn("b", h)  # keluar dari jendela cooldown


def _track(title, artist, preview="https://cdn/x.mp3"):
    return MusicTrack(id=f"dz_{title}", title=title, artist=artist, preview_url=preview, source="deezer")


class TestResolveAudio(unittest.IsolatedAsyncioTestCase):
    async def test_matching_track_used(self):
        music = FakeMusic([_track("Lathi", "Weird Genius"), _track("Hati-Hati di Jalan", "Tulus")])
        svc, _ = _service(music=music)
        song = CatalogSong(song_id="s1", title="Hati-Hati di Jalan", artist="Tulus")
        track = await svc.resolve_audio(song, "indo")
        self.assertEqual(track.id, "dz_Hati-Hati di Jalan")
        self.assertEqual(track.catalog_song_id, "s1")
        self.assertEqual(track.category, "indo")
        self.assertEqual(music.queries, ["Tulus Hati-Hati di Jalan"])

    async def test_no_match_returns_none(self):
        music = FakeMusic([_track("Hati-Hati di Jalan (Cover)", "Penyanyi Lain"), _track("Lain", "Tulus")])
        svc, _ = _service(music=music)
        song = CatalogSong(song_id="s1", title="Hati-Hati di Jalan", artist="Tulus")
        self.assertIsNone(await svc.resolve_audio(song))

    async def test_track_without_preview_skipped(self):
        music = FakeMusic([_track("Hati-Hati di Jalan", "Tulus", preview="")])
        svc, _ = _service(music=music)
        self.assertIsNone(await svc.resolve_audio(CatalogSong(song_id="s1", title="Hati-Hati di Jalan", artist="Tulus")))

    async def test_search_failure_returns_none(self):
        svc, _ = _service(music=FakeMusic(fail=True))
        self.assertIsNone(await svc.resolve_audio(CatalogSong(song_id="s1", title="X", artist="Y")))

    def test_fuzzy_rules(self):
        self.assertTrue(titles_match("Hati-Hati di Jalan", "Hati Hati Di Jalan"))
        self.assertTrue(titles_match("Bohemian Rhapsody", "Bohemian Rhapsody - Remastered 2011"))
        self.assertTrue(titles_match("Sunflower", "Sunflower (Spider-Man: Into the Spider-Verse)"))
        self.assertFalse(titles_match("Pupus", "Pupus Harapan"))
        self.assertTrue(artists_match("Post Malone and Swae Lee", "Post Malone"))
        self.assertTrue(artists_match("Mahalini feat. Rizky Febian", "Rizky Febian"))
        self.assertFalse(artists_match("Tulus", "Tulus Cover Band Bandung"))


class TestMusicTrackDefaults(unittest.TestCase):
    def test_new_fields_default_empty(self):
        t = MusicTrack(id="1", title="a", artist="b")
        dumped = t.model_dump()
        for key in ("rec_source", "requested_by", "request_comment", "host_line", "reason", "catalog_song_id"):
            self.assertEqual(dumped[key], "")


if __name__ == "__main__":
    unittest.main()
