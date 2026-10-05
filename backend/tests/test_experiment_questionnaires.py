"""Tests for Questionnaires, Scoring, and Snapshot Engine (Milestone 2)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.llm.client import MockLLMClient, LLMResponse
from experiment.config import load_config, ConditionConfig
from experiment.scoring import (
    load_all_questionnaires,
    parse_likert_response,
    compute_factor_scores,
)
from experiment.snapshot import (
    SnapshotEngine,
    format_chathistory,
    format_questionnaire_setup,
)


class TestQuestionnairesAndScoring(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_all_14_questionnaires_40_factors(self):
        all_q = load_all_questionnaires("backend/experiment/questionnaires")
        self.assertEqual(len(all_q), 14)

        aspect_factors = {"personality": 0, "interpersonal": 0, "motivation": 0, "emotion": 0}
        total_factors = 0

        for q_id, q_def in all_q.items():
            aspect = q_def["aspect"]
            n_sub = len(q_def["subscales"])
            aspect_factors[aspect] += n_sub
            total_factors += n_sub

        self.assertEqual(aspect_factors["personality"], 12)
        self.assertEqual(aspect_factors["interpersonal"], 17)
        self.assertEqual(aspect_factors["motivation"], 5)
        self.assertEqual(aspect_factors["emotion"], 6)
        self.assertEqual(total_factors, 40)

    def test_reverse_scoring_calculation(self):
        all_q = load_all_questionnaires("backend/experiment/questionnaires")
        bfi = all_q["bfi"]
        # Extraversion: items [1, 6R, 11, 16, 21R, 26, 31R, 36]
        # scale 1-5. If raw = 1 on reverse item 6, reverse scored = (1+5)-1 = 5.
        raw_answers = {
            1: 4.0,
            6: 1.0,  # 6 is reverse, so scored = 5
            11: 4.0,
            16: 4.0,
            21: 1.0,  # 21 is reverse, so scored = 5
            26: 4.0,
            31: 1.0,  # 31 is reverse, so scored = 5
            36: 4.0,
        }
        scores = compute_factor_scores(bfi, raw_answers)
        # All extraversion items scored 4 or 5: (4+5+4+4+5+4+5+4)/8 = 35/8 = 4.375
        self.assertAlmostEqual(scores["extraversion"], 4.375, places=3)

    def test_parse_likert_response_formats(self):
        # 1. JSON
        text_json = '{"1": 4, "2": 3, "3": 5, "4": 2}'
        ans, ok = parse_likert_response(text_json, 4, 1, 5)
        self.assertTrue(ok)
        self.assertEqual(ans[1], 4)
        self.assertEqual(ans[3], 5)

        # 2. Line format
        text_lines = "Item 1: 4\nItem 2: 3\nItem 3: 5\nItem 4: 2"
        ans2, ok2 = parse_likert_response(text_lines, 4, 1, 5)
        self.assertTrue(ok2)
        self.assertEqual(ans2[2], 3)

        # 3. Bracket list
        text_bracket = "[4, 3, 5, 2]"
        ans3, ok3 = parse_likert_response(text_bracket, 4, 1, 5)
        self.assertTrue(ok3)
        self.assertEqual(ans3[4], 2)

    async def test_snapshot_engine_execution(self):
        config = load_config("backend/experiment/configs/pilot.yaml")
        config.runtime.log_dir = self.temp_dir
        config.questionnaire.repeats = 1
        config.questionnaire.include = ["bfi", "dtdd"]  # test subset for speed

        class QMockClient(MockLLMClient):
            async def generate(self, prompt, **kwargs):
                # Return dummy valid answers
                data = {str(i): 3 for i in range(1, 50)}
                return LLMResponse(raw=json.dumps(data), parsed=data, model="mock-q")

        client = QMockClient()
        engine = SnapshotEngine(config, client, client)

        history = [
            {"theme_id": 1, "agent_a": "Hello partner", "agent_b": "Nice to meet you"}
        ]
        condition = ConditionConfig(
            condition_id="test_mock_snap",
            research_question="RQ1",
            persona_type="none",
            model_id="mock_model",
            n_runs=1,
        )

        records = await engine.run_snapshot_for_conversation(
            conv_id="conv_01",
            snapshot_theme=12,
            history=history,
            condition=condition,
        )

        self.assertEqual(len(records), 4)  # 2 agents x 2 questionnaires
        self.assertTrue(all(r["parse_ok"] for r in records))
        self.assertIn("extraversion", records[0]["scores"])


if __name__ == "__main__":
    unittest.main()
