"""Unit tests for Orchestrator state machine (FR-2)."""

import asyncio
import unittest
import tempfile

from app.llm.client import MockLLMClient
from app.orchestrator.engine import Orchestrator
from app.schemas import Clock, ExperimentCondition, PersonaCard, SessionState, Slot, SlotType, Tema, TemaMode
from app.tts.provider import MockTTSProvider


class TestOrchestrator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock(
            show="Uji Coba",
            duration_min=5,
            slots=[
                Slot(
                    id="s01",
                    order=1,
                    type=SlotType.TALK,
                    duration_sec=30,
                    tema=Tema(
                        title="Topik Singkat",
                        mode=TemaMode.IMPROV,
                        guidance="Sapa sebentar",
                    ),
                )
            ],
        )
        self.persona_a = PersonaCard(
            id="penyiar_a",
            name="Rian",
            gender="male",
            speaking_style="Santai",
            background_facts=["Fakta 1"],
            catchphrases=["Yo!"],
            topic_limits=[],
            do_not=[],
        )
        self.persona_b = PersonaCard(
            id="penyiar_b",
            name="Maya",
            gender="female",
            speaking_style="Ceria",
            background_facts=["Fakta 2"],
            catchphrases=["Halo!"],
            topic_limits=[],
            do_not=[],
        )

    async def test_orchestrator_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tts = MockTTSProvider()
            orchestrator = Orchestrator(
                clock=self.clock,
                persona_a=self.persona_a,
                persona_b=self.persona_b,
                llm_client=MockLLMClient(),
                supervisor_client=MockLLMClient(),
                tts_provider=tts,
                condition=ExperimentCondition.A,
                log_dir=tmp_dir,
            )

            self.assertEqual(orchestrator.state, SessionState.IDLE)
            session_id = await orchestrator.start()
            self.assertEqual(orchestrator.state, SessionState.RUNNING)
            self.assertIn("_A", session_id)

            await orchestrator.pause()
            self.assertEqual(orchestrator.state, SessionState.PAUSED)

            await orchestrator.resume()
            self.assertEqual(orchestrator.state, SessionState.RUNNING)

            await orchestrator.stop()
            self.assertEqual(orchestrator.state, SessionState.FINISHED)


if __name__ == "__main__":
    unittest.main()
