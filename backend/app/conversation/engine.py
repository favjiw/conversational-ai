"""Conversation engine — HITS AI Live (Condition A).

Two LLMs talk directly, no supervisor.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.llm.client import LLMClient, LLMResponse
from app.schemas import (
    Emotion,
    ExperimentCondition,
    LatencyMs,
    ModelsUsed,
    PersonaCard,
    PersonaOutput,
    Tema,
    TurnLog,
)
from app.session_logging.logger import SessionLogger

logger = logging.getLogger(__name__)


# ── Prompt builders ──────────────────────────────────────────────────────────


def build_persona_system_prompt(persona: PersonaCard) -> str:
    """Build the system instruction for a persona LLM call."""
    lines = [
        f"Kamu adalah {persona.name}, seorang penyiar AI radio.",
        f"Gender: {persona.gender}.",
        f"Gaya bicara: {persona.speaking_style}",
        "",
        "Catchphrases kamu (boleh dipakai sesekali, jangan dipaksakan):",
    ]
    for cp in persona.catchphrases:
        lines.append(f"- {cp}")

    lines.append("")
    lines.append("Fakta tentang dirimu (HANYA fakta ini yang boleh disebut):")
    for fact in persona.background_facts:
        lines.append(f"- {fact}")

    lines.append("")
    lines.append("Batasan topik:")
    for limit in persona.topic_limits:
        lines.append(f"- {limit}")

    lines.append("")
    lines.append("Larangan:")
    for dont in persona.do_not:
        lines.append(f"- {dont}")

    lines.append("")
    lines.append(
        "Balas dalam bahasa Indonesia santai, seolah sedang live radio. "
        "Gunakan tanda / untuk jeda pendek dan // untuk jeda panjang. "
        "Jangan terlalu panjang, 2-4 kalimat saja per giliran."
    )
    lines.append(
        'Balas HANYA dalam format JSON: {"text": "...", "emotion": "..."}'
    )
    lines.append(
        "Pilihan emotion: neutral, happy, excited, sad, surprised, thoughtful, empathetic."
    )

    return "\n".join(lines)


def build_persona_turn_prompt(
    tema: Tema,
    partner_name: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """Build the user prompt for a persona turn."""
    parts: list[str] = []

    # Tema context
    parts.append(f"Topik: {tema.title} (mode: {tema.mode.value})")
    if tema.content:
        parts.append(f"Materi:\n{tema.content}")
    if tema.guidance:
        parts.append(f"Arahan: {tema.guidance}")

    parts.append(f"\nKamu sedang berbincang dengan {partner_name}.")

    # Conversation history
    if conversation_history:
        parts.append("\nPercakapan sejauh ini:")
        for entry in conversation_history[-10:]:  # Last 10 turns
            parts.append(f"  {entry['name']}: {entry['text']}")

    parts.append("\nSekarang giliranmu bicara. Balas dalam JSON.")

    return "\n".join(parts)


# ── Conversation state ───────────────────────────────────────────────────────


@dataclass
class ConversationState:
    """Mutable state for a single Talk slot conversation."""

    history: list[dict[str, str]] = field(default_factory=list)
    turn_number: int = 0


# ── Engine ───────────────────────────────────────────────────────────────────


class ConversationEngine:
    """Runs a Talk slot conversation between two personas.

    Args:
        persona_a: The male persona card.
        persona_b: The female persona card.
        llm_client: LLM client for persona calls.
        condition: Experiment condition.
        session_logger: Logger for writing turn logs.
        session_id: Session identifier.
        persona_model: Model ID for persona calls.
        on_turn: Optional async callback invoked after each turn completes.
    """

    def __init__(
        self,
        persona_a: PersonaCard,
        persona_b: PersonaCard,
        llm_client: LLMClient,
        condition: ExperimentCondition = ExperimentCondition.A,
        session_logger: Optional[SessionLogger] = None,
        session_id: str = "",
        persona_model: str = "",
        on_turn=None,
        supervisor_client: Optional[Any] = None,
    ):
        self.persona_a = persona_a
        self.persona_b = persona_b
        self.llm = llm_client
        self.condition = condition
        self.logger = session_logger
        self.session_id = session_id
        self.persona_model = persona_model
        self.on_turn = on_turn
        self.supervisor_client = supervisor_client
        self._state = ConversationState()

    async def run_slot(
        self,
        tema: Tema,
        slot_id: str,
        max_turns: int = 20,
        theme_playlist: Optional[list[Tema]] = None,
        turns_per_theme: int = 6,
        on_theme_change=None,
    ) -> list[TurnLog]:
        """Run a full Talk slot conversation.

        Alternates between persona A and B for up to ``max_turns`` turns.
        Optionally rotates themes from ``theme_playlist`` every ``turns_per_theme`` turns.

        Args:
            tema: Default topic for this slot.
            slot_id: Slot identifier for logging.
            max_turns: Maximum number of turns before stopping.
            theme_playlist: Optional playlist of Tema objects to rotate through.
            turns_per_theme: Number of turns per theme before switching.
            on_theme_change: Async callback when active theme switches.

        Returns:
            List of TurnLog entries for all turns.
        """
        turn_logs: list[TurnLog] = []
        self._state = ConversationState()

        current_tema = theme_playlist[0] if theme_playlist else tema
        current_theme_idx = 0

        logger.info(
            "Starting slot %s: '%s' (mode=%s, condition=%s, max_turns=%d, themes=%d)",
            slot_id,
            current_tema.title,
            current_tema.mode.value,
            self.condition.value,
            max_turns,
            len(theme_playlist) if theme_playlist else 1,
        )

        if theme_playlist and on_theme_change:
            await on_theme_change(current_tema, current_theme_idx)

        for turn_idx in range(max_turns):
            # Check theme rotation
            if (
                theme_playlist
                and turns_per_theme > 0
                and turn_idx > 0
                and turn_idx % turns_per_theme == 0
            ):
                current_theme_idx = (turn_idx // turns_per_theme) % len(theme_playlist)
                current_tema = theme_playlist[current_theme_idx]
                logger.info(
                    "Switching to theme %d/%d: '%s'",
                    current_theme_idx + 1,
                    len(theme_playlist),
                    current_tema.title,
                )
                if on_theme_change:
                    await on_theme_change(current_tema, current_theme_idx)

            # Alternate personas: even=A, odd=B
            if turn_idx % 2 == 0:
                active_persona = self.persona_a
                partner_persona = self.persona_b
            else:
                active_persona = self.persona_b
                partner_persona = self.persona_a

            self._state.turn_number = turn_idx + 1

            turn_log = await self._run_single_turn(
                active_persona=active_persona,
                partner_persona=partner_persona,
                tema=current_tema,
                slot_id=slot_id,
            )
            turn_logs.append(turn_log)
            if self.logger:
                self.logger.log_turn(turn_log)

            # Notify callback
            if self.on_turn:
                await self.on_turn(turn_log)

        logger.info(
            "Completed slot %s: %d turns", slot_id, len(turn_logs)
        )
        return turn_logs

    async def _run_single_turn(
        self,
        active_persona: PersonaCard,
        partner_persona: PersonaCard,
        tema: Tema,
        slot_id: str,
    ) -> TurnLog:
        """Execute one turn for a single persona."""
        turn = self._state.turn_number
        latency = LatencyMs()

        # ── Persona call ─────────────────────────────────────────────────
        system_prompt = build_persona_system_prompt(active_persona)
        user_prompt = build_persona_turn_prompt(
            tema=tema,
            partner_name=partner_persona.name,
            conversation_history=self._state.history,
        )

        persona_start = time.perf_counter()
        persona_response = await self.llm.generate(
            user_prompt,
            system_instruction=system_prompt,
            response_schema=PersonaOutput,
            temperature=0.7,
            model_override=self.persona_model or None,
        )
        latency.persona = int((time.perf_counter() - persona_start) * 1000)

        raw_reply = persona_response.raw
        parsed_output = self._parse_persona_output(persona_response)
        final_text = parsed_output.text
        emotion = parsed_output.emotion

        # ── Update state ─────────────────────────────────────────────────
        self._state.history.append(
            {"name": active_persona.name, "text": final_text}
        )

        # ── Build turn log ───────────────────────────────────────────────
        turn_log = TurnLog(
            session_id=self.session_id,
            condition=self.condition,
            slot_id=slot_id,
            turn=turn,
            persona=active_persona.id,
            raw_reply=raw_reply,
            verdict=None,
            regenerations=0,
            final_text=final_text,
            emotion=emotion,
            latency_ms=latency,
            models=ModelsUsed(
                persona=persona_response.model,
                supervisor="",
            ),
        )

        return turn_log

    def _parse_persona_output(self, response: LLMResponse) -> PersonaOutput:
        """Parse persona LLM response into PersonaOutput."""
        try:
            return PersonaOutput.model_validate(response.parsed)
        except Exception:
            logger.warning("Failed to parse persona output, using fallback")
            return PersonaOutput(
                text=response.raw or "[Tidak ada respons]",
                emotion=Emotion.NEUTRAL,
            )
