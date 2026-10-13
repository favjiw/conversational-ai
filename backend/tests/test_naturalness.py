"""Tests for PRD v1.1 Naturalness Percakapan (FR-1..FR-11)."""

import os
import unittest

from pathlib import Path

from app.conversation.engine import (
    ConversationEngine,
    build_persona_system_prompt,
    build_persona_turn_prompt,
)
from app.llm.client import MockLLMClient
from app.schemas import (
    ExperimentCondition,
    PersonaCard,
    PromptProfile,
    Tema,
    TemaMode,
)
from app.orchestrator.clock_runner import clean_text_for_tts
from experiment.naturalness import compute_metrics, load_turns, main as naturalness_main


class TestPromptProfiles(unittest.TestCase):
    def setUp(self):
        self.persona = PersonaCard(
            id="persona_a",
            name="Raka",
            gender="male",
            speaking_style="Santai",
            catchphrases=["Stay tuned bareng kita!", "Gimana nih menurut lo?"],
            topic_limits=["Kultur pop", "Gaya hidup"],
            background_facts=["Penyiar radio muda Bandung", "Suka kopi"],
            do_not=["Jangan kaku"],
            opinions=["Kopi hitam itu terbaik"],
        )
        self.tema = Tema(
            title="Ngobrol",
            mode=TemaMode.IMPROV,
            guidance="Bahas santai.",
            guidance_v2="Jawab dengan pendapat spesifik milikmu.",
        )

    def test_baseline_prompt_contains_catchphrases(self):
        prompt = build_persona_system_prompt(self.persona, PromptProfile.BASELINE_V1)
        self.assertIn("Catchphrases kamu", prompt)
        self.assertIn("HANYA fakta ini yang boleh disebut", prompt)
        self.assertIn("Batasan topik", prompt)

    def test_natural_prompt_removes_catchphrases(self):
        prompt = build_persona_system_prompt(self.persona, PromptProfile.NATURAL_V2)
        self.assertNotIn("Catchphrases kamu", prompt)
        self.assertNotIn("HANYA fakta ini yang boleh disebut", prompt)
        self.assertIn("Hindari topik berikut", prompt)
        self.assertIn("Pendapat dan seleramu", prompt)

    def test_natural_turn_prompt_uses_guidance_v2(self):
        prompt = build_persona_turn_prompt(
            tema=self.tema,
            partner_name="Salsa",
            conversation_history=[],
            profile=PromptProfile.NATURAL_V2,
            dialog_act=None,
        )
        self.assertIn("Jawab dengan pendapat spesifik milikmu", prompt)
        self.assertNotIn("Bahas santai.", prompt)


class TestCleanTextForTTS(unittest.TestCase):
    def test_removes_written_laughter(self):
        self.assertNotIn("hahaha", clean_text_for_tts("Wah hahaha seru banget"))
        self.assertNotIn("hehe", clean_text_for_tts("iya hehe bener"))
        self.assertNotIn("wkwk", clean_text_for_tts("wkwk lucu banget"))


class TestNaturalnessMetrics(unittest.TestCase):
    def test_repetitive_session_metrics(self):
        turns = [
            {"persona": "persona_b", "final_text": "Bener banget! Gimana nih menurut lo?"},
            {"persona": "persona_a", "final_text": "Bener banget! Gimana nih menurut lo?"},
            {"persona": "persona_b", "final_text": "Bener banget! Gimana nih menurut lo?"},
        ]
        m = compute_metrics(turns)
        self.assertEqual(m["n_turns"], 3)
        self.assertGreater(m["phrases_per_turn"], 0)
        self.assertGreater(m["echo_rate"], 0)


class TestNaturalnessCLI(unittest.TestCase):
    def test_fixture_regression_runs(self):
        fixture = Path(__file__).parent / "fixtures" / "session_eea08943.jsonl"
        turns = load_turns(str(fixture))
        self.assertEqual(len(turns), 4)
        m = compute_metrics(turns)
        # Top opener "bener banget" should appear on persona_b
        self.assertIn("persona_b", m["top_opener_share"])
        self.assertEqual(m["top_opener_share"]["persona_b"]["top_opener"], "bener banget gimana")

    def test_cli_smoke(self):
        fixture = Path(__file__).parent / "fixtures" / "session_eea08943.jsonl"
        rc = naturalness_main(["--session", str(fixture)])
        self.assertEqual(rc, 0)


class TestCatchphraseAndDialogAct(unittest.IsolatedAsyncioTestCase):
    async def test_natural_v2_run_slot_logs_fields(self):
        persona_a = PersonaCard(
            id="penyiar_a", name="Raka", gender="male",
            catchphrases=["Mantap pisan!"], background_facts=["Suka kopi"],
            topic_limits=[], do_not=[],
        )
        persona_b = PersonaCard(
            id="penyiar_b", name="Salsa", gender="female",
            catchphrases=["Asik banget!"], background_facts=["Suka teh"],
            topic_limits=[], do_not=[],
        )
        tema = Tema(title="Ngobrol", mode=TemaMode.IMPROV, guidance="Santai")
        engine = ConversationEngine(
            persona_a=persona_a,
            persona_b=persona_b,
            llm_client=MockLLMClient(),
            condition=ExperimentCondition.A,
            session_id="test_natural",
            profile=PromptProfile.NATURAL_V2,
            seed=42,
        )
        turns = await engine.run_slot(tema=tema, slot_id="s01", max_turns=6)
        self.assertEqual(len(turns), 6)
        for t in turns:
            self.assertEqual(t.prompt_profile, "natural_v2")
            self.assertIsNotNone(t.dialog_act)
            self.assertEqual(t.seed, 42)


if __name__ == "__main__":
    unittest.main()
