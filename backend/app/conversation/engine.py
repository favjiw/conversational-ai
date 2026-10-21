"""Conversation engine — HITS AI Live (Condition A).

Two LLMs talk directly, no supervisor.

PRD v1.1 (Naturalness Percakapan) adds, on top of the frozen ``baseline_v1``
profile, a ``natural_v2`` profile with:
- a dialog-act sampler (FR-4)
- a catchphrase scheduler (FR-3)
- session context injection (FR-7)
- a lexical anti-repetition guard (FR-5)
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.llm.client import LLMClient, LLMResponse
from app.schemas import (
    DialogAct,
    Emotion,
    ExperimentCondition,
    LatencyMs,
    ModelsUsed,
    PersonaCard,
    PersonaOutput,
    PromptProfile,
    SupervisorVerdict,
    Tema,
    TurnLog,
)
from app.session_logging.logger import SessionLogger

logger = logging.getLogger(__name__)

# Catchphrase scheduler probabilities (FR-3)
CATCHPHRASE_PROBABILITY = 1.0 / 6.0
CATCHPHRASE_COOLDOWN_TURNS = 6

# Dialog act list and anti-repetition window (FR-4, FR-5)
DIALOG_ACTS = [
    DialogAct.ANECDOTE,
    DialogAct.OPINION_DIFF,
    DialogAct.NEW_FACT,
    DialogAct.PERSONAL_QUESTION,
    DialogAct.TEASE,
    DialogAct.SHORT_REACT,
    DialogAct.TRANSITION,
]

DIALOG_ACT_HINTS = {
    DialogAct.ANECDOTE: "ceritakan pengalaman atau anekdot spesifik milikmu",
    DialogAct.OPINION_DIFF: "sampaikan pendapat yang berbeda dari partner beserta alasannya",
    DialogAct.NEW_FACT: "tambahkan satu fakta atau detail baru ke obrolan",
    DialogAct.PERSONAL_QUESTION: "tanyakan hal personal yang ringan ke partner",
    DialogAct.TEASE: "goda partner secara ringan dan ramah",
    DialogAct.SHORT_REACT: "beri reaksi singkat satu kalimat",
    DialogAct.TRANSITION: "pindahkan obrolan ke sub-topik yang masih berkaitan",
    DialogAct.WRAP_UP: "tutup tema; ini satu-satunya giliran yang boleh menyapa pendengar",
}

# Talk berbasis durasi (mode clock): instruksi giliran penutup slot Talk.
TALK_CLOSING_HINT = (
    "Waktu Talk hampir habis: tutup obrolan dengan rapi dalam giliran ini, misalnya rekap singkat, "
    "teaser segmen berikutnya, atau ajak pendengar dengerin lagu dulu. Jangan buka topik baru."
)

ANTI_REPETITION_WINDOW = 6
TRIGRAM_REPEAT_LIMIT = 3
TRIGRAM_HISTORY_WINDOW = 10
MAX_GUARD_REGENERATIONS = 1


# ── Prompt builders ──────────────────────────────────────────────────────────


def build_persona_system_prompt(
    persona: PersonaCard,
    profile: PromptProfile = PromptProfile.BASELINE_V1,
) -> str:
    """Build the system instruction for a persona LLM call.

    ``baseline_v1`` reproduces the pre-v1.1 prompt byte-for-byte.
    ``natural_v2`` removes the catchphrase list, reinterprets topic_limits as
    "avoid" topics, and relaxes the "only these facts" rule (FR-3, FR-6).
    """
    if profile == PromptProfile.BASELINE_V1:
        return _build_baseline_system_prompt(persona)
    return _build_natural_system_prompt(persona)


def _build_baseline_system_prompt(persona: PersonaCard) -> str:
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
        "Jangan terlalu panjang, 2-4 kalimat saja per giliran. "
        "ATURAN KETAT: DILARANG KERAS menggunakan emoji atau simbol apapun (seperti ⚡, 🎵, 🎙️, 🔥, 😊). "
        "DILARANG menuliskan keterangan panggung atau tindakan dalam tanda kurung seperti (tertawa), (senyum). "
        "Hanya hasilkan teks tutur lisan murni yang diucapkan lewat mikrofon."
    )
    lines.append(
        'Balas HANYA dalam format JSON: {"text": "...", "emotion": "..."}'
    )
    lines.append(
        "Pilihan emotion: neutral, happy, excited, sad, surprised, thoughtful, empathetic."
    )

    return "\n".join(lines)


def _build_natural_system_prompt(persona: PersonaCard) -> str:
    lines = [
        f"Kamu adalah {persona.name}, seorang penyiar AI radio.",
        f"Gender: {persona.gender}.",
        f"Gaya bicara: {persona.speaking_style}",
        "",
        "Fakta inti tentang dirimu:",
    ]
    for fact in persona.background_facts:
        lines.append(f"- {fact}")

    if persona.opinions:
        lines.append("")
        lines.append("Pendapat dan seleramu (boleh kamu pegang dan bela):")
        for opinion in persona.opinions:
            lines.append(f"- {opinion}")

    lines.append("")
    lines.append("Hindari topik berikut:")
    for limit in persona.topic_limits:
        lines.append(f"- {limit}")

    lines.append("")
    lines.append("Larangan:")
    for dont in persona.do_not:
        lines.append(f"- {dont}")

    lines.append("")
    lines.append(
        "Fakta inti ini tetap. Detail kecil boleh diimprovisasi asal tidak "
        "bertentangan dengan fakta inti atau ucapanmu sebelumnya."
    )
    lines.append("")
    lines.append(
        "Balas dalam bahasa Indonesia santai, seolah sedang live radio. "
        "Gunakan maksimal 2 tanda / untuk jeda pendek dan 1 tanda // untuk jeda panjang. "
        "JANGAN menuliskan tawa tertulis seperti hahaha, hehe, wkwk. "
        "ATURAN KETAT: DILARANG KERAS menggunakan emoji atau simbol apapun (seperti ⚡, 🎵, 🎙️, 🔥, 😊). "
        "DILARANG menuliskan keterangan panggung atau tindakan dalam tanda kurung seperti (tertawa), (senyum). "
        "Hanya hasilkan teks tutur lisan murni yang diucapkan lewat mikrofon."
    )
    lines.append(
        'Balas HANYA dalam format JSON: {"text": "...", "emotion": "..."}'
    )
    lines.append(
        "Pilihan emotion: neutral, happy, excited, sad, surprised, thoughtful, empathetic."
    )

    return "\n".join(lines)


def _tokens(text: str) -> list[str]:
    """Tokenize for lexical checks (alphanumeric runs, lowercased)."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _trigram_strs(text: str) -> set[str]:
    """Return the set of contiguous trigrams of a text."""
    toks = _tokens(text)
    if len(toks) < 3:
        return set()
    return {" ".join(toks[i:i + 3]) for i in range(len(toks) - 2)}


def build_persona_turn_prompt(
    tema: Tema,
    partner_name: str,
    conversation_history: list[dict[str, str]],
    profile: PromptProfile = PromptProfile.BASELINE_V1,
    dialog_act: Optional[DialogAct] = None,
    catchphrase: Optional[str] = None,
    session_context: Optional[dict] = None,
    last_turn_in_theme: bool = False,
    previous_theme: Optional[Tema] = None,
    extra_instructions: Optional[list[str]] = None,
) -> str:
    """Build the user prompt for a persona turn.

    ``extra_instructions`` (mode clock: penutup Talk, komentar penonton, gaya HITS) are
    appended right before the final instruction; ``None`` keeps the prompt unchanged.

    ``baseline_v1`` reproduces the pre-v1.1 prompt. ``natural_v2`` injects the
    sampled dialog act, an optional catchphrase, session context, and the
    anti-repetition guidance (FR-4, FR-3, FR-7, FR-5).
    """
    if profile == PromptProfile.BASELINE_V1:
        return _build_baseline_turn_prompt(tema, partner_name, conversation_history, extra_instructions)
    return _build_natural_turn_prompt(
        tema=tema,
        partner_name=partner_name,
        conversation_history=conversation_history,
        dialog_act=dialog_act,
        catchphrase=catchphrase,
        session_context=session_context,
        last_turn_in_theme=last_turn_in_theme,
        previous_theme=previous_theme,
        extra_instructions=extra_instructions,
    )


def _append_extras(parts: list[str], extra_instructions: Optional[list[str]]) -> None:
    for line in extra_instructions or []:
        if line:
            parts.append(f"\n{line}")


def _build_baseline_turn_prompt(
    tema: Tema,
    partner_name: str,
    conversation_history: list[dict[str, str]],
    extra_instructions: Optional[list[str]] = None,
) -> str:
    parts: list[str] = []

    parts.append(f"Topik: {tema.title} (mode: {tema.mode.value})")
    if tema.content:
        parts.append(f"Materi:\n{tema.content}")
    if tema.guidance:
        parts.append(f"Arahan: {tema.guidance}")

    parts.append(f"\nKamu sedang berbincang dengan {partner_name}.")

    if conversation_history:
        parts.append("\nPercakapan sejauh ini:")
        for entry in conversation_history[-10:]:
            parts.append(f"  {entry['name']}: {entry['text']}")

    _append_extras(parts, extra_instructions)
    parts.append("\nSekarang giliranmu bicara. Balas dalam JSON.")

    return "\n".join(parts)


def _build_natural_turn_prompt(
    tema: Tema,
    partner_name: str,
    conversation_history: list[dict[str, str]],
    dialog_act: Optional[DialogAct],
    catchphrase: Optional[str],
    session_context: Optional[dict],
    last_turn_in_theme: bool,
    previous_theme: Optional[Tema],
    extra_instructions: Optional[list[str]] = None,
) -> str:
    parts: list[str] = []

    guidance = tema.guidance_v2 or tema.guidance
    parts.append(f"Topik: {tema.title} (mode: {tema.mode.value})")
    if tema.content:
        parts.append(f"Materi:\n{tema.content}")
    if guidance:
        parts.append(f"Arahan: {guidance}")

    parts.append(_build_session_context_block(session_context, previous_theme))

    parts.append(f"\nKamu sedang berbincang dengan {partner_name}.")

    if conversation_history:
        parts.append("\nPercakapan sejauh ini:")
        for entry in conversation_history[-10:]:
            parts.append(f"  {entry['name']}: {entry['text']}")

    if dialog_act is not None:
        hint = DIALOG_ACT_HINTS[dialog_act]
        parts.append(f"\nTugas giliran ini: {hint}.")

    parts.append(f"\nPanjang giliran: {_sample_length()}.")

    anti = _anti_repetition_guidance(conversation_history)
    if anti:
        parts.append(anti)

    if catchphrase:
        parts.append(
            f'\nBoleh memakai catchphrase berikut kali ini saja: "{catchphrase}"'
        )

    _append_extras(parts, extra_instructions)
    parts.append("\nSekarang giliranmu bicara. Balas dalam JSON.")

    return "\n".join(parts)


def _build_session_context_block(
    session_context: Optional[dict],
    previous_theme: Optional[Tema],
) -> str:
    """Build the session-context block (FR-7)."""
    ctx = session_context or {}
    has_song = bool(ctx.get("has_song"))
    previous_song = ctx.get("previous_song") or ""

    if has_song:
        song_note = "Ada lagu sedang atau baru diputar."
        if previous_song:
            song_note += f" Lagu sebelumnya: {previous_song}."
    else:
        song_note = (
            'Tidak ada lagu yang sedang diputar. '
            'JANGAN merujuk ke lagu ("setelah lagu", "lagu tadi").'
        )

    if ctx.get("listener_answered"):
        listener_note = "Ada pendengar yang menjawab; boleh merujuk jawabannya."
    else:
        listener_note = (
            "Belum ada pendengar yang menjawab. "
            "Jangan mengaku ada pendengar yang sedang membalas."
        )

    availability = "Cuaca, waktu, dan berita TIDAK tersedia kecuali sudah diberikan di Materi."

    return f"Konteks sesi: {song_note} {listener_note} {availability}"


def _sample_length() -> str:
    roll = random.random()
    if roll < 0.4:
        return "satu kalimat pendek (sekitar 8 sampai 15 kata)"
    if roll < 0.8:
        return "sedang (sekitar 20 sampai 35 kata)"
    return "panjang (maksimal sekitar 60 kata)"


def _anti_repetition_guidance(conversation_history: list[dict[str, str]]) -> str:
    """Compute forbidden openers/closers from recent turns (FR-5)."""
    if len(conversation_history) < 2:
        return ""
    recent = conversation_history[-ANTI_REPETITION_WINDOW:]
    openers: list[str] = []
    closers: list[str] = []
    for entry in recent:
        toks = _tokens(entry["text"])
        if len(toks) >= 3:
            openers.append(" ".join(toks[:3]))
            closers.append(" ".join(toks[-3:]))

    forbidden: list[str] = []
    for op in set(openers):
        if openers.count(op) >= 2:
            forbidden.append(op)
    for cl in set(closers):
        if closers.count(cl) >= 2:
            forbidden.append(cl)

    if not forbidden:
        return ""
    joined = ", ".join(f'"{f}"' for f in forbidden[:6])
    return f"\nJangan membuka atau menutup giliran dengan: {joined}."


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
        profile: PromptProfile = PromptProfile.BASELINE_V1,
        seed: Optional[int] = None,
        session_context: Optional[dict] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
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
        self.profile = profile
        self.temperature = temperature
        self.top_p = top_p
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.session_context = session_context or {}
        self._rng = random.Random(seed)
        self.seed = seed
        self._state = ConversationState()
        # Per-persona catchphrase cooldown state (FR-3)
        self._catchphrase_last_turn: dict[str, int] = {}
        self._catchphrase_used_in_theme: dict[str, int] = {}
        self._theme_counter = 0

    async def run_slot(
        self,
        tema: Tema,
        slot_id: str,
        max_turns: int = 20,
        theme_playlist: Optional[list[Tema]] = None,
        turns_per_theme: int = 6,
        on_theme_change=None,
        on_turn=None,
        should_stop: Optional[Callable[[], bool]] = None,
        is_closing: Optional[Callable[[], bool]] = None,
        turn_extras: Optional[Callable[[int, bool], list[str]]] = None,
        theme_index_fn: Optional[Callable[[int], int]] = None,
    ) -> list[TurnLog]:
        """Run a full Talk slot conversation.

        Alternates between persona A and B for up to ``max_turns`` turns.
        Optionally rotates themes from ``theme_playlist`` every ``turns_per_theme`` turns.

        Mode clock (Talk berbasis durasi): ``should_stop`` is checked before every turn
        after the first (``max_turns`` stays the safety limit), ``is_closing`` marks closing
        turns (prompt ``TALK_CLOSING_HINT``, logged as ``wrap_up``),
        ``turn_extras(turn_idx, closing)`` returns extra prompt lines for that turn, and
        ``theme_index_fn(turn_idx)`` picks the playlist point from elapsed Talk time (no
        wrap-around, the last point stays until the end). All default to the previous behaviour.

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
        previous_theme: Optional[Tema] = None

        logger.info(
            "Starting slot %s: '%s' (mode=%s, condition=%s, max_turns=%d, themes=%d, profile=%s)",
            slot_id,
            current_tema.title,
            current_tema.mode.value,
            self.condition.value,
            max_turns,
            len(theme_playlist) if theme_playlist else 1,
            self.profile.value,
        )

        if theme_playlist and on_theme_change:
            await on_theme_change(current_tema, current_theme_idx)

        for turn_idx in range(max_turns):
            if should_stop is not None and turn_idx > 0 and should_stop():
                logger.info("Slot %s stops after %d turns (time budget)", slot_id, turn_idx)
                break

            # Check theme rotation: by elapsed Talk time (mode clock) or every turns_per_theme turns
            next_theme_idx: Optional[int] = None
            if theme_playlist and theme_index_fn is not None:
                wanted = max(0, min(len(theme_playlist) - 1, theme_index_fn(turn_idx)))
                if wanted != current_theme_idx:
                    next_theme_idx = wanted
            elif (
                theme_playlist
                and turns_per_theme > 0
                and turn_idx > 0
                and turn_idx % turns_per_theme == 0
            ):
                next_theme_idx = (turn_idx // turns_per_theme) % len(theme_playlist)
            if next_theme_idx is not None:
                previous_theme = current_tema
                current_theme_idx = next_theme_idx
                current_tema = theme_playlist[current_theme_idx]
                self._theme_counter += 1
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

            # Is this the last turn of the current theme? (FR-4 wrap_up rule)
            if should_stop is not None or theme_index_fn is not None:
                last_turn_in_theme = False  # Talk berbasis durasi: penutup ditentukan is_closing
            elif theme_playlist and turns_per_theme > 0:
                last_turn_in_theme = (turn_idx % turns_per_theme) == (turns_per_theme - 1)
            else:
                last_turn_in_theme = (turn_idx == max_turns - 1)

            closing = bool(is_closing and is_closing())
            extras = list(turn_extras(turn_idx, closing)) if turn_extras else []
            if closing:
                extras.append(TALK_CLOSING_HINT)

            turn_log = await self._run_single_turn(
                active_persona=active_persona,
                partner_persona=partner_persona,
                tema=current_tema,
                slot_id=slot_id,
                last_turn_in_theme=last_turn_in_theme,
                previous_theme=previous_theme,
                closing=closing,
                extra_instructions=extras or None,
            )
            turn_logs.append(turn_log)
            if self.logger:
                self.logger.log_turn(turn_log)

            # Notify callback
            cb = on_turn or self.on_turn
            if cb:
                await cb(turn_log)

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
        last_turn_in_theme: bool = False,
        previous_theme: Optional[Tema] = None,
        closing: bool = False,
        extra_instructions: Optional[list[str]] = None,
    ) -> TurnLog:
        """Execute one turn for a single persona."""
        turn = self._state.turn_number
        latency = LatencyMs()

        # ── Sample dialog act + catchphrase (natural_v2 only) ────────────
        # A closing turn of a duration-based Talk is a wrap-up in every profile.
        if closing:
            dialog_act: Optional[DialogAct] = DialogAct.WRAP_UP
        else:
            dialog_act = self._sample_dialog_act(active_persona, last_turn_in_theme)
        catchphrase = self._sample_catchphrase(active_persona)

        # ── Persona call ─────────────────────────────────────────────────
        system_prompt = build_persona_system_prompt(active_persona, self.profile)
        user_prompt = build_persona_turn_prompt(
            tema=tema,
            partner_name=partner_persona.name,
            conversation_history=self._state.history,
            profile=self.profile,
            dialog_act=dialog_act,
            catchphrase=catchphrase,
            session_context=self.session_context,
            last_turn_in_theme=last_turn_in_theme,
            previous_theme=previous_theme,
            extra_instructions=extra_instructions,
        )

        persona_start = time.perf_counter()
        persona_response = await self.llm.generate(
            user_prompt,
            system_instruction=system_prompt,
            response_schema=PersonaOutput,
            temperature=self.temperature,
            model_override=self.persona_model or None,
            top_p=self.top_p,
            presence_penalty=self.presence_penalty,
            frequency_penalty=self.frequency_penalty,
        )
        latency.persona = int((time.perf_counter() - persona_start) * 1000)

        raw_reply = persona_response.raw
        parsed_output = self._parse_persona_output(persona_response)
        final_text = parsed_output.text
        emotion = parsed_output.emotion

        # ── Anti-repetition guard (FR-5, natural_v2 only) ────────────────
        guard_regenerations = 0
        if self.profile == PromptProfile.NATURAL_V2:
            for _ in range(MAX_GUARD_REGENERATIONS):
                if not self._guard_triggered(final_text):
                    break
                guard_regenerations += 1
                reg_start = time.perf_counter()
                persona_response = await self.llm.generate(
                    user_prompt,
                    system_instruction=system_prompt,
                    response_schema=PersonaOutput,
                    temperature=self.temperature,
                    model_override=self.persona_model or None,
                    top_p=self.top_p,
                    presence_penalty=self.presence_penalty,
                    frequency_penalty=self.frequency_penalty,
                )
                latency.persona += int((time.perf_counter() - reg_start) * 1000)
                raw_reply = persona_response.raw
                parsed_output = self._parse_persona_output(persona_response)
                final_text = parsed_output.text
                emotion = parsed_output.emotion

        # ── Update state ─────────────────────────────────────────────────
        self._state.history.append(
            {"name": active_persona.name, "text": final_text}
        )
        if catchphrase:
            self._catchphrase_last_turn[active_persona.id] = turn
            self._catchphrase_used_in_theme[active_persona.id] = self._theme_counter

        # ── Supervisor check for Condition C ────────────────────────────
        verdict = None
        supervisor_model = ""
        if self.condition == ExperimentCondition.C and self.supervisor_client:
            sup_start = time.perf_counter()
            sup_prompt = f"Evaluasi drift persona {active_persona.name}: {final_text}"
            sup_res = await self.supervisor_client.generate(
                sup_prompt,
                response_schema=SupervisorVerdict,
            )
            latency.supervisor = int((time.perf_counter() - sup_start) * 1000)
            supervisor_model = sup_res.model
            try:
                verdict = SupervisorVerdict.model_validate(sup_res.parsed)
            except Exception:
                verdict = SupervisorVerdict(drift_detected=False)

        latency.total = latency.persona + latency.supervisor + latency.tts

        # ── Build turn log ───────────────────────────────────────────────
        turn_log = TurnLog(
            session_id=self.session_id,
            condition=self.condition,
            slot_id=slot_id,
            turn=turn,
            persona=active_persona.id,
            raw_reply=raw_reply,
            verdict=verdict,
            regenerations=0,
            final_text=final_text,
            emotion=emotion,
            latency_ms=latency,
            models=ModelsUsed(
                persona=persona_response.model,
                supervisor=supervisor_model,
            ),
            prompt_profile=self.profile.value,
            dialog_act=dialog_act.value if dialog_act else None,
            catchphrase_injected=catchphrase,
            guard_regenerations=guard_regenerations,
            seed=self.seed,
        )

        return turn_log

    # ── Naturalness samplers & guards ──────────────────────────────────────

    def _sample_dialog_act(
        self,
        persona: PersonaCard,
        last_turn_in_theme: bool,
    ) -> Optional[DialogAct]:
        """Sample a dialog act, or None for baseline_v1 (FR-4)."""
        if self.profile == PromptProfile.BASELINE_V1:
            return None

        if last_turn_in_theme:
            return DialogAct.WRAP_UP

        choices = list(DIALOG_ACTS)
        if getattr(self, "_last_dialog_act", None) in choices:
            choices = [a for a in choices if a != self._last_dialog_act]
        act = self._rng.choice(choices)
        self._last_dialog_act = act
        return act

    def _sample_catchphrase(self, persona: PersonaCard) -> Optional[str]:
        """Schedule a catchphrase with 1/6 probability + cooldown (FR-3)."""
        if self.profile == PromptProfile.BASELINE_V1:
            return None
        if not persona.catchphrases:
            return None

        turn = self._state.turn_number
        last = self._catchphrase_last_turn.get(persona.id, -CATCHPHRASE_COOLDOWN_TURNS)
        used_in_theme = self._catchphrase_used_in_theme.get(persona.id)

        if turn - last < CATCHPHRASE_COOLDOWN_TURNS:
            return None
        if used_in_theme == self._theme_counter:
            return None
        if self._rng.random() >= CATCHPHRASE_PROBABILITY:
            return None

        return self._rng.choice(persona.catchphrases)

    def _guard_triggered(self, text: str) -> bool:
        """Return True if the reply repeats a forbidden opener/closer or trigram."""
        if not text:
            return False

        recent = self._state.history[-ANTI_REPETITION_WINDOW:]
        toks = _tokens(text)
        if len(toks) >= 3:
            opener = " ".join(toks[:3])
            closer = " ".join(toks[-3:])
            for entry in recent:
                e_toks = _tokens(entry["text"])
                if len(e_toks) >= 3:
                    if opener == " ".join(e_toks[:3]):
                        return True
                    if closer == " ".join(e_toks[-3:]):
                        return True

        if len(toks) >= 3:
            history_trigrams: dict[str, int] = {}
            for entry in self._state.history[-TRIGRAM_HISTORY_WINDOW:]:
                for tg in _trigram_strs(entry["text"]):
                    history_trigrams[tg] = history_trigrams.get(tg, 0) + 1
            for tg in _trigram_strs(text):
                if history_trigrams.get(tg, 0) + 1 >= TRIGRAM_REPEAT_LIMIT:
                    return True

        return False

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
