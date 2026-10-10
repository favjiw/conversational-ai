"""Unit tests for music provider module."""

import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from app.music.models import MusicTrack
from app.music.provider import (
    MockMusicProvider,
    DeezerMusicProvider,
    create_music_provider,
    CATEGORY_QUERIES,
)

DEEZER_SAMPLE = {
    "data": [
        {"id": 111, "title": "Hati-Hati di Jalan", "duration": 242,
         "preview": "https://cdn.dzcdn.net/sample.mp3",
         "link": "https://www.deezer.com/track/111",
         "artist": {"name": "Tulus"},
         "album": {"title": "Manusia", "cover_medium": "https://img/c.jpg"}},
        {"id": 222, "title": "No Preview", "duration": 180,
         "preview": "",
         "artist": {"name": "X"}, "album": {"title": "Y"}},
        {"id": 333, "title": "Harder Better", "duration": 226,
         "preview": "https://cdn.dzcdn.net/daft.mp3",
         "link": "https://www.deezer.com/track/333",
         "artist": {"name": "Daft Punk"},
         "album": {"title": "Discovery", "cover_medium": "https://img/d.jpg"}},
    ],
    "total": 80,
}


def _mock_httpx(response_data: dict):
    """Return a context-managed mock httpx.AsyncClient."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()
    inst = AsyncMock()
    inst.get.return_value = mock_resp
    inst.__aenter__ = AsyncMock(return_value=inst)
    inst.__aexit__ = AsyncMock(return_value=False)
    return inst



class TestMockMusicProvider(unittest.IsolatedAsyncioTestCase):
    async def test_returns_tracks(self):
        tracks = await MockMusicProvider().search()
        self.assertTrue(len(tracks) > 0)
        self.assertIsInstance(tracks[0], MusicTrack)
        self.assertEqual(tracks[0].source, "mock")

    async def test_filter_by_category(self):
        tracks = await MockMusicProvider().search(category="korea")
        self.assertTrue(all(t.category == "korea" for t in tracks))

    async def test_unknown_category_returns_all(self):
        tracks = await MockMusicProvider().search(category="dangdut")
        self.assertTrue(len(tracks) > 0)

    def test_provider_name(self):
        self.assertEqual(MockMusicProvider().provider_name, "mock")


class TestDeezerMusicProvider(unittest.IsolatedAsyncioTestCase):
    async def test_search_parses_and_filters(self):
        provider = DeezerMusicProvider()
        with patch("app.music.provider.httpx.AsyncClient",
                   return_value=_mock_httpx(DEEZER_SAMPLE)):
            tracks = await provider.search(category="indo_hits", limit=5)
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0].title, "Hati-Hati di Jalan")
        self.assertEqual(tracks[0].artist, "Tulus")
        self.assertEqual(tracks[0].source, "deezer")
        self.assertTrue(tracks[0].preview_url.endswith(".mp3"))

    async def test_all_null_preview_returns_empty(self):
        no_preview = {"data": [
            {"id": 1, "title": "X", "duration": 100, "preview": "",
             "artist": {"name": "A"}, "album": {"title": "B"}},
        ]}
        with patch("app.music.provider.httpx.AsyncClient",
                   return_value=_mock_httpx(no_preview)):
            tracks = await DeezerMusicProvider().search(category="barat")
        self.assertEqual(len(tracks), 0)

    async def test_fail_inject_raises(self):
        with self.assertRaises(RuntimeError):
            await DeezerMusicProvider(fail_inject=True).search()

    def test_provider_name(self):
        self.assertEqual(DeezerMusicProvider().provider_name, "deezer")

    def test_resolve_query_explicit(self):
        self.assertEqual(
            DeezerMusicProvider._resolve_query("indo", "custom"), "custom")

    def test_resolve_query_from_category(self):
        q = DeezerMusicProvider._resolve_query("barat", "")
        self.assertIn(q, CATEGORY_QUERIES["barat"])

    def test_resolve_query_fallback(self):
        self.assertEqual(
            DeezerMusicProvider._resolve_query("zzz", ""), "top hits")


class TestFactory(unittest.TestCase):
    def test_mock(self):
        self.assertIsInstance(create_music_provider("mock"), MockMusicProvider)

    def test_deezer(self):
        self.assertIsInstance(create_music_provider("deezer"), DeezerMusicProvider)

    def test_unknown_fallback(self):
        self.assertIsInstance(create_music_provider("nope"), MockMusicProvider)

    def test_fail_inject(self):
        p = create_music_provider("deezer", fail_inject="music")
        self.assertTrue(p._fail_inject)


if __name__ == "__main__":
    unittest.main()
