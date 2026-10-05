"""Tests for Experiment Mode Runner (Milestone 1)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.llm.client import MockLLMClient
from experiment.config import load_config, ConditionConfig
from experiment.runner import (
    load_themes,
    load_personas,
    build_messages_for_agent,
    ExperimentConversationRunner,
)


class TestExperimentRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_themes_and_correction(self):
        themes = load_themes("backend/experiment/data/themes_aron1997.json")
        self.assertEqual(len(themes), 36)
        self.assertIn("fire", themes[33]["text"].lower())
        self.assertNotIn(themes[32]["text"], themes[33]["text"])

    def test_personas_loaded(self):
        low_p = load_personas("backend/experiment/personas/low.yaml")
        high_p = load_personas("backend/experiment/personas/high.yaml")
        self.assertEqual(len(low_p), 20)
        self.assertEqual(len(high_p), 20)
        self.assertEqual(low_p[0]["id"], "low_01")
        self.assertEqual(high_p[0]["id"], "high_01")

    def test_message_building(self):
        themes = load_themes("backend/experiment/data/themes_aron1997.json")
        sys_prompt = "Brief thoughts."
        history = [
            {"theme_id": 1, "agent_a": "A reply 1", "agent_b": "B reply 1"}
        ]
        # Agent A answering theme 2
        msgs_a = build_messages_for_agent("A", 1, history, themes, sys_prompt)
        # Verify no two consecutive 'user' roles
        for i in range(len(msgs_a) - 1):
            self.assertFalse(msgs_a[i]["role"] == "user" and msgs_a[i+1]["role"] == "user")

        # Agent B answering theme 2 (requires history[1]["agent_a"])
        history.append({"theme_id": 2, "agent_a": "A reply 2", "agent_b": ""})
        msgs_b = build_messages_for_agent("B", 1, history, themes, sys_prompt)
        for i in range(len(msgs_b) - 1):
            self.assertFalse(msgs_b[i]["role"] == "user" and msgs_b[i+1]["role"] == "user")
        self.assertIn("A reply 2", msgs_b[-1]["content"])

    async def test_full_mock_conversation_72_utterances(self):
        config = load_config("backend/experiment/configs/pilot.yaml")
        config.runtime.log_dir = self.temp_dir
        client_a = MockLLMClient()
        client_b = MockLLMClient()

        runner = ExperimentConversationRunner(config, client_a, client_b)
        condition = ConditionConfig(
            condition_id="test_mock_rq1",
            research_question="RQ1",
            persona_type="none",
            model_id="mock_model",
            n_runs=1,
        )

        snapshots_hit = []
        async def on_snap(conv_id, snapshot_theme, history, **kwargs):
            snapshots_hit.append(snapshot_theme)

        utterances = await runner.run_single_conversation(
            condition=condition,
            conv_idx=1,
            on_snapshot=on_snap,
        )

        self.assertEqual(len(utterances), 72)
        self.assertEqual(snapshots_hit, [12, 24, 36])

        # Verify alternation
        for i in range(0, 72, 2):
            self.assertEqual(utterances[i]["agent"], "A")
            self.assertEqual(utterances[i+1]["agent"], "B")
            self.assertEqual(utterances[i]["theme_idx"], i // 2)
            self.assertEqual(utterances[i+1]["theme_idx"], i // 2)

        # Check saved JSONL
        log_file = Path(self.temp_dir) / config.experiment_id / "conversations" / "test_mock_rq1" / "conv_01.jsonl"
        self.assertTrue(log_file.exists())
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 72)


if __name__ == "__main__":
    unittest.main()
