"""Data models for the music module (FR-7).

Defines the track representation returned by every MusicProvider and the
search request used by the orchestrator / emotion classifier.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MusicTrack(BaseModel):
    """A single music track returned by a MusicProvider."""

    id: str
    title: str
    artist: str
    album: str = ""
    duration_sec: int = 0
    preview_url: str = ""
    preview_duration_sec: int = 30
    category: str = ""  # indo_hits | indo | barat | korea
    source: str = ""  # deezer | mock
    image_url: str = ""
    link: str = ""  # attribution link to the source platform
    # Asal pilihan lagu (kosong = perilaku lama): comment | talk_mood | category | fallback
    rec_source: str = ""
    requested_by: str = ""  # username penonton yang me-request
    request_comment: str = ""  # isi komentar request
    host_line: str = ""  # bahan intro dari modul rekomendasi (bukan dibacakan mentah)
    reason: str = ""  # alasan pemilihan dari modul rekomendasi
    catalog_song_id: str = ""  # song_id di katalog hits_rec


class CatalogSong(BaseModel):
    """Lagu katalog hits_rec yang dipilih modul rekomendasi (belum punya audio)."""

    song_id: str
    title: str
    artist: str
    language: str = ""
    genre: str = ""
    year: int | None = None
    moods: list[str] = Field(default_factory=list)
    energy: str = ""
    valence: str = ""


class SongRecommendation(BaseModel):
    """Hasil satu permintaan ke modul rekomendasi, sudah dalam bentuk milik backend ini."""

    status: str = "ok"  # ok | disabled | timeout | error
    comment: str = ""
    username: str = ""
    intent: str = ""  # explicit_song | mood_request | not_a_request | "" (gagal)
    needs_moderation: bool = False
    song: CatalogSong | None = None
    reason: str = ""
    host_line: str = ""
    note: str = ""
    timings: dict[str, float] = Field(default_factory=dict)  # detik per langkah (intent, retrieval, rerank, total)


class MusicSearchRequest(BaseModel):
    """Parameters for a music search call."""

    category: str = ""  # clock slot category
    query: str = ""  # free-text override (e.g. from emotion classifier)
    mood: str = ""  # emotion tag for FR-7
    duration_target_sec: int = 180
    limit: int = 5
