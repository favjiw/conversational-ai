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


class MusicSearchRequest(BaseModel):
    """Parameters for a music search call."""

    category: str = ""  # clock slot category
    query: str = ""  # free-text override (e.g. from emotion classifier)
    mood: str = ""  # emotion tag for FR-7
    duration_target_sec: int = 180
    limit: int = 5
