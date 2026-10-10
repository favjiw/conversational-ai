"""Clock Runner for 1-hour Pagi Bener Live Rundown (FR-1, FR-2, FR-7).

Executes all 39 slots of clock-pagi-bener-live-1jam.json:
- Song slots: Deezer MP3 preview and music event
- Talk slots: ConversationEngine + TTS
- Spot/Adlibs slots: radio commercial adlib via TTS
- Jingle/Smash/Time-signal slots: sounder/jingle cues
- Time markers: quarter checkpoints (07.15, 07.30, 07.45, 08.00)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

from app.conversation.engine import ConversationEngine
from app.llm.client import LLMClient
from app.music.models import MusicTrack
from app.music.provider import MusicProvider
from app.schemas import (
    Clock,
    Emotion,
    PersonaCard,
    SessionState,
    Slot,
    SlotType,
    Tema,
    TemaMode,
    TurnEvent,
)
from app.tts.provider import TTSProvider

logger = logging.getLogger(__name__)


def clean_text_for_tts(text: str) -> str:
    """Strip bracketed tags, emojis, and symbols so TTS reads only spoken radio words."""
    # 1. Remove bracketed or parenthesized cues like [ADLIBS / SPONSOR], [Smash], (tertawa)
    cleaned = re.sub(r"\[.*?\]", "", text)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    # 2. Remove emojis and uncommon unicode symbol ranges
    cleaned = re.sub(
        r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\u2300-\u23ff\u2b50\u200d\ufe0f]",
        "",
        cleaned,
    )
    # 3. Remove markdown symbols and quotes
    cleaned = re.sub(r"[*#~`\"']+", "", cleaned)
    # 4. Collapse spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


SAMPLE_ADLIBS = [
    "Dengerin terus 103.9 HITS Unikom Radio! Pagi ceria bareng kopi hangat dan musik terbaik Bandung.",
    "Mau tugas kampus lancar tanpa ngantuk? Kopi Hits siap nemenin deadline kamu sampai tuntas!",
    "HITS Radio Streaming, dengerin di mana aja lewat website dan live TikTok kita tiap jam 7 pagi!",
    "Pagi Bener bareng HITS Radio! Kirim salam dan request lagu favorit kamu lewat kolom komentar live ya!",
    "Disponsori oleh merchandise resmi HITS Media Kreasi. Tampil keren gaya anak muda masa kini!",
    "Tetap aman berkendara di jalan raya Bandung, patuhi rambu lalu lintas dan nyalakan lampu utama!",
]

CUE_VOICE_SCRIPTS = {
    "s01": "103.9 HITS Unikom Radio! Musik terbaik anak muda Bandung.",
    "s02": "Tepat pukul 07.00 Waktu Indonesia Barat. Selamat pagi Bandung, dengerin terus Pagi Bener!",
    "s03": "HITS Unikom Radio, Jalan Dipatiukur Nomor 112 Bandung. Streaming live tiap pagi!",
    "s04": "Layanan masyarakat HITS FM: Selalu tertib berlalu lintas di jalan raya Bandung dan utamakan keselamatan bersama.",
    "s05": "Halo sobat HITS, saya Afgan! Terus dengerin lagu-lagu hits favorit kamu cuma di 103.9 FM Bandung!",
    "s06": "HITS Mashup! Musik tanpa henti hanya di Pagi Bener!",
    "s11": "103.9 HITS FM Bandung, The Real Youth Radio!",
    "s13": "HITS Station ID, energi kreatif anak muda Bandung!",
    "s20": "Pagi Bener! Masalah, Musik, dan Motivasi!",
    "s29": "103.9 HITS Unikom Radio, suara generasi muda!",
    "s37": "HITS Radio Bandung, sahabat setia pagi ceriamu!",
}


TALK_DEFAULT_TOPICS = {
    "s08": ("HITS News", "Berita terkini seputar tren gaya hidup, musik baru, dan agenda kampus Bandung pagi ini."),
    "s10": ("Traffic Info", "Update arus lalu lintas seputar jalan Dipatiukur, Dago, Pasteur, dan Surapati Bandung."),
    "s19": ("Teaser 3M", "Teaser segmen Masalah, Musik, dan Motivasi. Siap-siap dengerin curhat pendengar seru."),
    "s28": ("Segmen 3M Curhat", "Membahas curhat pendengar tentang tantangan bangun pagi, skripsi, dan kerjaan kantor."),
    "s36": ("Segmen 3M Solusi", "Lanjutan solusi santai dan motivasi semangat menjalani hari dari Raka dan Salsa."),
    "s38": ("Closing & Next Live", "Pamitan siaran Pagi Bener hari ini, terima kasih pendengar dan nantikan siaran besok jam 7 pagi!"),
}


class ClockRunner:
    """Orchestrates the 39-slot live radio clock."""

    def __init__(
        self,
        clock: Clock,
        persona_a: PersonaCard,
        persona_b: PersonaCard,
        llm_client: LLMClient,
        tts_provider: TTSProvider,
        music_provider: MusicProvider,
        supervisor_client: Optional[LLMClient] = None,
        broadcast_fn: Optional[Callable[[dict], Coroutine]] = None,
        demo_music_sec: int = 30,
        talk_turns_per_slot: int = 2,
    ):
        self.clock = clock
        self.persona_a = persona_a
        self.persona_b = persona_b
        self.llm = llm_client
        self.tts = tts_provider
        self.music = music_provider
        self.supervisor_llm = supervisor_client
        self.broadcast = broadcast_fn

        self.demo_music_sec = demo_music_sec
        self.talk_turns_per_slot = talk_turns_per_slot

        self._state = SessionState.IDLE
        self._session_id = ""
        self._current_slot_idx = 0
        self._start_time = 0.0
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stop_requested = False
        self._total_turns = 0
        self._slot_task = None
        self._run_task = None
        self._skip_requested = False
        self._generation = 0
        self._playback_id = None
        self._playback_done = asyncio.Event()
        self._playback_sequence = 0
        self._playback_error = None

        self._control_lock = asyncio.Lock()

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def current_slot_idx(self) -> int:
        return self._current_slot_idx

    async def emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self.broadcast:
            await self.broadcast({"type": event_type, "data": {
                **data, "session_id": self._session_id,
                "generation": self._generation,
            }})

    def playback_feedback(self, data: dict[str, Any]) -> None:
        """Accept only feedback for the current audio and slot revision."""
        if (data.get("session_id") != self._session_id
                or data.get("generation") != self._generation
                or data.get("playback_id") != self._playback_id):
            return
        if data.get("state") == "ended":
            self._playback_done.set()
        elif data.get("state") == "error":
            self._playback_error = data.get("message") or "Audio playback failed"
            self._playback_done.set()

    async def _play_audio(self, event_type: str, data: dict[str, Any]) -> None:
        self._playback_sequence += 1
        self._playback_id = f"{self._generation}:{self._playback_sequence}"
        self._playback_error = None
        self._playback_done.clear()
        await self.emit_event(event_type, {**data, "playback_id": self._playback_id})
        # Actual browser completion, not an estimate of MP3 duration, advances the runner.
        await self._playback_done.wait()
        if self._playback_error:
            raise RuntimeError(self._playback_error)
        self._playback_id = None

    async def start(self, session_id: str) -> None:
        async with self._control_lock:
            if self._state != SessionState.IDLE:
                raise RuntimeError(f"Runner already in state {self._state.value}")

            self._session_id = session_id
            self._state = SessionState.RUNNING
            self._start_time = time.time()
            self._stop_requested = False
            self._skip_requested = False
            self._current_slot_idx = 0
            self._total_turns = 0
            self._generation += 1

            await self.emit_event("status", {
                "state": "running",
                "session_id": self._session_id,
                "mode": "clock_live",
            })

            self._run_task = asyncio.create_task(self._run_loop())

    async def pause(self) -> None:
        async with self._control_lock:
            if self._state == SessionState.RUNNING:
                self._state = SessionState.PAUSED
                self._pause_event.clear()
                await self.emit_event("status", {"state": "paused", "session_id": self._session_id})

    async def resume(self) -> None:
        async with self._control_lock:
            if self._state == SessionState.PAUSED:
                self._state = SessionState.RUNNING
                self._pause_event.set()
                await self.emit_event("status", {"state": "running", "session_id": self._session_id})

    async def skip_to_next(self) -> None:
        """Skip current slot and move to the next one."""
        async with self._control_lock:
            if self._state == SessionState.RUNNING:
                self._skip_requested = True
                self._generation += 1
                self._pause_event.set()  # Unblock if sleeping
                
                # Interrupt the current slot task if any
                if self._slot_task and not self._slot_task.done():
                    self._slot_task.cancel()
                
                # Unblock any pending playback wait
                self._playback_done.set()

                logger.info("Skip requested for slot %d", self._current_slot_idx)
                await self.emit_event("clock_slot_skipped", {
                    "slot_index": self._current_slot_idx,
                    "session_id": self._session_id,
                    "generation": self._generation
                })

    async def stop(self) -> None:
        async with self._control_lock:
            self._stop_requested = True
            self._pause_event.set()
            
            if self._slot_task and not self._slot_task.done():
                self._slot_task.cancel()
                
            self._playback_done.set()
            self._state = SessionState.FINISHED
            await self.emit_event("status", {"state": "idle", "session_id": self._session_id})

    async def _run_loop(self) -> None:
        total_slots = len(self.clock.slots)
        logger.info("ClockRunner starting execution of %d slots", total_slots)

        try:
            for idx, slot in enumerate(self.clock.slots):
                if self._stop_requested:
                    break

                await self._pause_event.wait()
                if self._stop_requested:
                    break

                self._current_slot_idx = idx
                self._skip_requested = False

                await self.emit_event("clock_slot_started", {
                    "slot_index": idx,
                    "total_slots": total_slots,
                    "slot_id": slot.id,
                    "slot_type": slot.type.value,
                    "label": slot.label or slot.id,
                    "category": slot.category or "",
                    "nominal_sec": slot.nominal_sec or slot.duration_sec,
                    "generation": self._generation,
                })

                # Wrap slot handler in a cancellable task so skip() can interrupt it
                self._slot_task = asyncio.create_task(
                    self._dispatch_slot(slot, idx)
                )
                try:
                    await self._slot_task
                except asyncio.CancelledError:
                    logger.info("Slot %d interrupted by skip", idx)
                finally:
                    self._slot_task = None

                if self._stop_requested:
                    break

                # If skipped, do not emit "completed" for this slot
                if self._skip_requested:
                    logger.info("Slot %d skipped", idx)
                    continue

                await self.emit_event("clock_slot_completed", {
                    "slot_index": idx,
                    "slot_id": slot.id,
                })

            if not self._stop_requested:
                self._state = SessionState.FINISHED
                await self.emit_event("status", {"state": "finished", "session_id": self._session_id})

        except Exception as e:
            logger.error("ClockRunner error at slot %d: %s", self._current_slot_idx, e, exc_info=True)
            self._state = SessionState.IDLE
            await self.emit_event("status", {"state": "idle", "error": str(e), "session_id": self._session_id})

    async def _dispatch_slot(self, slot: Slot, idx: int) -> None:
        if slot.type == SlotType.SONG:
            await self._handle_song_slot(slot)
        elif slot.type == SlotType.TALK:
            await self._handle_talk_slot(slot)
        elif slot.type == SlotType.SPOT_ADLIBS:
            await self._handle_adlibs_slot(slot, idx)
        elif slot.type == SlotType.TIME_MARKER:
            await self._handle_time_marker_slot(slot)
        else:
            await self._handle_cue_slot(slot)

    async def _handle_song_slot(self, slot: Slot) -> None:
        category = slot.category or "indo_hits"
        logger.info("Song slot %s category=%s", slot.id, category)
        tracks = await self.music.search(category=category, limit=3)
        track = tracks[0] if tracks else MusicTrack(
            id=f"track_{slot.id}",
            title=f"Lagu Hits ({category})",
            artist="HITS Radio",
            category=category,
            source="fallback",
        )

        cat_clean = category.replace("_", " ").title()
        intro_speaker = self.persona_a if (self._total_turns % 2 == 0) else self.persona_b

        # 1. LLM Host Announcer Bicara Intro Lagu
        intro_text = (
            f"Nah sekarang giliran lagu hits {cat_clean}! Kita puterin buat kamu {track.artist} "
            f"dengan lagu {track.title}. Selamat dengerin sobat HITS!"
        )
        if self.llm:
            try:
                llm_res = await self.llm.generate(
                    prompt=(
                        f"Kamu {intro_speaker.name}, penyiar 103.9 HITS Radio Bandung. "
                        f"Kenalkan lagu hits berikutnya yang akan diputar: '{track.title}' oleh {track.artist} (kategori: {cat_clean}). "
                        f"Bicara 1-2 kalimat gaya santai gaul ceria anak muda Bandung.\n"
                        f"ATURAN KETAT: DILARANG menyertakan emoji atau simbol apapun (seperti petir, musik, api). "
                        f"DILARANG menyertakan tanda kurung atau petik. HANYA kata-kata lisan siaran murni."
                    ),
                    system_instruction="Kamu adalah penyiar radio Bandung yang gaul dan ceria. Jangan pernah gunakan emoji.",
                )
                if llm_res.raw and len(llm_res.raw.strip()) > 5:
                    intro_text = llm_res.raw.strip()
            except Exception as e:
                logger.warning("LLM intro generation fallback: %s", e)

        # Tunggu sampai penyiar selesai bicara intro
        await self._speak_turn(slot.id, intro_speaker, intro_text, emotion="happy", wait_spoken=True)

        # 2. Putar Preview Deezer MP3
        wait_sec = min(self.demo_music_sec, slot.nominal_sec or 30)
        await self._play_audio("clock_music", {
            "slot_id": slot.id,
            "category": category,
            "track": track.model_dump(),
            "preview_sec": wait_sec,
        })

        # 3. LLM Host Announcer Bicara Outro / Backsell Lagu
        outro_speaker = self.persona_b if intro_speaker == self.persona_a else self.persona_a
        outro_text = (
            f"Keren banget lagu dari {track.artist} barusan! Masih di 103.9 HITS FM Pagi Bener, "
            f"stay tuned terus bareng {self.persona_a.name} dan {self.persona_b.name}!"
        )
        if self.llm:
            try:
                llm_res = await self.llm.generate(
                    prompt=(
                        f"Kamu {outro_speaker.name}, penyiar 103.9 HITS Radio Bandung. "
                        f"Beri komentar 1 kalimat menikmati lagu '{track.title}' dari {track.artist} yang baru saja selesai diputar. "
                        f"Lalu ajak pendengar tetap stay tuned di 103.9 HITS Radio.\n"
                        f"ATURAN KETAT: DILARANG menyertakan emoji atau simbol apapun. "
                        f"DILARANG menyertakan tanda kurung atau petik. HANYA kata-kata lisan siaran murni."
                    ),
                    system_instruction="Kamu adalah penyiar radio Bandung yang gaul dan ceria. Jangan pernah gunakan emoji.",
                )
                if llm_res.raw and len(llm_res.raw.strip()) > 5:
                    outro_text = llm_res.raw.strip()
            except Exception as e:
                logger.warning("LLM outro generation fallback: %s", e)

        # Tunggu sampai penyiar selesai bicara outro
        await self._speak_turn(slot.id, outro_speaker, outro_text, emotion="happy", wait_spoken=True)

    async def _handle_talk_slot(self, slot: Slot) -> None:
        title, guidance = TALK_DEFAULT_TOPICS.get(
            slot.id, (slot.label or "Obrolan Pagi Bener", "Obrolan santai penyiar")
        )
        tema = Tema(title=title, mode=TemaMode.IMPROV, content=guidance, guidance=guidance)
        async def on_turn(turn_log) -> None:
            speaker = self.persona_a if turn_log.persona == self.persona_a.id else self.persona_b
            emotion_str = turn_log.emotion.value if hasattr(turn_log.emotion, "value") else str(turn_log.emotion)
            # wait_spoken=True ensures Turn 1 finishes speaking before Turn 2 is generated
            await self._speak_turn(slot.id, speaker, turn_log.final_text, emotion=emotion_str, wait_spoken=True)

        engine = ConversationEngine(
            persona_a=self.persona_a,
            persona_b=self.persona_b,
            llm_client=self.llm,
            supervisor_client=self.supervisor_llm,
            on_turn=on_turn,
        )

        await engine.run_slot(
            tema=tema,
            max_turns=self.talk_turns_per_slot,
            slot_id=slot.id,
            on_turn=on_turn,
        )

    async def _handle_adlibs_slot(self, slot: Slot, idx: int) -> None:
        adlib_text = SAMPLE_ADLIBS[idx % len(SAMPLE_ADLIBS)]
        speaker = self.persona_a if (idx % 2 == 0) else self.persona_b
        formatted_text = f"📢 [ADLIBS / SPONSOR] {adlib_text}"
        await self._speak_turn(slot.id, speaker, formatted_text, emotion="excited", wait_spoken=True)

    async def _handle_cue_slot(self, slot: Slot) -> None:
        cue_text = CUE_VOICE_SCRIPTS.get(
            slot.id,
            f"103.9 HITS Radio Bandung! {slot.label or slot.type.value}"
        )
        speaker = self.persona_b
        label_clean = slot.label or slot.type.value
        dur = await self._speak_turn(slot.id, speaker, f"⚡ [{label_clean}] {cue_text}", emotion="excited", wait_spoken=True)

        await self.emit_event("clock_cue", {
            "slot_id": slot.id,
            "type": slot.type.value,
            "label": label_clean,
            "nominal_sec": slot.nominal_sec or round(dur),
        })
        # If nominal stager has slight trailing music padding (capped at 3s)
        rem_sec = max(0.0, min(3.0, (slot.nominal_sec or 0) - dur))
        if rem_sec > 0:
            await self._sleep_cancellable(rem_sec)

    async def _handle_time_marker_slot(self, slot: Slot) -> None:
        target = slot.target_min or 0
        marker_text = f"⏰ Checkpoint Siaran: Tepat pukul 07.{target:02d} WIB di 103.9 HITS Unikom Radio!"
        await self._speak_turn(slot.id, self.persona_a, marker_text, emotion="happy", wait_spoken=True)
        await self.emit_event("clock_time_marker", {
            "slot_id": slot.id,
            "label": slot.label or "Checkpoint",
            "target_min": slot.target_min,
        })

    async def _speak_turn(
        self,
        slot_id: str,
        speaker: PersonaCard,
        text: str,
        emotion: str = "neutral",
        wait_spoken: bool = True,
    ) -> float:
        self._total_turns += 1
        audio_url = None
        duration_sec = max(2.5, len(text) / 14.0)
        spoken_text = clean_text_for_tts(text)
        try:
            if spoken_text:
                audio_bytes = await self.tts.synthesize(spoken_text, speaker.voice or "male_voice")
                audio_dir = Path("cache/tts")
                audio_dir.mkdir(parents=True, exist_ok=True)
                ext = "mp3" if self.tts.provider_name in ("elevenlabs", "edge") else "wav"
                filename = f"clock_{self._session_id}_t{self._total_turns}.{ext}"
                (audio_dir / filename).write_bytes(audio_bytes)
                audio_url = f"/audio/{filename}"

                # Calculate duration from audio bytes
                if ext == "mp3":
                    # 48kbps mono CBR MP3 is ~6000 bytes/sec
                    duration_sec = max(2.0, len(audio_bytes) / 6000.0)
                else:
                    # 16-bit 16kHz mono WAV is 32000 bytes/sec
                    duration_sec = max(2.0, len(audio_bytes) / 32000.0)
        except Exception as e:
            logger.warning("TTS error in _speak_turn: %s", e)

        duration_sec = round(duration_sec, 2)
        if audio_url:
            await self._play_audio("turn", {
                "slot_id": slot_id,
                "slot_index": self._current_slot_idx,
                "turn": self._total_turns,
                "persona": speaker.id,
                "persona_name": speaker.name,
                "text": text,
                "emotion": emotion,
                "audio_url": audio_url,
                "duration_sec": duration_sec,
            })
        else:
            await self.emit_event("turn", {
                "slot_id": slot_id,
                "slot_index": self._current_slot_idx,
                "turn": self._total_turns,
                "persona": speaker.id,
                "persona_name": speaker.name,
                "text": text,
                "emotion": emotion,
                "audio_url": None,
                "duration_sec": duration_sec,
            })
            if wait_spoken:
                await self._sleep_cancellable(duration_sec + 0.6)

        return duration_sec

    async def _sleep_cancellable(self, seconds: float) -> None:
        step = 0.5
        elapsed = 0.0
        while elapsed < seconds and not self._stop_requested and not self._skip_requested:
            await self._pause_event.wait()
            if self._stop_requested or self._skip_requested:
                break
            await asyncio.sleep(step)
            elapsed += step

