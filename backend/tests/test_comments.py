"""Tes antrean komentar penonton dan endpoint /api/comments (tanpa API dan tanpa hits_rec)."""

import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.comments import queue as cq
from app.comments.queue import CommentQueue
from app.music.models import CatalogSong, SongRecommendation


def _rec(intent="explicit_song", song="Hati-Hati di Jalan", moderation=False, status="ok", note=""):
    return SongRecommendation(
        status=status, intent=intent, needs_moderation=moderation, note=note,
        song=CatalogSong(song_id=f"id_{song}", title=song, artist="Tulus") if song else None,
        timings={"total": 0.5},
    )


class FakeRecommender:
    """Hasil per kata kunci di komentar; mencatat pesanan yang dilepas/diputar."""

    def __init__(self, ready=True, delay=0.0):
        self.ready = ready
        self.status = "ready" if ready else "disabled"
        self.delay = delay
        self.calls = []
        self.released = []
        self.played = []
        self.active = 0
        self.max_active = 0

    def status_info(self):
        return {"status": self.status}

    async def recommend_for_comment(self, username, text):
        self.calls.append(text)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(self.delay)
        self.active -= 1
        if "kasar" in text:
            return _rec("not_a_request", None, moderation=True, note="perlu moderasi")
        if "halo" in text:
            return _rec("not_a_request", None, note="bukan permintaan lagu")
        if "timeout" in text:
            return _rec("", None, status="timeout", note="melebihi 8 s")
        if "kosong" in text:
            return _rec("mood_request", None, note="tidak ada kandidat")
        return _rec("explicit_song", text.split()[-1])

    def release(self, song_id):
        self.released.append(song_id)

    def mark_played(self, song_id):
        self.played.append(song_id)


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event_type, data, roles):
        self.events.append((event_type, data, roles))

    def of(self, event_type):
        return [(d, r) for t, d, r in self.events if t == event_type]


def _queue(rec=None, max_pending=5):
    recorder = Recorder()
    return CommentQueue(rec or FakeRecommender(), broadcast=recorder, max_pending=max_pending), recorder


class TestClassification(unittest.IsolatedAsyncioTestCase):
    async def test_request_goes_to_waiting_and_broadcasts_comment_to_all(self):
        q, events = _queue()
        entry, dup = await q.submit("@andi ", "puterin lagu tulus")
        self.assertFalse(dup)
        self.assertEqual(entry.username, "andi")
        self.assertEqual(entry.status, cq.CLASSIFYING)
        await q.wait_idle()
        self.assertEqual(entry.status, cq.WAITING)
        self.assertTrue(entry.moderated)
        self.assertIs(q.next_request(), entry)
        comment_events = events.of("comment")
        self.assertEqual(len(comment_events), 1)
        self.assertIsNone(comment_events[0][1])  # semua role (console + stage)
        self.assertEqual(comment_events[0][0]["song"]["title"], "tulus")

    async def test_not_a_request_is_general(self):
        q, _ = _queue()
        entry, _ = await q.submit("budi", "halo kak salam dari bandung")
        await q.wait_idle()
        self.assertEqual(entry.status, cq.GENERAL)
        self.assertEqual(q.general_comments(), [entry])
        self.assertIsNone(q.next_request())

    async def test_moderation_rejected_console_only(self):
        q, events = _queue()
        entry, _ = await q.submit("troll", "komentar kasar")
        await q.wait_idle()
        self.assertEqual(entry.status, cq.REJECTED)
        self.assertEqual(events.of("comment"), [])  # stage tidak pernah menerima
        rejected = events.of("comment_rejected")
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0][1], ("console",))
        self.assertNotIn(entry, q.general_comments())
        for data, roles in events.of("comment_queue"):
            self.assertEqual(roles, ("console",))

    async def test_timeout_falls_back_to_unmoderated_general(self):
        q, _ = _queue()
        entry, _ = await q.submit("c", "ini timeout")
        await q.wait_idle()
        self.assertEqual(entry.status, cq.GENERAL)
        self.assertFalse(entry.moderated)
        self.assertIn("timeout", entry.note)

    async def test_request_without_song_unavailable(self):
        q, _ = _queue()
        entry, _ = await q.submit("d", "lagu kosong")
        await q.wait_idle()
        self.assertEqual(entry.status, cq.UNAVAILABLE)

    async def test_recommender_not_ready_skips_llm(self):
        rec = FakeRecommender(ready=False)
        q, events = _queue(rec)
        entry, _ = await q.submit("e", "puterin lagu tulus")
        self.assertEqual(entry.status, cq.GENERAL)
        self.assertFalse(entry.moderated)
        self.assertEqual(rec.calls, [])
        self.assertEqual(len(events.of("comment")), 1)


class TestLimits(unittest.IsolatedAsyncioTestCase):
    async def test_one_at_a_time(self):
        rec = FakeRecommender(delay=0.02)
        q, _ = _queue(rec)
        for i in range(3):
            await q.submit(f"u{i}", f"puterin lagu L{i}")
        await q.wait_idle()
        self.assertEqual(rec.max_active, 1)
        self.assertEqual([e.status for e in q.entries()], [cq.WAITING] * 3)
        # FIFO
        self.assertEqual(q.next_request().username, "u0")

    async def test_duplicate_ignored(self):
        rec = FakeRecommender()
        q, _ = _queue(rec)
        first, _ = await q.submit("andi", "puterin lagu Tulus")
        again, dup = await q.submit("@ANDI", "  puterin   lagu tulus ")
        self.assertTrue(dup)
        self.assertIs(again, first)
        await q.wait_idle()
        self.assertEqual(len(q.entries()), 1)
        self.assertEqual(len(rec.calls), 1)

    async def test_one_active_request_per_user(self):
        rec = FakeRecommender()
        q, _ = _queue(rec)
        await q.submit("andi", "puterin lagu A")
        await q.wait_idle()
        second, _ = await q.submit("andi", "puterin lagu B")
        await q.wait_idle()
        self.assertEqual(second.status, cq.GENERAL)
        self.assertIn("request aktif", second.note)
        self.assertTrue(second.moderated)  # tetap lewat moderasi
        self.assertEqual(rec.released, ["id_B"])

    async def test_user_with_active_request_still_moderated(self):
        q, events = _queue()
        await q.submit("andi", "puterin lagu A")
        await q.wait_idle()
        rude, _ = await q.submit("andi", "komentar kasar")
        await q.wait_idle()
        self.assertEqual(rude.status, cq.REJECTED)
        self.assertNotIn(rude.id, [d["id"] for d, r in events.of("comment")])

    async def test_classification_backlog_skips_llm(self):
        rec = FakeRecommender(delay=0.05)
        q, _ = _queue(rec, max_pending=2)
        for i in range(3):
            await q.submit(f"u{i}", f"puterin lagu L{i}")
        third = q.entries()[2]
        self.assertEqual(third.status, cq.GENERAL)
        self.assertFalse(third.moderated)
        self.assertIn("klasifikasi", third.note)
        await q.wait_idle()
        self.assertEqual(len(rec.calls), 2)

    async def test_same_user_racing_requests_release_reservation(self):
        rec = FakeRecommender(delay=0.01)
        q, _ = _queue(rec)
        a, _ = await q.submit("andi", "puterin lagu A")
        b, _ = await q.submit("andi", "puterin lagu B")  # masih classifying semua
        await q.wait_idle()
        self.assertEqual(a.status, cq.WAITING)
        self.assertEqual(b.status, cq.GENERAL)
        self.assertEqual(rec.released, ["id_B"])

    async def test_max_pending(self):
        rec = FakeRecommender()
        q, _ = _queue(rec, max_pending=2)
        for i in range(2):
            await q.submit(f"u{i}", f"puterin lagu L{i}")
            await q.wait_idle()
        third, _ = await q.submit("u9", "puterin lagu L9")
        await q.wait_idle()
        self.assertEqual(third.status, cq.GENERAL)
        self.assertIn("penuh", third.note)
        self.assertEqual(rec.released, ["id_L9"])

    async def test_validation(self):
        q, _ = _queue()
        with self.assertRaises(ValueError):
            await q.submit("  @ ", "halo")


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_play_return_unavailable(self):
        rec = FakeRecommender()
        q, events = _queue(rec)
        a, _ = await q.submit("a", "puterin lagu A")
        b, _ = await q.submit("b", "puterin lagu B")
        await q.wait_idle()

        await q.schedule(a.id, "s11")
        self.assertEqual((a.status, a.slot_id), (cq.SCHEDULED, "s11"))
        self.assertIs(q.next_request(), b)

        await q.return_to_queue(a.id)  # skip saat persiapan
        self.assertEqual((a.status, a.slot_id), (cq.WAITING, ""))
        self.assertIs(q.next_request(), a)  # urutan semula

        await q.schedule(a.id, "s12")
        await q.mark_played(a.id)
        self.assertEqual(a.status, cq.PLAYED)
        self.assertEqual(rec.played, ["id_A"])

        await q.mark_unavailable(b.id, "audio tidak ditemukan")
        self.assertEqual(b.status, cq.UNAVAILABLE)
        self.assertEqual(rec.released, ["id_B"])

        snap = q.snapshot()
        self.assertEqual(snap["waiting"], 0)
        self.assertEqual(snap["comments"][0]["id"], b.id)  # terbaru di atas


class TestReadInTalk(unittest.IsolatedAsyncioTestCase):
    async def test_general_comment_read_once_and_announced(self):
        q, events = _queue()
        halo, _ = await q.submit("budi", "halo kak salam dari bandung")
        await q.wait_idle()
        self.assertIs(q.next_general_comment(), halo)
        await q.mark_read(halo.id, "s13")
        self.assertEqual((halo.status, halo.slot_id), (cq.READ, "s13"))
        self.assertIsNone(q.next_general_comment())  # tidak dibacakan lagi
        await q.mark_read(halo.id, "s13")
        read = events.of("comment_read")
        self.assertEqual(len(read), 1)
        self.assertIsNone(read[0][1])  # console + stage
        self.assertEqual(read[0][0]["username"], "budi")

    async def test_unmoderated_comment_never_read(self):
        q, _ = _queue(FakeRecommender(ready=False))
        await q.submit("x", "halo kak")
        self.assertIsNone(q.next_general_comment())

    async def test_rejected_comment_never_read(self):
        q, _ = _queue()
        await q.submit("troll", "komentar kasar")
        await q.wait_idle()
        self.assertIsNone(q.next_general_comment())

    async def test_request_mentioned_once(self):
        q, _ = _queue()
        req, _ = await q.submit("andi", "puterin lagu Tulus")
        await q.wait_idle()
        self.assertIs(q.next_unmentioned_request(), req)
        q.mark_request_mentioned(req.id)
        self.assertIsNone(q.next_unmentioned_request())


class TestCommentsEndpoint(unittest.TestCase):
    def setUp(self):
        import app.main as main
        self.main = main
        self.client = TestClient(main.app)
        self.queue = CommentQueue(FakeRecommender(ready=False), broadcast=main._broadcast_comment_event)
        self.patch = patch.object(main, "comment_queue", self.queue)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_post_and_list(self):
        with self.client.websocket_connect("/ws/session?role=stage") as stage:
            res = self.client.post("/api/comments", json={"username": "andi", "text": "halo kak"})
            self.assertEqual(res.status_code, 200)
            body = res.json()
            self.assertFalse(body["duplicate"])
            self.assertEqual(body["comment"]["status"], "general")
            while True:
                event = stage.receive_json()
                self.assertNotIn(event["type"], ("comment_queue", "comment_rejected"))  # khusus console
                if event["type"] == "comment":
                    break
            self.assertEqual(event["data"]["username"], "andi")

        dup = self.client.post("/api/comments", json={"username": "andi", "text": "halo kak"})
        self.assertTrue(dup.json()["duplicate"])
        listing = self.client.get("/api/comments").json()
        self.assertEqual(len(listing["comments"]), 1)
        self.assertEqual(listing["recommender"]["status"], "disabled")

    def test_validation(self):
        self.assertEqual(self.client.post("/api/comments", json={"text": "halo"}).status_code, 422)
        self.assertEqual(self.client.post("/api/comments", json={"username": "a", "text": ""}).status_code, 422)
        self.assertEqual(self.client.post("/api/comments", json={"username": "a", "text": "x" * 301}).status_code, 422)
        self.assertEqual(self.client.post("/api/comments", json={"username": " @ ", "text": "halo"}).status_code, 400)

    def test_health_reports_recommender(self):
        data = self.client.get("/health").json()
        self.assertIn(data["recommender"]["status"], ("disabled", "loading", "ready", "error"))


if __name__ == "__main__":
    unittest.main()
