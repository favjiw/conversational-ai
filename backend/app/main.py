"""FastAPI server for HITS AI Live (Condition A).

Exposes REST APIs and WebSocket for:
- Direct ConversationEngine session control (start, stop)
- Real-time turn events + audio generation via TTS
- Condition A (two agents, no supervisor)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import get_settings
from app.conversation.engine import ConversationEngine
from app.llm.client import create_llm_client
from app.llm.rate_limiter import RateLimiterRegistry
from app.schemas import (
    Emotion,
    ExperimentCondition,
    PersonaCard,
    SessionState,
    SessionStatus,
    Tema,
    TemaMode,
    TurnEvent,
    TurnLog,
)
from app.session_logging.logger import SessionLogger
from app.tts.provider import create_tts_provider
from app.music.provider import create_music_provider
from app.music.models import MusicTrack
from app.clock.validator import validate_clock_semantics
from app.orchestrator.clock_runner import clean_text_for_tts

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hits.server")

settings = get_settings()

app = FastAPI(
    title="HITS AI Live API (Condition A)",
    description="Two-agent LLM conversation with TTS audio streaming",
    version="1.0.0",
)

# CORS middleware for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for live session streaming."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected. Total: %d", len(self.active_connections))

    async def broadcast_json(self, data: dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning("Error sending WS message: %s", e)
                self.disconnect(connection)

ws_manager = ConnectionManager()

# ── App State & Engine Singletons ───────────────────────────────────────────

rate_limiter_registry = RateLimiterRegistry(default_rpm=5)

llm_client = create_llm_client(
    mode=settings.LLM_MODE,
    api_key=settings.GEMINI_API_KEY,
    default_model=settings.GEMINI_MODEL_PERSONA,
    rate_limiter_registry=rate_limiter_registry,
    fail_inject=settings.FAIL_INJECT,
)

tts_provider = create_tts_provider(
    mode=settings.TTS_MODE,
    provider=settings.TTS_PROVIDER,
    api_key=settings.ELEVENLABS_API_KEY if settings.TTS_PROVIDER == "elevenlabs" else settings.GEMINI_API_KEY,
    model=settings.GEMINI_MODEL_TTS,
    elevenlabs_model=settings.ELEVENLABS_MODEL_ID,
    voicestudio_url=settings.VOICESTUDIO_URL,
    voicestudio_api_key=settings.VOICESTUDIO_API_KEY,
    voicestudio_model=settings.VOICESTUDIO_MODEL,
    edge_voice_male=settings.EDGE_VOICE_MALE,
    edge_voice_female=settings.EDGE_VOICE_FEMALE,
    edge_rate_female=settings.EDGE_RATE_FEMALE,
    edge_pitch_female=settings.EDGE_PITCH_FEMALE,
    edge_rate_male=settings.EDGE_RATE_MALE,
    edge_pitch_male=settings.EDGE_PITCH_MALE,
)

music_provider = create_music_provider(
    provider=settings.MUSIC_PROVIDER,
    fail_inject=settings.FAIL_INJECT,
)

current_engine: Optional[ConversationEngine] = None
background_task: Optional[asyncio.Task] = None
current_session_id: Optional[str] = None
current_state: SessionState = SessionState.IDLE

# ── Broadcast Helpers ───────────────────────────────────────────────────────

async def on_session_status(state: SessionState, session_id: Optional[str] = None):
    """Broadcast status change to all WebSocket clients."""
    global current_state
    current_state = state
    await ws_manager.broadcast_json({
        "type": "status",
        "data": {
            "state": state.value,
            "session_id": session_id or current_session_id,
        },
    })

# ── REST Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "llm_mode": settings.LLM_MODE,
        "tts_mode": settings.TTS_MODE,
        "active_session": current_session_id,
        "session_state": current_state.value,
    }

@app.get("/audio/{filename}")
def serve_audio(filename: str):
    audio_dir = Path("cache/tts")
    file_path = audio_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
    return FileResponse(path=str(file_path), media_type=media_type)


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "male_voice"


@app.post("/api/tts")
async def synthesize_tts(req: TTSRequest):
    """Direct TTS endpoint for TTSLab and real-time audio testing."""
    try:
        audio_bytes = await tts_provider.synthesize(req.text, req.voice or "male_voice")
        media_type = "audio/wav" if audio_bytes.startswith(b"RIFF") else ("audio/mpeg" if settings.TTS_PROVIDER in ("elevenlabs", "edge") else "audio/wav")
        return Response(content=audio_bytes, media_type=media_type)
    except Exception as e:
        logger.error("TTS synthesize failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/music/search")
async def search_music(category: str = "", query: str = "", limit: int = 5):
    """Search music tracks via the configured MusicProvider.
    
    Args:
        category: Clock slot category (indo_hits, indo, barat, korea).
        query: Free-text search query (overrides category).
        limit: Max results (default 5).
    
    Returns:
        List of MusicTrack with preview_url populated.
    """
    try:
        tracks = await music_provider.search(
            category=category, query=query, limit=limit
        )
        return {"tracks": [t.model_dump() for t in tracks]}
    except Exception as e:
        logger.error("Music search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



def load_aron_themes() -> list[Tema]:
    themes_path = Path(__file__).parent / "data" / "aron_themes_id.json"
    if not themes_path.exists():
        return []
    try:
        data = json.loads(themes_path.read_text(encoding="utf-8"))
        themes = []
        for item in data:
            themes.append(
                Tema(
                    title=item["title"],
                    mode=TemaMode.IMPROV,
                    content=f"Set: {item['set_label']}. Pertanyaan: {item['question_id']}",
                    guidance=item["guidance"],
                )
            )
        return themes
    except Exception as e:
        logger.error("Failed loading aron themes: %s", e)
        return []


class StartSessionRequest(BaseModel):
    condition: ExperimentCondition = ExperimentCondition.A
    max_turns: int = 10
    topic: Optional[str] = None
    custom_tema_title: Optional[str] = None
    custom_tema_guidance: Optional[str] = None
    custom_tema_content: Optional[str] = None
    custom_tema_mode: Optional[TemaMode] = None
    persona_a: Optional[Any] = None
    persona_b: Optional[Any] = None
    custom_persona_a: Optional[PersonaCard] = None
    custom_persona_b: Optional[PersonaCard] = None
    preset: Optional[str] = "custom"  # "quick", "15min", "1hour_aron", "custom"
    theme_mode: Optional[str] = "single"  # "single" | "aron_closeness"
    turns_per_theme: Optional[int] = 6


@app.get("/api/themes/aron")
async def get_aron_themes():
    themes_path = Path(__file__).parent / "data" / "aron_themes_id.json"
    if not themes_path.exists():
        return []
    return json.loads(themes_path.read_text(encoding="utf-8"))


async def run_session_background(
    engine: ConversationEngine,
    tema: Tema,
    max_turns: int,
    session_id: str,
    theme_playlist: Optional[list[Tema]] = None,
    turns_per_theme: int = 6,
    on_theme_change=None,
):
    try:
        await on_session_status(SessionState.RUNNING, session_id)
        await engine.run_slot(
            tema=tema,
            max_turns=max_turns,
            slot_id="live",
            theme_playlist=theme_playlist,
            turns_per_theme=turns_per_theme,
            on_theme_change=on_theme_change,
        )
        await on_session_status(SessionState.FINISHED, session_id)
    except asyncio.CancelledError:
        logger.info("Session %s cancelled", session_id)
        await on_session_status(SessionState.IDLE, session_id)
    except Exception as e:
        logger.error("Session error: %s", e, exc_info=True)
        await on_session_status(SessionState.IDLE, session_id)

@app.post("/api/session/start")
async def start_session(req: StartSessionRequest):
    global current_engine, background_task, current_session_id
    if background_task and not background_task.done():
        raise HTTPException(status_code=400, detail="A session is already running")

    session_id = f"session_{uuid.uuid4().hex[:8]}"
    current_session_id = session_id

    # Resolve Persona A
    name_a = "Raka"
    style_a = "Pria ceria, lugas, santai, energi tinggi"
    if isinstance(req.persona_a, dict):
        name_a = req.persona_a.get("name") or name_a
        style_a = req.persona_a.get("style") or style_a

    persona_a = req.custom_persona_a or PersonaCard(
        id="persona_a",
        name=name_a,
        gender="male",
        voice=settings.ELEVENLABS_VOICE_A or "JBFqnCBsd6RMkjVDRZzb",
        speaking_style=style_a,
        catchphrases=["Stay tuned bareng kita!", "Gimana nih menurut lo?"],
        topic_limits=["Kultur pop", "Gaya hidup", "Musik", "Kota"],
        background_facts=["Penyiar radio muda Bandung", "Suka kopi dan kuliner"],
        do_not=["Jangan gunakan bahasa kaku", "Jangan mengulang kalimat persis"],
    )

    # Resolve Persona B
    name_b = "Salsa"
    style_b = "Wanita hangat, tanggap, ramah, humoris"
    if isinstance(req.persona_b, dict):
        name_b = req.persona_b.get("name") or name_b
        style_b = req.persona_b.get("style") or style_b

    persona_b = req.custom_persona_b or PersonaCard(
        id="persona_b",
        name=name_b,
        gender="female",
        voice=settings.ELEVENLABS_VOICE_B or "EXAVITQu4vr4xnSDxMaL",
        speaking_style=style_b,
        catchphrases=["Bener banget!", "Wah seru tuh!"],
        topic_limits=["Kultur pop", "Gaya hidup", "Musik", "Kota"],
        background_facts=["Penyiar radio hits Bandung", "Suka nonton konser dan tren sosial"],
        do_not=["Jangan gunakan bahasa kaku", "Jangan memotong kasar"],
    )

    topic_title = req.topic or req.custom_tema_title or "Kemacetan pagi di Bandung"
    tema = Tema(
        title=topic_title,
        mode=req.custom_tema_mode or TemaMode.IMPROV,
        content=req.custom_tema_content or None,
        guidance=req.custom_tema_guidance or "Bahas situasi lalu lintas santai dan tips buat pendengar.",
    )

    session_logger = SessionLogger(
        session_id=session_id,
        log_dir=settings.LOG_DIR,
    )

    async def on_turn_callback(turn_log: TurnLog):
        active_persona = persona_a if turn_log.persona == persona_a.id else persona_b
        audio_url = None
        try:
            if settings.TTS_PROVIDER == "edge":
                voice = settings.EDGE_VOICE_MALE if active_persona.gender == "male" else settings.EDGE_VOICE_FEMALE
            elif settings.TTS_PROVIDER == "elevenlabs":
                voice = active_persona.voice or (
                    settings.ELEVENLABS_VOICE_A if active_persona.gender == "male" else settings.ELEVENLABS_VOICE_B
                )
            else:
                voice = "Puck" if active_persona.gender == "male" else "Kore"

            logger.info("Synthesizing TTS (%s) for turn %d (%s, voice=%s)...", settings.TTS_PROVIDER, turn_log.turn, active_persona.name, voice)
            spoken_text = clean_text_for_tts(turn_log.final_text)
            if not spoken_text:
                spoken_text = turn_log.final_text
            audio_bytes = await tts_provider.synthesize(
                text=spoken_text,
                voice=voice,
            )
            cache_dir = Path("cache/tts")
            cache_dir.mkdir(parents=True, exist_ok=True)
            ext = "mp3" if settings.TTS_PROVIDER in ("elevenlabs", "edge") else "wav"
            filename = f"{session_id}_turn_{turn_log.turn:04d}.{ext}"
            file_path = cache_dir / filename
            file_path.write_bytes(audio_bytes)
            audio_url = f"/audio/{filename}"
            logger.info("TTS generated turn %d (%d bytes, url=%s)", turn_log.turn, len(audio_bytes), audio_url)
        except Exception as err:
            logger.warning("TTS error for turn %d: %s", turn_log.turn, err)

        event = TurnEvent(
            slot_id="live",
            turn=turn_log.turn,
            persona=turn_log.persona,
            persona_name=active_persona.name,
            text=turn_log.final_text,
            emotion=turn_log.emotion,
            audio_url=audio_url,
        )
        await ws_manager.broadcast_json({
            "type": "turn",
            "data": event.model_dump(),
        })

    current_engine = ConversationEngine(
        persona_a=persona_a,
        persona_b=persona_b,
        llm_client=llm_client,
        condition=req.condition,
        persona_model=settings.GEMINI_MODEL_PERSONA,
        session_id=session_id,
        session_logger=session_logger,
        on_turn=on_turn_callback,
    )

    theme_playlist = None
    max_turns = req.max_turns
    turns_per_theme = req.turns_per_theme or 6

    if req.preset in ("1hour_aron", "15min") or req.theme_mode == "aron_closeness":
        aron_list = load_aron_themes()
        if aron_list:
            if req.preset == "15min":
                theme_playlist = aron_list[:8]
            else:
                theme_playlist = aron_list

            if req.preset in ("1hour_aron", "15min"):
                max_turns = len(theme_playlist) * turns_per_theme

    async def on_theme_change_callback(new_tema: Tema, theme_idx: int):
        await ws_manager.broadcast_json({
            "type": "theme_change",
            "data": {
                "title": new_tema.title,
                "guidance": new_tema.guidance,
                "content": new_tema.content,
                "theme_index": theme_idx + 1,
                "total_themes": len(theme_playlist) if theme_playlist else 1,
            },
        })

    background_task = asyncio.create_task(
        run_session_background(
            engine=current_engine,
            tema=tema,
            max_turns=max_turns,
            session_id=session_id,
            theme_playlist=theme_playlist,
            turns_per_theme=turns_per_theme,
            on_theme_change=on_theme_change_callback,
        )
    )
    return {
        "status": "started",
        "session_id": session_id,
        "condition": req.condition.value,
        "max_turns": max_turns,
        "total_themes": len(theme_playlist) if theme_playlist else 1,
    }

@app.post("/api/session/stop")
async def stop_session():
    global background_task
    if background_task and not background_task.done():
        background_task.cancel()
    await on_session_status(SessionState.IDLE)
    return {"status": "stopped", "session_id": current_session_id}


# ── Clock Rundown (Pagi Bener 1-Jam) Endpoints ──────────────────────────────

from app.clock.parser import load_pagi_bener_clock
from app.orchestrator.clock_runner import ClockRunner

clock_runner_instance: Optional[ClockRunner] = None
clock_runner_task: Optional[asyncio.Task] = None

@app.get("/api/clock")
def get_default_clock():
    """Return default loaded clock template."""
    clock = load_pagi_bener_clock()
    data = clock.model_dump()
    data["show"] = "Pagi Bener"
    return data

@app.get("/api/personas")
def get_personas():
    """Return default personas."""
    return {
        "persona_a": {
            "id": "persona_a",
            "name": "Raka",
            "gender": "male",
            "voice": settings.EDGE_VOICE_MALE,
        },
        "persona_b": {
            "id": "persona_b",
            "name": "Salsa",
            "gender": "female",
            "voice": settings.EDGE_VOICE_FEMALE,
        },
    }

class ValidateClockRequest(BaseModel):
    clock: dict[str, Any]

@app.post("/api/clock/validate")
def validate_clock_endpoint(req: ValidateClockRequest):
    try:
        from app.schemas import Clock
        clock = Clock.model_validate(req.clock)
        issues = validate_clock_semantics(clock)
        return {"valid": len(issues) == 0, "issues": issues}
    except Exception as e:
        return {"valid": False, "issues": [str(e)]}

@app.get("/api/clock/pagi-bener")
def get_pagi_bener_clock():
    """Return the loaded 39-slot Pagi Bener clock template."""
    clock = load_pagi_bener_clock()
    return clock.model_dump()

class StartClockRequest(BaseModel):
    demo_music_sec: Optional[int] = 30
    talk_turns_per_slot: Optional[int] = 2

@app.post("/api/clock/start")
async def start_clock_session(req: StartClockRequest = StartClockRequest()):
    global clock_runner_instance, clock_runner_task, current_session_id
    if clock_runner_task and not clock_runner_task.done():
        raise HTTPException(status_code=400, detail="Clock session is already running")

    clock = load_pagi_bener_clock()
    session_id = f"clock_{uuid.uuid4().hex[:8]}"
    current_session_id = session_id

    voice_a = settings.EDGE_VOICE_MALE if settings.TTS_PROVIDER == "edge" else (settings.ELEVENLABS_VOICE_A or "JBFqnCBsd6RMkjVDRZzb")
    voice_b = settings.EDGE_VOICE_FEMALE if settings.TTS_PROVIDER == "edge" else (settings.ELEVENLABS_VOICE_B or "EXAVITQu4vr4xnSDxMaL")

    persona_a = PersonaCard(
        id="persona_a",
        name="Raka",
        gender="male",
        voice=voice_a,
        speaking_style="Pria ceria, lugas, santai, energi tinggi",
        catchphrases=["Stay tuned bareng kita!", "Gimana nih menurut lo?"],
        topic_limits=["Kultur pop", "Gaya hidup", "Musik", "Kota"],
        background_facts=["Penyiar radio muda Bandung", "Suka kopi dan kuliner"],
        do_not=["Jangan gunakan bahasa kaku"],
    )

    persona_b = PersonaCard(
        id="persona_b",
        name="Salsa",
        gender="female",
        voice=voice_b,
        speaking_style="Wanita hangat, tanggap, ramah, humoris",
        catchphrases=["Bener banget!", "Wah seru tuh!"],
        topic_limits=["Kultur pop", "Gaya hidup", "Musik", "Kota"],
        background_facts=["Penyiar radio hits Bandung", "Suka nonton konser"],
        do_not=["Jangan gunakan bahasa kaku"],
    )

    async def broadcast_clock_event(event: dict[str, Any]):
        await ws_manager.broadcast_json(event)

    clock_runner_instance = ClockRunner(
        clock=clock,
        persona_a=persona_a,
        persona_b=persona_b,
        llm_client=llm_client,
        tts_provider=tts_provider,
        music_provider=music_provider,
        broadcast_fn=broadcast_clock_event,
        demo_music_sec=req.demo_music_sec or 30,
        talk_turns_per_slot=req.talk_turns_per_slot or 2,
    )

    await clock_runner_instance.start(session_id)
    clock_runner_task = clock_runner_instance._run_task
    return {"status": "started", "session_id": session_id, "total_slots": len(clock.slots)}

@app.post("/api/clock/stop")
async def stop_clock_session():
    global clock_runner_instance
    if clock_runner_instance:
        await clock_runner_instance.stop()
    return {"status": "stopped"}

@app.post("/api/clock/next")
async def skip_clock_slot():
    global clock_runner_instance
    if not clock_runner_instance:
        raise HTTPException(status_code=404, detail="No active clock session")
    if clock_runner_instance.state != SessionState.RUNNING:
        raise HTTPException(status_code=400, detail="Clock not running")
    
    next_index = clock_runner_instance._current_slot_idx + 1
    await clock_runner_instance.skip_to_next()
    return {"status": "skipped", "next_slot_index": next_index}

@app.get("/api/session/status")
def get_session_status():
    return SessionStatus(
        state=current_state,
        current_slot_id="live" if current_state == SessionState.RUNNING else None,
        elapsed_sec=0.0,
    )

@app.get("/api/logs")
def list_logs():
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("*.jsonl"), reverse=True)
    return [{"session_id": f.stem, "filename": f.name, "size_bytes": f.stat().st_size} for f in files]

@app.get("/api/logs/{session_id}")
def get_log_content(session_id: str):
    log_file = Path(settings.LOG_DIR) / f"{session_id}.jsonl"
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    lines = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lines.append(json.loads(line))
    return lines

@app.websocket("/ws/session")
async def websocket_session_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "status",
            "data": {"state": current_state.value, "session_id": current_session_id},
        })
        while True:
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif cmd.get("action") == "playback_feedback":
                    # Forward playback feedback to ClockRunner
                    global clock_runner_instance
                    if clock_runner_instance:
                        clock_runner_instance.playback_feedback(cmd.get("data", {}))
            except Exception as e:
                logger.warning("WS command error: %s", e)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)