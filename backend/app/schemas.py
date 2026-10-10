"""Pydantic models for every data structure defined in PRD Section 10.

These models serve as the single source of truth for:
- Clock / Slot / Tema schema  (FR-1)
- Persona cards
- LLM output structures (persona reply, supervisor verdict)
- Turn-level logging (FR-11)
- Experiment metadata (FR-12)

All JSON files in ``data/`` and all JSONL log lines MUST validate against
these models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class SlotType(str, Enum):
    SMASH = "smash"
    TIME_SIGNAL = "time_signal"
    JINGLE = "jingle"
    PSA = "psa"
    GREETINGS_ARTIS = "greetings_artis"
    IMAGE_MASHUP = "image_mashup"
    SMASH_VERSI = "smash_versi"
    SONG = "song"
    SONG_BLOCK = "song_block"
    SPOT_ADLIBS = "spot_adlibs"
    ICE_BREAKING = "ice_breaking"
    TALK = "talk"
    TIME_MARKER = "time_marker"
    SELLING_NEXT_HOUR = "selling_next_hour"


class SlotSource(str, Enum):
    STATIC_AUDIO = "static_audio"
    TTS = "tts"
    MUSIC_API = "music_api"
    LLM_CONVERSATION = "llm_conversation"
    NONE = "none"


class TemaMode(str, Enum):
    SCRIPTED = "scripted"
    IMPROV = "improv"
    LISTENER_CONTENT = "listener_content"


class Emotion(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    EXCITED = "excited"
    SAD = "sad"
    SURPRISED = "surprised"
    THOUGHTFUL = "thoughtful"
    EMPATHETIC = "empathetic"


class DriftType(str, Enum):
    FABRICATED_DETAIL = "fabricated_detail"
    STYLE_SHIFT = "style_shift"
    TOPIC_VIOLATION = "topic_violation"
    CONTRADICTION = "contradiction"
    ROLE_CONFUSION = "role_confusion"


class SupervisorAction(str, Enum):
    FORWARD = "forward"
    REGENERATE = "regenerate"


class ExperimentCondition(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


# ── Clock & Tema ─────────────────────────────────────────────────────────────

class Tema(BaseModel):
    """A single show topic attached to a Talk slot."""
    title: str
    mode: TemaMode
    content: Optional[str] = None
    guidance: Optional[str] = None


class Slot(BaseModel):
    """One slot in the rundown clock."""
    id: str
    order: int
    type: SlotType
    duration_sec: int = 0
    nominal_sec: Optional[int] = None
    label: Optional[str] = None
    category: Optional[str] = None
    source: Optional[SlotSource] = None
    asset: Optional[str] = None
    tts_text: Optional[str] = None
    tema: Optional[Tema] = None
    optional: Optional[bool] = False
    note: Optional[str] = None
    target_min: Optional[int] = None
    hour_param: Optional[str] = None
    adapted: Optional[bool] = False

    @model_validator(mode="before")
    @classmethod
    def populate_duration(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "duration_sec" not in data or data["duration_sec"] is None:
                data["duration_sec"] = data.get("nominal_sec", 0)
        return data


class Clock(BaseModel):
    """Full rundown for a show."""
    show: str
    duration_min: int
    slots: list[Slot]


# ── Persona ──────────────────────────────────────────────────────────────────

class PersonaCard(BaseModel):
    """Identity card defining a single AI broadcaster persona."""
    id: str
    name: str
    gender: Literal["male", "female"]
    voice: str = ""
    speaking_style: str = ""
    catchphrases: list[str] = Field(default_factory=list)
    topic_limits: list[str] = Field(default_factory=list)
    background_facts: list[str] = Field(default_factory=list)
    do_not: list[str] = Field(default_factory=list)


# ── LLM Outputs ──────────────────────────────────────────────────────────────

class PersonaOutput(BaseModel):
    """Structured reply from a persona LLM call."""
    text: str
    emotion: Emotion


class CorrectionMemory(BaseModel):
    """Memory patch injected by the supervisor when drift is detected."""
    persona_reminder: str = ""
    conversation_summary: str = ""
    facts_to_enforce: list[str] = Field(default_factory=list)


class LedgerEntry(BaseModel):
    """A single factual claim recorded in the supervisor's ledger."""
    persona: str
    claim: str
    turn: int


class SupervisorVerdict(BaseModel):
    """Structured output of the supervisor's drift check."""
    drift_detected: bool = False
    drift_types: list[DriftType] = Field(default_factory=list)
    severity: int = 0
    evidence: str = ""
    action: SupervisorAction = SupervisorAction.FORWARD
    correction_memory: CorrectionMemory = Field(default_factory=CorrectionMemory)
    ledger_updates: list[LedgerEntry] = Field(default_factory=list)


# ── Logging ──────────────────────────────────────────────────────────────────

class LatencyMs(BaseModel):
    """Per-stage latency in milliseconds for a single turn."""
    persona: int = 0
    supervisor: int = 0
    tts: int = 0


class ModelsUsed(BaseModel):
    """Model identifiers used for a single turn."""
    persona: str = ""
    supervisor: str = ""


class TurnLog(BaseModel):
    """One line in the JSONL session log."""
    session_id: str
    condition: ExperimentCondition
    slot_id: str
    turn: int
    persona: str
    raw_reply: str
    verdict: Optional[SupervisorVerdict] = None
    regenerations: int = 0
    final_text: str
    emotion: Emotion
    latency_ms: LatencyMs = Field(default_factory=LatencyMs)
    models: ModelsUsed = Field(default_factory=ModelsUsed)


# ── WebSocket Events ─────────────────────────────────────────────────────────

class SessionStatus(BaseModel):
    """Real-time status pushed to the frontend via WebSocket."""
    state: SessionState
    current_slot_id: Optional[str] = None
    current_slot_type: Optional[SlotType] = None
    current_turn: int = 0
    elapsed_sec: float = 0.0
    api_status: str = "ok"  # ok | rate_limited | error


class TurnEvent(BaseModel):
    """A completed turn pushed to the frontend via WebSocket."""
    slot_id: str
    turn: int
    persona: str
    persona_name: str
    text: str
    emotion: Emotion
    verdict: Optional[SupervisorVerdict] = None
    latency_ms: LatencyMs = Field(default_factory=LatencyMs)
    audio_url: Optional[str] = None


class StartSessionRequest(BaseModel):
    """Request body for POST /api/session/start."""
    condition: ExperimentCondition = ExperimentCondition.A
    max_turns: int = 10
    custom_tema_title: Optional[str] = None
    custom_tema_mode: TemaMode = TemaMode.IMPROV
    custom_persona_a: Optional[PersonaCard] = None
    custom_persona_b: Optional[PersonaCard] = None
