"""Unit tests for ConversationEngine (FR-3)."""

import unittest
from app.conversation.engine import ConversationEngine
from app.llm.client import MockLLMClient
from app.schemas import ExperimentCondition, PersonaCard, Tema, TemaMode


class TestConversation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.persona_a = PersonaCard(
            id="penyiar_a",
            name="Rian",
            gender="male",
            age_range="20-25",
            speaking_style="Enerjik, santai, banyak slang Bandung",
            background_facts=["Kuliah di Unikom", "Suka dengerin indie pop"],
            catchphrases=["Mantap pisan!", "Gas pol!"],
            topic_limits=["Jangan bicara politik praktis"],
            do_not=["Jangan memotong pembicaraan dengan kasar"],
        )
        self.persona_b = PersonaCard(
            id="penyiar_b",
            name="Maya",
            gender="female",
            age_range="20-25",
            speaking_style="Ramah, ceria, tertata rapi",
            background_facts=["Suka kuliner dan podcast", "Alumni DKV"],
            catchphrases=["Asik banget!", "Gitu dong!"],
            topic_limits=["Jangan debat SARA"],
            do_not=["Jangan memberi saran medis ilegal"],
        )
        self.tema = Tema(
            title="Ngobrol Santai",
            mode=TemaMode.IMPROV,
            guidance="Bahas kegiatan pagi hari dan cuaca Bandung hari ini.",
        )

    async def test_condition_a_run_slot(self):
        engine = ConversationEngine(
            persona_a=self.persona_a,
            persona_b=self.persona_b,
            llm_client=MockLLMClient(),
            supervisor_client=MockLLMClient(),
            condition=ExperimentCondition.A,
            session_id="test_sess_a",
        )
        turns = await engine.run_slot(tema=self.tema, slot_id="s01", max_turns=2)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].turn, 1)
        self.assertEqual(turns[1].turn, 2)
        self.assertEqual(turns[0].persona, "penyiar_a")
        self.assertEqual(turns[1].persona, "penyiar_b")

    async def test_condition_b_run_slot(self):
        engine = ConversationEngine(
            persona_a=self.persona_a,
            persona_b=self.persona_b,
            llm_client=MockLLMClient(),
            supervisor_client=MockLLMClient(),
            condition=ExperimentCondition.B,
            session_id="test_sess_b",
        )
        turns = await engine.run_slot(tema=self.tema, slot_id="s01", max_turns=2)
        self.assertEqual(len(turns), 2)

    async def test_condition_c_run_slot_with_supervisor(self):
        engine = ConversationEngine(
            persona_a=self.persona_a,
            persona_b=self.persona_b,
            llm_client=MockLLMClient(),
            supervisor_client=MockLLMClient(),
            condition=ExperimentCondition.C,
            session_id="test_sess_c",
        )
        turns = await engine.run_slot(tema=self.tema, slot_id="s01", max_turns=2)
        self.assertEqual(len(turns), 2)
        # In Condition C, supervisor verdict should be populated
        self.assertIsNotNone(turns[0].verdict)


if __name__ == "__main__":
    unittest.main()
