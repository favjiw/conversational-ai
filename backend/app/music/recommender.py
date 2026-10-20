"""Adapter modul rekomendasi lagu ``hits_rec`` (repo ffromme/hits-song-recommender, karya Iam).

Kode rekan tidak diedit; semua penyesuaian ada di sini:

- ``hits_rec.config`` membaca ``LLM_*`` dari ``os.environ`` saat import, jadi env diisi dari
  ``Settings`` kita dulu, lalu ``hits_rec`` di-import secara lazy di thread latar.
- Model embedding dimuat ±10–30 s, jadi pemuatan berjalan di thread latar dengan status
  ``loading | ready | disabled | error``. Selama belum ``ready`` semua panggilan langsung
  mengembalikan status ``disabled`` dan pemanggil memakai fallback (Deezer per kategori).
- Fungsi ``hits_rec`` sinkron: dijalankan di satu worker thread (antre satu per satu, sekaligus
  membatasi beban ke LLM) dengan batas waktu ``RECOMMENDER_TIMEOUT_SEC``.
- Klien OpenAI bawaan rekan memakai ``max_retries=5, timeout=120``; di live itu terlalu lama,
  jadi diganti klien dengan retry 1 kali dan timeout sama dengan batas waktu rekomendasi.
- Cooldown: ``Recommender.recommend`` langsung memanggil ``history.add``. Di sini ``add`` hanya
  *memesan* lagu (agar tidak dipilih dua kali selama menunggu giliran). Lagu baru masuk riwayat
  putar lewat ``mark_played`` saat benar-benar on-air, dan pesanan dilepas lewat ``release``
  bila request batal atau hasilnya datang terlambat.
- Katalog tidak punya audio: audio dicari di Deezer (``artist title``) lalu judul + artis
  dicocokkan secara fuzzy sebelum dipakai.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor
from difflib import SequenceMatcher
from typing import Any, Callable, Optional

from app.music.models import CatalogSong, MusicTrack, SongRecommendation
from app.music.provider import MusicProvider

logger = logging.getLogger(__name__)

# Bahasa katalog per kategori slot. Katalog belum punya lagu Korea, jadi slot "korea" tidak dilayani.
CATEGORY_LANGUAGE: dict[str, str] = {
    "indo_hits": "id",
    "indo": "id",
    "barat": "en",
}

TITLE_MIN_SCORE = 0.85  # kemiripan minimal judul katalog vs judul Deezer
ARTIST_MIN_SCORE = 0.85
COOLDOWN_SIZE = 10  # sama dengan hits_rec.config.COOLDOWN_N
TALK_MOOD_SITUATION = (
    "Penyiar baru selesai membahas topik ini di segmen Talk. Pilih lagu yang paling nyambung "
    "dengan suasana obrolannya."
)


# ── Riwayat putar dengan pemesanan ──────────────────────────────────────────


class ReservingHistory:
    """Pengganti ``hits_rec.retrieval.PlayHistory`` (duck typing, thread-safe).

    Lagu dianggap sedang cooldown bila termasuk ``size`` lagu terakhir yang benar-benar diputar
    *atau* sedang dipesan oleh request yang menunggu.
    """

    def __init__(self, size: int = COOLDOWN_SIZE) -> None:
        self._played: deque[str] = deque(maxlen=size)
        self._reserved: Counter[str] = Counter()
        self._lock = threading.Lock()

    def add(self, song_id: str) -> None:
        # Dipanggil hits_rec saat lagu dipilih: hanya dipesan, belum diputar.
        with self._lock:
            self._reserved[song_id] += 1

    def release(self, song_id: str) -> None:
        with self._lock:
            if self._reserved[song_id] > 0:
                self._reserved[song_id] -= 1
            if self._reserved[song_id] <= 0:
                del self._reserved[song_id]

    def mark_played(self, song_id: str) -> None:
        with self._lock:
            if self._reserved.get(song_id, 0) > 0:
                self._reserved[song_id] -= 1
                if self._reserved[song_id] <= 0:
                    del self._reserved[song_id]
            self._played.append(song_id)

    def __contains__(self, song_id: object) -> bool:
        with self._lock:
            return song_id in self._played or song_id in self._reserved

    def __len__(self) -> int:
        with self._lock:
            return len(self._played) + len(self._reserved)

    def __bool__(self) -> bool:
        # hits_rec memakai ``history or PlayHistory()``: riwayat kosong tidak boleh dianggap "tidak ada".
        return True


# ── Pembungkus hits_rec (satu-satunya tempat yang meng-import hits_rec) ─────


def _apply_env(settings: Any) -> None:
    """Isi env yang dibaca ``hits_rec.config`` saat import. Nilai Settings kita yang berlaku."""
    os.environ["LLM_API_KEY"] = settings.RECOMMENDER_LLM_API_KEY
    os.environ["LLM_BASE_URL"] = settings.RECOMMENDER_LLM_BASE_URL
    os.environ["LLM_MODEL"] = settings.RECOMMENDER_LLM_MODEL
    if settings.RECOMMENDER_LLM_REASONING_EFFORT:
        os.environ["LLM_REASONING_EFFORT"] = settings.RECOMMENDER_LLM_REASONING_EFFORT
    else:
        os.environ.pop("LLM_REASONING_EFFORT", None)


class HitsRecBackend:
    """Memuat ``hits_rec`` dan menyediakan panggilan sinkron yang dipakai layanan."""

    def __init__(self, settings: Any, history: ReservingHistory) -> None:
        _apply_env(settings)
        from openai import OpenAI

        from hits_rec import llm
        from hits_rec.config import RERANK_CANDIDATES
        from hits_rec.pipeline import Recommender
        from hits_rec.rerank import rerank
        from hits_rec.retrieval import search_by_mood

        # Cache jawaban LLM rekan (.cache/llm/): hemat kuota, tapi latensi di log jadi tidak nyata.
        llm.cache_enabled = bool(getattr(settings, "RECOMMENDER_LLM_CACHE", False))
        llm._client = OpenAI(
            api_key=settings.RECOMMENDER_LLM_API_KEY,
            base_url=settings.RECOMMENDER_LLM_BASE_URL,
            max_retries=1,
            timeout=settings.RECOMMENDER_TIMEOUT_SEC,
        )
        self._history = history
        self._rerank = rerank
        self._search_by_mood = search_by_mood
        self._rerank_candidates = RERANK_CANDIDATES
        self._recommender = Recommender(history=history)

    def recommend(self, comment: str) -> Any:
        return self._recommender.recommend(comment)

    def recommend_mood(self, mood_text: str, language: Optional[str]) -> Any:
        """Lagu untuk mood topik Talk (tanpa komentar). Mengembalikan objek bentuk PipelineResult."""
        timings: dict[str, float] = {}
        start = time.perf_counter()
        scored = self._search_by_mood(mood_text, None, language, self._history)
        timings["retrieval"] = time.perf_counter() - start
        candidates = [song for song, _ in scored][: self._rerank_candidates]
        recommendation = None
        note = "tidak ada kandidat"
        if candidates:
            step = time.perf_counter()
            recommendation = self._rerank(mood_text, TALK_MOOD_SITUATION, candidates)
            timings["rerank"] = time.perf_counter() - step
            self._history.add(recommendation.song.song_id)
            note = "mood topik Talk"
        timings["total"] = time.perf_counter() - start
        return _Result(intent=None, recommendation=recommendation, note=note, timings=timings)


class _Result:
    """Bentuk minimal PipelineResult untuk jalur mood Talk."""

    def __init__(self, intent: Any, recommendation: Any, note: str, timings: dict[str, float]) -> None:
        self.intent = intent
        self.recommendation = recommendation
        self.note = note
        self.timings = timings


# ── Layanan ─────────────────────────────────────────────────────────────────


BackendFactory = Callable[[Any, ReservingHistory], Any]


class SongRecommenderService:
    """Layanan rekomendasi lagu untuk backend. Setiap kegagalan berakhir di status, bukan exception."""

    def __init__(
        self,
        settings: Any,
        music: MusicProvider,
        backend_factory: Optional[BackendFactory] = None,
    ) -> None:
        self._settings = settings
        self._music = music
        self._factory: BackendFactory = backend_factory or HitsRecBackend
        self._history = ReservingHistory()
        self._backend: Any = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._loader: Optional[threading.Thread] = None
        self.status, self.reason = self._initial_status()
        self.load_sec: Optional[float] = None

    @property
    def timeout_sec(self) -> float:
        return float(self._settings.RECOMMENDER_TIMEOUT_SEC)

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def _initial_status(self) -> tuple[str, str]:
        s = self._settings
        if not s.RECOMMENDER_ENABLED:
            return "disabled", "RECOMMENDER_ENABLED=false"
        if s.LLM_MODE == "mock":
            return "disabled", "LLM_MODE=mock"
        if not s.RECOMMENDER_LLM_API_KEY:
            return "disabled", "RECOMMENDER_LLM_API_KEY kosong"
        return "loading", ""

    def status_info(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "model": self._settings.RECOMMENDER_LLM_MODEL if self.status != "disabled" else "",
            "load_sec": self.load_sec,
            "talk_mood": bool(self._settings.RECOMMENDER_TALK_MOOD),
        }

    # ── Siklus hidup ──

    def start_loading(self) -> None:
        """Muat hits_rec di thread latar; tidak memblok startup backend."""
        if self.status != "loading" or self._loader is not None:
            return
        self._loader = threading.Thread(target=self._load, name="song-recommender-load", daemon=True)
        self._loader.start()

    def load_now(self) -> None:
        """Muat secara sinkron (untuk tes dan skrip)."""
        if self.status == "loading":
            self._load()

    def _load(self) -> None:
        started = time.perf_counter()
        try:
            backend = self._factory(self._settings, self._history)
        except ImportError as exc:
            self.status, self.reason = "disabled", f"paket hits_rec belum terinstal ({exc})"
            logger.warning("Song recommender disabled: %s", self.reason)
            return
        except Exception as exc:  # model/indeks gagal dimuat
            self.status, self.reason = "error", f"{type(exc).__name__}: {exc}"
            logger.error("Song recommender failed to load: %s", self.reason, exc_info=True)
            return
        self._backend = backend
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="song-recommender")
        self.load_sec = round(time.perf_counter() - started, 1)
        self.status, self.reason = "ready", ""
        logger.info("Song recommender ready in %.1fs", self.load_sec)

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # ── Rekomendasi ──

    async def recommend_for_comment(self, username: str, text: str) -> SongRecommendation:
        base = SongRecommendation(comment=text, username=username)
        if not self.ready:
            return base.model_copy(update={"status": "disabled", "note": self.reason or self.status})
        return await self._run(base, lambda: self._backend.recommend(text))

    async def recommend_for_mood(self, mood_text: str, category: str) -> SongRecommendation:
        """Lagu berbasis mood topik Talk, dengan filter bahasa dari kategori slot."""
        base = SongRecommendation(comment=mood_text)
        if not self.ready:
            return base.model_copy(update={"status": "disabled", "note": self.reason or self.status})
        language = CATEGORY_LANGUAGE.get(category)
        if language is None:
            return base.model_copy(update={"status": "disabled", "note": f"kategori {category!r} tidak ada di katalog"})
        return await self._run(base, lambda: self._backend.recommend_mood(mood_text, language))

    async def _run(self, base: SongRecommendation, call: Callable[[], Any]) -> SongRecommendation:
        assert self._executor is not None
        started = time.perf_counter()
        future: Future = self._executor.submit(call)
        try:
            raw = await asyncio.wait_for(asyncio.wrap_future(future), timeout=self.timeout_sec)
        except asyncio.TimeoutError:
            # Thread tidak bisa dihentikan paksa. Bila hasilnya datang terlambat, lepas pesanan lagunya.
            future.add_done_callback(self._release_late_result)
            logger.warning("Song recommender timeout after %.1fs: %r", self.timeout_sec, base.comment)
            return base.model_copy(update={
                "status": "timeout",
                "note": f"melebihi {self.timeout_sec:g} s",
                "timings": {"total": round(time.perf_counter() - started, 3)},
            })
        except Exception as exc:
            logger.warning("Song recommender error: %s", exc, exc_info=True)
            return base.model_copy(update={"status": "error", "note": f"{type(exc).__name__}: {exc}"})
        return self._convert(base, raw)

    def _release_late_result(self, future: Future) -> None:
        if future.cancelled() or future.exception() is not None:
            return
        song_id = _song_id_of(future.result())
        if song_id:
            self._history.release(song_id)

    @staticmethod
    def _convert(base: SongRecommendation, raw: Any) -> SongRecommendation:
        intent = getattr(raw, "intent", None)
        rec = getattr(raw, "recommendation", None)
        song = getattr(rec, "song", None) if rec else None
        return base.model_copy(update={
            "status": "ok",
            "intent": getattr(intent, "type", "") or "",
            "needs_moderation": bool(getattr(intent, "needs_moderation", False)),
            "song": _catalog_song(song) if song is not None else None,
            "reason": getattr(rec, "reason", "") if rec else "",
            "host_line": getattr(rec, "host_line", "") if rec else "",
            "note": getattr(raw, "note", "") or "",
            "timings": {k: round(float(v), 3) for k, v in (getattr(raw, "timings", {}) or {}).items()},
        })

    # ── Cooldown ──

    def mark_played(self, song_id: str) -> None:
        """Lagu katalog benar-benar diputar: masuk riwayat cooldown."""
        if song_id:
            self._history.mark_played(song_id)

    def release(self, song_id: str) -> None:
        """Request batal / tidak dipakai: lepas pesanan lagu."""
        if song_id:
            self._history.release(song_id)

    # ── Audio ──

    async def resolve_audio(self, song: CatalogSong, category: str = "") -> Optional[MusicTrack]:
        """Cari audio lagu katalog di provider musik; None bila tidak ada yang cocok."""
        started = time.perf_counter()
        try:
            tracks = await self._music.search(category=category, query=f"{song.artist} {song.title}", limit=5)
        except Exception as exc:
            logger.warning("Audio search failed for %s - %s: %s", song.artist, song.title, exc)
            return None
        elapsed = time.perf_counter() - started
        for track in tracks:
            if track.preview_url and titles_match(song.title, track.title) and artists_match(song.artist, track.artist):
                logger.info("Audio for %s - %s found in %.2fs (%s)", song.artist, song.title, elapsed, track.id)
                return track.model_copy(update={
                    "catalog_song_id": song.song_id,
                    "category": category or track.category,
                })
        logger.info("No matching audio for %s - %s (%d results, %.2fs)", song.artist, song.title, len(tracks), elapsed)
        return None


# ── Bantuan ─────────────────────────────────────────────────────────────────


def _catalog_song(song: Any) -> CatalogSong:
    return CatalogSong(
        song_id=str(getattr(song, "song_id", "")),
        title=getattr(song, "title", ""),
        artist=getattr(song, "artist", ""),
        language=getattr(song, "language", "") or "",
        genre=getattr(song, "genre", "") or "",
        year=getattr(song, "year", None),
        moods=list(getattr(song, "moods", []) or []),
        energy=getattr(song, "energy", "") or "",
        valence=getattr(song, "valence", "") or "",
    )


def _song_id_of(raw: Any) -> str:
    rec = getattr(raw, "recommendation", None)
    song = getattr(rec, "song", None) if rec else None
    return str(getattr(song, "song_id", "") or "")


_PAREN = re.compile(r"[\(\[].*?[\)\]]")
_SUFFIX = re.compile(r"\s+-\s+.*$")  # "Judul - Remastered 2011", "Judul - Live"
_FEAT = re.compile(r"\b(feat\.?|ft\.?|featuring)\b.*$")
_ARTIST_SPLIT = re.compile(r"\s*(?:,|&|\bfeat\.?|\bft\.?|\bfeaturing\b|\band\b|\bx\b|\bwith\b)\s*")


def _normalize(text: str) -> str:
    text = text.lower()
    text = _PAREN.sub(" ", text)
    text = _SUFFIX.sub("", text)
    text = _FEAT.sub("", text)
    text = re.sub(r"[^0-9a-z]+", " ", text)
    return " ".join(text.split())


def _close(a: str, b: str, min_score: float) -> bool:
    if not a or not b:
        return False
    return a == b or SequenceMatcher(None, a, b).ratio() >= min_score


def titles_match(catalog_title: str, found_title: str) -> bool:
    return _close(_normalize(catalog_title), _normalize(found_title), TITLE_MIN_SCORE)


def artists_match(catalog_artist: str, found_artist: str) -> bool:
    """Cocok bila salah satu artis katalog (kolaborasi dipecah) sama dengan artis hasil pencarian."""
    found = _normalize(found_artist)
    parts = [_normalize(p) for p in _ARTIST_SPLIT.split(catalog_artist.lower()) if p.strip()]
    return any(_close(p, found, ARTIST_MIN_SCORE) for p in parts)
