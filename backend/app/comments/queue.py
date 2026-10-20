"""Antrean komentar penonton dan request lagu.

Setiap komentar diklasifikasi satu per satu lewat modul rekomendasi (``SongRecommenderService``):

- ``explicit_song`` / ``mood_request`` dengan lagu → antrean request lagu (status ``waiting``),
  dipakai ``ClockRunner`` untuk slot lagu berikutnya;
- ``not_a_request`` → komentar umum (``general``) untuk segmen Talk nanti;
- ``needs_moderation`` → ``rejected``: tidak masuk antrean mana pun, dicatat di log, dan hanya
  console yang diberi tahu.

Batas beban LLM: klasifikasi berjalan satu per satu, jumlah request yang menunggu dibatasi
``max_pending``, satu request aktif per username, dan duplikat dibuang. Komentar yang melewati
batas request tetap diklasifikasi (moderasi tetap jalan) lalu disimpan sebagai komentar umum.
LLM hanya dilewati bila antrean klasifikasi menumpuk atau layanan belum siap; komentar itu
disimpan sebagai komentar umum dengan ``moderated=False``.

Komentar tidak memotong lagu (KEPUTUSAN-DESAIN §3.B.7): antrean ini hanya menyimpan; yang
memutuskan kapan dipakai adalah Rundown Engine.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.music.models import SongRecommendation

logger = logging.getLogger(__name__)

# Status komentar
CLASSIFYING = "classifying"  # menunggu diklasifikasi
WAITING = "waiting"  # request lagu menunggu slot (menunggu)
SCHEDULED = "scheduled"  # dijadwalkan di slot lagu tertentu
PLAYED = "played"  # sudah diputar
REJECTED = "rejected"  # ditolak moderasi
UNAVAILABLE = "unavailable"  # request tanpa lagu yang bisa diputar (tidak tersedia)
GENERAL = "general"  # komentar biasa untuk segmen Talk

ACTIVE_REQUEST = (WAITING, SCHEDULED)
REQUEST_INTENTS = ("explicit_song", "mood_request")
MAX_TEXT_LEN = 300
MAX_USERNAME_LEN = 64
DUPLICATE_WINDOW_SEC = 300.0
MAX_ENTRIES = 500  # entri lama yang sudah selesai dibuang

Broadcast = Callable[[str, dict[str, Any], Optional[tuple[str, ...]]], Awaitable[None]]


class CommentIn(BaseModel):
    """Body ``POST /api/comments``."""

    username: str = Field(min_length=1, max_length=MAX_USERNAME_LEN)
    text: str = Field(min_length=1, max_length=MAX_TEXT_LEN)


class CommentEntry(BaseModel):
    id: str
    username: str
    text: str
    received_at: float
    status: str = CLASSIFYING
    moderated: bool = False  # sudah melewati klasifikasi/moderasi LLM
    slot_id: str = ""  # slot lagu tempat request dijadwalkan/diputar
    note: str = ""
    recommendation: Optional[SongRecommendation] = None

    def public(self) -> dict[str, Any]:
        """Bentuk untuk WS/HTTP."""
        rec = self.recommendation
        return {
            "id": self.id,
            "username": self.username,
            "text": self.text,
            "received_at": self.received_at,
            "status": self.status,
            "moderated": self.moderated,
            "slot_id": self.slot_id,
            "note": self.note,
            "intent": rec.intent if rec else "",
            "song": rec.song.model_dump() if rec and rec.song else None,
            "timings": rec.timings if rec else {},
        }


def normalize_username(name: str) -> str:
    return name.strip().lstrip("@").strip()


def _dedupe_key(username: str, text: str) -> tuple[str, str]:
    return username.lower(), " ".join(text.lower().split())


class CommentQueue:
    def __init__(
        self,
        recommender: Any,
        broadcast: Optional[Broadcast] = None,
        max_pending: int = 5,
        event_log: Optional[Any] = None,
    ) -> None:
        self._recommender = recommender
        self._broadcast = broadcast
        self._event_log = event_log  # MusicEventLogger (opsional)
        self.max_pending = max(1, int(max_pending))
        self._entries: list[CommentEntry] = []
        self._sem = asyncio.Semaphore(1)  # satu klasifikasi LLM pada satu waktu
        self._tasks: set[asyncio.Task] = set()

    # ── Masukan ──

    async def submit(self, username: str, text: str) -> tuple[CommentEntry, bool]:
        """Simpan komentar baru. Mengembalikan (entri, duplikat?)."""
        username = normalize_username(username)
        text = " ".join(text.split())
        if not username or not text:
            raise ValueError("username dan text wajib diisi")

        dup = self._find_duplicate(username, text)
        if dup is not None:
            logger.info("Duplicate comment from @%s ignored", username)
            return dup, True

        entry = CommentEntry(id=uuid.uuid4().hex[:10], username=username, text=text, received_at=time.time())
        self._entries.append(entry)
        self._trim()

        # Batas per username / antrean penuh tetap diklasifikasi (moderasi tetap jalan) dan dicek
        # lagi setelahnya; LLM hanya dilewati bila antrean klasifikasi sendiri sudah menumpuk.
        backlog = sum(1 for e in self._entries if e is not entry and e.status == CLASSIFYING)
        skip_reason = "terlalu banyak komentar menunggu klasifikasi" if backlog >= self.max_pending else ""
        if skip_reason or not self._recommender.ready:
            # Tanpa klasifikasi: langsung jadi komentar umum (belum dimoderasi LLM).
            entry.status = GENERAL
            entry.note = skip_reason or f"rekomendasi {self._recommender.status}: tidak diklasifikasi"
            self._log_comment(entry)
            await self._announce(entry)
            return entry, False

        task = asyncio.create_task(self._classify(entry))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        await self._emit_queue()
        return entry, False

    def _find_duplicate(self, username: str, text: str) -> Optional[CommentEntry]:
        key = _dedupe_key(username, text)
        cutoff = time.time() - DUPLICATE_WINDOW_SEC
        for entry in reversed(self._entries):
            if entry.received_at < cutoff:
                break
            if _dedupe_key(entry.username, entry.text) == key:
                return entry
        return None

    def _limit_reason(self, username: str, exclude: Optional[CommentEntry] = None) -> str:
        """Alasan komentar ini tidak boleh menjadi request lagu ('' = boleh)."""
        user = username.lower()
        busy = [e for e in self._entries if e is not exclude and e.status in ACTIVE_REQUEST + (CLASSIFYING,)]
        if any(e.username.lower() == user and e.status in ACTIVE_REQUEST for e in busy):
            return f"@{username} sudah punya request aktif"
        if sum(1 for e in busy if e.status == WAITING) >= self.max_pending:
            return f"antrean request penuh ({self.max_pending})"
        return ""

    async def _classify(self, entry: CommentEntry) -> None:
        async with self._sem:
            rec: SongRecommendation = await self._recommender.recommend_for_comment(entry.username, entry.text)
        entry.recommendation = rec

        if rec.status != "ok":
            # Rekomendasi gagal/timeout: simpan sebagai komentar biasa (belum dimoderasi).
            entry.status = GENERAL
            entry.note = f"klasifikasi {rec.status}: {rec.note}"
        elif rec.needs_moderation:
            entry.moderated = True
            entry.status = REJECTED
            entry.note = rec.note or "perlu moderasi"
            logger.warning("Comment rejected by moderation: @%s %r", entry.username, entry.text)
        elif rec.intent in REQUEST_INTENTS:
            entry.moderated = True
            limit = self._limit_reason(entry.username, exclude=entry)
            if limit:
                self._release(entry)
                entry.status = GENERAL
                entry.note = limit
            elif rec.song is None:
                entry.status = UNAVAILABLE
                entry.note = rec.note or "tidak ada lagu yang cocok"
            else:
                entry.status = WAITING
                entry.note = rec.note
        else:
            entry.moderated = True
            entry.status = GENERAL
            entry.note = rec.note
        logger.info("Comment @%s -> %s (%s) %s", entry.username, entry.status, rec.intent or "-",
                    rec.song.title if rec.song else "")
        self._log_comment(entry)
        await self._announce(entry)

    # ── Dipakai ClockRunner (Tahap 3) ──

    def next_request(self) -> Optional[CommentEntry]:
        """Request lagu tertua yang masih menunggu (tidak mengubah status)."""
        return next((e for e in self._entries if e.status == WAITING), None)

    async def schedule(self, entry_id: str, slot_id: str) -> None:
        await self._set_status(entry_id, SCHEDULED, slot_id=slot_id)

    async def notify_scheduled(self, entry_id: str, slot_id: str, track: dict[str, Any],
                               audio_search_sec: float = 0.0) -> None:
        """Request sudah punya audio dan dijadwalkan di slot ``slot_id`` (console saja)."""
        entry = self.get(entry_id)
        if entry is None:
            return
        await self._send("song_request_scheduled", {
            "comment": entry.public(),
            "slot_id": slot_id,
            "track": track,
            "audio_search_sec": round(audio_search_sec, 3),
        }, ("console",))

    async def mark_played(self, entry_id: str) -> None:
        entry = self.get(entry_id)
        if entry and entry.recommendation and entry.recommendation.song:
            self._recommender.mark_played(entry.recommendation.song.song_id)
        await self._set_status(entry_id, PLAYED)

    async def return_to_queue(self, entry_id: str) -> None:
        """Request belum diputar (skip/stop saat persiapan): kembali menunggu di urutan semula."""
        await self._set_status(entry_id, WAITING, slot_id="")

    async def mark_unavailable(self, entry_id: str, note: str) -> None:
        entry = self.get(entry_id)
        if entry:
            self._release(entry)
        await self._set_status(entry_id, UNAVAILABLE, note=note)

    async def _set_status(self, entry_id: str, status: str, **fields: Any) -> None:
        entry = self.get(entry_id)
        if entry is None:
            return
        entry.status = status
        for key, value in fields.items():
            setattr(entry, key, value)
        if self._event_log is not None:
            self._event_log.log("request_status", comment_id=entry.id, username=entry.username,
                                status=status, slot_id=entry.slot_id, note=entry.note)
        await self._emit_queue()

    # ── Baca ──

    def get(self, entry_id: str) -> Optional[CommentEntry]:
        return next((e for e in self._entries if e.id == entry_id), None)

    def entries(self) -> list[CommentEntry]:
        return list(self._entries)

    def general_comments(self) -> list[CommentEntry]:
        return [e for e in self._entries if e.status == GENERAL]

    def snapshot(self, limit: int = 50) -> dict[str, Any]:
        recent = self._entries[-limit:]
        return {
            "recommender": self._recommender.status_info(),
            "max_pending": self.max_pending,
            "waiting": sum(1 for e in self._entries if e.status == WAITING),
            "comments": [e.public() for e in reversed(recent)],
        }

    async def wait_idle(self) -> None:
        """Tunggu semua klasifikasi selesai (untuk tes)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    # ── Internal ──

    def _log_comment(self, entry: CommentEntry) -> None:
        if self._event_log is None:
            return
        rec = entry.recommendation
        self._event_log.log(
            "comment",
            comment_id=entry.id,
            username=entry.username,
            text=entry.text,
            status=entry.status,
            moderated=entry.moderated,
            rec_status=rec.status if rec else "skipped",
            intent=rec.intent if rec else "",
            song=rec.song.model_dump() if rec and rec.song else None,
            note=entry.note,
            timings=rec.timings if rec else {},
        )

    def _release(self, entry: CommentEntry) -> None:
        rec = entry.recommendation
        if rec and rec.song:
            self._recommender.release(rec.song.song_id)

    def _trim(self) -> None:
        excess = len(self._entries) - MAX_ENTRIES
        if excess <= 0:
            return
        done = (PLAYED, REJECTED, UNAVAILABLE, GENERAL)
        keep: list[CommentEntry] = []
        for entry in self._entries:
            if excess > 0 and entry.status in done:
                excess -= 1
                continue
            keep.append(entry)
        self._entries = keep

    async def _announce(self, entry: CommentEntry) -> None:
        if entry.status == REJECTED:
            await self._send("comment_rejected", entry.public(), ("console",))
        else:
            # Event yang sama dipakai /stage untuk reading_comments (rencana Tahap 4 /stage).
            await self._send("comment", entry.public(), None)
        await self._emit_queue()

    async def _emit_queue(self) -> None:
        await self._send("comment_queue", self.snapshot(), ("console",))

    async def _send(self, event_type: str, data: dict[str, Any], roles: Optional[tuple[str, ...]]) -> None:
        if not self._broadcast:
            return
        try:
            await self._broadcast(event_type, data, roles)
        except Exception as exc:
            logger.warning("Comment broadcast failed: %s", exc)
