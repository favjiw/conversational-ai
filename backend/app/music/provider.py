"""Music provider abstraction (FR-7).

Supports Deezer (30-sec preview, public API, no key needed) and Mock mode.
Pattern follows TTSProvider / LLMClient: ABC → concrete impls → factory.

Deezer was chosen over Spotify because Spotify revoked preview_url access
for new apps (Nov 2024).  Deezer's public ``/search`` endpoint returns a
``preview`` field with a direct MP3 URL — no auth, no API key.
"""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.music.models import MusicTrack

logger = logging.getLogger(__name__)


# ── Category → Deezer search query mapping ───────────────────────────────────

CATEGORY_QUERIES: dict[str, list[str]] = {
    "indo_hits": [
        "top indonesia 2024",
        "hits indonesia terbaru",
        "juicy luicy",
        "mahalini",
        "tulus",
    ],
    "indo": [
        "pop indonesia",
        "lagu indonesia populer",
        "rizky febian",
        "nadin amizah",
        "fiersa besari",
    ],
    "barat": [
        "top hits global",
        "pop hits 2024",
        "the weeknd",
        "dua lipa",
        "bruno mars",
    ],
    "korea": [
        "kpop top",
        "blackpink",
        "bts",
        "newjeans",
        "aespa",
    ],
}

DEFAULT_QUERY = "top hits"


# ── Provider interface ───────────────────────────────────────────────────────


class MusicProvider(ABC):
    """Abstract music provider interface."""

    @abstractmethod
    async def search(
        self,
        category: str = "",
        query: str = "",
        limit: int = 5,
    ) -> list[MusicTrack]:
        """Search for tracks."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


# ── Mock provider ────────────────────────────────────────────────────────────

_MOCK_TRACKS: list[dict] = [
    {"id": "mock_1", "title": "Lagu Mock Indonesia",
     "artist": "Mock Artist ID", "album": "Mock Album",
     "duration_sec": 210, "category": "indo"},
    {"id": "mock_2", "title": "Mock Pop Hit",
     "artist": "Mock Artist EN", "album": "Mock Album EN",
     "duration_sec": 195, "category": "barat"},
    {"id": "mock_3", "title": "Mock K-pop",
     "artist": "Mock Group KR", "album": "Mock Album KR",
     "duration_sec": 200, "category": "korea"},
    {"id": "mock_4", "title": "Mock Indo Hits",
     "artist": "Mock Artist Hits", "album": "Mock Hits Album",
     "duration_sec": 185, "category": "indo_hits"},
]



# ── Deezer provider ─────────────────────────────────────────────────────────

DEEZER_SEARCH_URL = "https://api.deezer.com/search"


class DeezerMusicProvider(MusicProvider):
    """Fetches 30-sec preview MP3s via Deezer public search API.

    No API key required.  The ``preview`` field in the track object is a
    direct-play MP3 URL.
    """

    MAX_RETRIES = 2
    TIMEOUT_SEC = 10.0

    def __init__(self, fail_inject: bool = False) -> None:
        self._fail_inject = fail_inject

    async def search(
        self, category: str = "", query: str = "", limit: int = 5,
    ) -> list[MusicTrack]:
        if self._fail_inject:
            raise RuntimeError("FAIL_INJECT: music provider failure")

        search_query = self._resolve_query(category, query)
        logger.info("Deezer search: category=%s query=%r", category, search_query)

        raw = await self._call_api(search_query, limit=limit + 5)
        tracks: list[MusicTrack] = []
        for item in raw:
            preview = item.get("preview", "")
            if not preview:
                continue
            artist_obj = item.get("artist", {})
            album_obj = item.get("album", {})
            tracks.append(MusicTrack(
                id=str(item.get("id", "")),
                title=item.get("title", ""),
                artist=artist_obj.get("name", ""),
                album=album_obj.get("title", ""),
                duration_sec=item.get("duration", 0),
                preview_url=preview,
                preview_duration_sec=30,
                category=category,
                source="deezer",
                image_url=album_obj.get("cover_medium", ""),
                link=item.get("link", ""),
            ))
            if len(tracks) >= limit:
                break

        logger.info("Deezer returned %d tracks with preview", len(tracks))
        return tracks

    @property
    def provider_name(self) -> str:
        return "deezer"

    @staticmethod
    def _resolve_query(category: str, query: str) -> str:
        if query:
            return query
        queries = CATEGORY_QUERIES.get(category)
        if queries:
            return random.choice(queries)
        return DEFAULT_QUERY

    async def _call_api(self, query: str, limit: int = 10) -> list[dict]:
        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT_SEC) as client:
                    resp = await client.get(
                        DEEZER_SEARCH_URL,
                        params={"q": query, "limit": limit},
                    )
                    resp.raise_for_status()
                    return resp.json().get("data", [])
            except Exception as exc:
                last_error = exc
                logger.warning("Deezer error (attempt %d): %s", attempt + 1, exc)
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(1.0 * (attempt + 1))
        logger.error("Deezer failed after retries: %s", last_error)
        return []


# ── Factory ──────────────────────────────────────────────────────────────────


def create_music_provider(
    provider: str = "mock",
    fail_inject: str = "",
) -> MusicProvider:
    """Create MusicProvider based on config.

    Args:
        provider: ``"mock"`` or ``"deezer"``.
        fail_inject: If contains ``"music"``, inject failures.
    """
    inject = "music" in fail_inject
    if provider == "deezer":
        logger.info("Using DeezerMusicProvider")
        return DeezerMusicProvider(fail_inject=inject)
    if provider != "mock":
        logger.warning("Unknown MUSIC_PROVIDER=%r, falling back to mock", provider)
    logger.info("Using MockMusicProvider")
    return MockMusicProvider()


class MockMusicProvider(MusicProvider):
    """Deterministic mock — returns canned tracks, no network."""

    async def search(
        self, category: str = "", query: str = "", limit: int = 5,
    ) -> list[MusicTrack]:
        await asyncio.sleep(0.02)
        pool = [t for t in _MOCK_TRACKS
                if not category or t["category"] == category]
        if not pool:
            pool = _MOCK_TRACKS
        return [
            MusicTrack(
                id=t["id"], title=t["title"], artist=t["artist"],
                album=t["album"], duration_sec=t["duration_sec"],
                preview_url="", category=t["category"], source="mock",
            )
            for t in pool[:limit]
        ]

    @property
    def provider_name(self) -> str:
        return "mock"
