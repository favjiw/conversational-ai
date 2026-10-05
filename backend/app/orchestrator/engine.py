"""Orchestrator state machine (FR-2).

Phase 1 scope: runs Talk slots sequentially, calls ConversationEngine,
then sends TTS audio. Non-Talk slots are skipped or play placeholder audio.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Optional

from app.schemas import (
    Clock,
    ExperimentCondition,
    PersonaCard,
    SessionState,
    SessionStatus,
    SlotType,
    TurnEvent,
    TurnLog,
)
from app.conversation.engine import ConversationEngine
from app.llm.client import LLMClient
from app.session_logging.logger import SessionLogger, generate_session_id
from app.tts.provider import TTSProvider

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs a full show session by executing slots in order.

    State machine: IDLE → RUNNING → (PAUSED) → FINISHED

    Args:
        clock: The show's clock/rundown.
        persona_a: Male persona card.
        persona_b: Female persona card.
        llm_client: LLM client for persona calls.
        supervisor_client: LLM client for supervisor calls.
        tts_provider: TTS provider for audio synthesis.
        condition: Experiment condition (A/B/C).
        persona_model: Model ID for persona LLM.
        supervisor_model: Model ID for supervisor LLM.
        log_dir: Directory for session logs.
        on_status: Async callback for status updates.
        on_turn: Async callback for completed turns.
    """

    def __init__(
        self,
        clock: Clock,
        persona_a: PersonaCard,
        persona_b: PersonaCard,
        llm_client: LLMClient,
        supervisor_client: LLMClient,
        tts_provider: TTSProvider,
        condition: ExperimentCondition = ExperimentCondition.C,
        persona_model: str = "",
        supervisor_model: str = "",
        log_dir: str = "logs",
        on_status: Optional[Callable[..., Coroutine]] = None,
        on_turn: Optional[Callable[..., Coroutine]] = None,
    ):
        self.clock = clock
        self.persona_a = persona_a
        self.persona_b = persona_b
        self.llm = llm_client
        self.supervisor_llm = supervisor_client
        self.tts = tts_provider
        self.condition = condition
        self.persona_model = persona_model
        self.supervisor_model = supervisor_model
        self.log_dir = log_dir
        self._on_status = on_status
        self._on_turn = on_turn

        self._state = SessionState.IDLE
        self._session_id = ""
        self._session_logger: Optional[SessionLogger] = None
        self._current_slot_idx = 0
        self._start_time = 0.0
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
        self._stop_requested = False

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def session_id(self) -> str:
        return self._session_id

    async def start(self) -> str:
        """Start a new session. Returns the session ID."""
        if self._state != SessionState.IDLE:
            raise RuntimeError(f"Cannot start: state is {self._state.value}")

        self._session_id = generate_session_id(self.condition.value)
        self._session_logger = SessionLogger(
            self._session_id, self.log_dir
        )
        self._state = SessionState.RUNNING
        self._start_time = time.time()
        self._stop_requested = False
        self._current_slot_idx = 0

        logger.info(
            "Session started: %s (condition=%s)",
            self._session_id,
            self.condition.value,
        )

        await self._emit_status()

        # Run slots in background
        asyncio.create_task(self._run_all_slots())

        return self._session_id

    async def pause(self) -> None:
        """Pause the session."""
        if self._state == SessionState.RUNNING:
            self._state = SessionState.PAUSED
            self._pause_event.clear()
            logger.info("Session paused: %s", self._session_id)
            await self._emit_status()

    async def resume(self) -> None:
        """Resume a paused session."""
        if self._state == SessionState.PAUSED:
            self._state = SessionState.RUNNING
            self._pause_event.set()
            logger.info("Session resumed: %s", self._session_id)
            await self._emit_status()

    async def stop(self) -> None:
        """Stop the session (kill switch)."""
        self._stop_requested = True
        self._pause_event.set()  # Unblock if paused
        self._state = SessionState.FINISHED
        logger.info("Session stopped: %s", self._session_id)
        await self._emit_status()

    async def _run_all_slots(self) -> None:
        """Execute all slots sequentially."""
        try:
            for idx, slot in enumerate(self.clock.slots):
                if self._stop_requested:
                    break

                # Wait if paused
                await self._pause_event.wait()
                if self._stop_requested:
                    break

                self._current_slot_idx = idx
                await self._emit_status()

                if slot.type == SlotType.TALK:
                    await self._run_talk_slot(slot)
                else:
                    # Phase 1: skip non-Talk slots with a brief log
                    logger.info(
                        "Skipping non-Talk slot: %s (%s)",
                        slot.id,
                        slot.type.value,
                    )
                    await asyncio.sleep(0.1)  # Brief yield

            if not self._stop_requested:
                self._state = SessionState.FINISHED
                logger.info("Session finished: %s", self._session_id)
                await self._emit_status()

        except Exception as e:
            logger.error("Session error: %s", e, exc_info=True)
            self._state = SessionState.FINISHED
            await self._emit_status()

    async def _run_talk_slot(self, slot) -> None:
        """Run a Talk slot through the conversation engine."""
        if not slot.tema:
            logger.warning("Talk slot %s has no tema, skipping", slot.id)
            return

        # Calculate max turns from duration (~15s per turn as estimate)
        max_turns = max(4, slot.duration_sec // 15)

        async def handle_turn(turn_log: TurnLog) -> None:
            """Process a completed turn: TTS + notify frontend."""
            # Synthesize audio
            voice = ""
            persona_name = ""
            if turn_log.persona == self.persona_a.id:
                voice = self.persona_a.voice or "male_voice"
                persona_name = self.persona_a.name
            else:
                voice = self.persona_b.voice or "female_voice"
                persona_name = self.persona_b.name

            audio_url: Optional[str] = None
            try:
                audio_bytes = await self.tts.synthesize(
                    turn_log.final_text, voice
                )
                # Save audio to a temporary file for serving
                audio_dir = f"cache/audio/{self._session_id}"
                from pathlib import Path

                ext = "mp3" if self.tts.provider_name.endswith("elevenlabs") else "wav"
                Path(audio_dir).mkdir(parents=True, exist_ok=True)
                audio_path = f"{audio_dir}/turn_{turn_log.turn:04d}.{ext}"
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                audio_url = f"/audio/{self._session_id}/turn_{turn_log.turn:04d}.{ext}"
            except Exception as e:
                logger.error("TTS failed for turn %d: %s", turn_log.turn, e)

            # Notify frontend
            if self._on_turn:
                event = TurnEvent(
                    slot_id=turn_log.slot_id,
                    turn=turn_log.turn,
                    persona=turn_log.persona,
                    persona_name=persona_name,
                    text=turn_log.final_text,
                    emotion=turn_log.emotion,
                    verdict=turn_log.verdict,
                    latency_ms=turn_log.latency_ms,
                    audio_url=audio_url,
                )
                await self._on_turn(event)

        engine = ConversationEngine(
            persona_a=self.persona_a,
            persona_b=self.persona_b,
            llm_client=self.llm,
            supervisor_client=self.supervisor_llm,
            condition=self.condition,
            session_logger=self._session_logger,
            session_id=self._session_id,
            persona_model=self.persona_model,
            supervisor_model=self.supervisor_model,
            on_turn=handle_turn,
        )

        await engine.run_slot(
            tema=slot.tema,
            slot_id=slot.id,
            max_turns=max_turns,
        )

    async def _emit_status(self) -> None:
        """Push status update to frontend."""
        if self._on_status is None:
            return

        current_slot = None
        current_slot_type = None
        if 0 <= self._current_slot_idx < len(self.clock.slots):
            s = self.clock.slots[self._current_slot_idx]
            current_slot = s.id
            current_slot_type = s.type

        elapsed = time.time() - self._start_time if self._start_time else 0

        status = SessionStatus(
            state=self._state,
            current_slot_id=current_slot,
            current_slot_type=current_slot_type,
            elapsed_sec=round(elapsed, 1),
        )

        await self._on_status(status)
