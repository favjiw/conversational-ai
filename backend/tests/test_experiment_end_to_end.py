"""End-to-end integration test for Experiment Mode pipeline (Milestones 1-5)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiment.config import ExperimentConfig, ConditionConfig, ModelDefinition
from experiment.run import run_experiment, estimate_calls


class TestExperimentEndToEnd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_full_pipeline_mock_execution_and_reporting(self):
        # 1-run fast test configuration
        config = ExperimentConfig(
            experiment_id="test_exp_pipeline",
            profile="pilot",
            alpha=0.05,
            models=[
                ModelDefinition(id="mock_model", provider="mock", model_name="mock-agent")
            ],
            conditions=[
                ConditionConfig(
                    condition_id="test_rq1_smoke",
                    research_question="RQ1",
                    persona_type="none",
                    model_id="mock_model",
                    n_runs=1,
                )
            ],
        )
        config.runtime.log_dir = self.temp_dir
        config.runtime.llm_mode = "mock"
        config.questionnaire.repeats = 1
        config.questionnaire.include = ["bfi", "dtdd"]  # 2 questionnaires for test speed

        # 1. Test estimate calls
        est = estimate_calls(config)
        self.assertEqual(est["conditions_count"], 1)
        self.assertEqual(est["conversation_calls"], 72)
        # 1 run * 3 snapshots * 2 agents * 2 questionnaires * 1 repeat = 12 calls
        self.assertEqual(est["questionnaire_calls"], 12)

        # 2. Run full experiment pipeline
        report_path = await run_experiment(config, force_mock=True)
        self.assertTrue(report_path.exists())

        exp_dir = Path(self.temp_dir) / "test_exp_pipeline"

        # Check config snapshot
        self.assertTrue((exp_dir / "config_snapshot.json").exists())

        # Check conversation log has 72 utterances
        conv_file = exp_dir / "conversations" / "test_rq1_smoke" / "conv_01.jsonl"
        self.assertTrue(conv_file.exists())
        conv_lines = conv_file.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(conv_lines), 72)

        # Check questionnaire log has snapshots
        q_file = exp_dir / "questionnaires" / "test_rq1_smoke" / "conv_01.jsonl"
        self.assertTrue(q_file.exists())
        q_lines = q_file.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(q_lines), 12)  # 3 snapshots * 2 agents * 2 questionnaires

        # Check Table 3 and detailed outputs
        self.assertTrue((exp_dir / "table3_summary.csv").exists())
        self.assertTrue((exp_dir / "table3_summary.md").exists())
        self.assertTrue((exp_dir / "table_detailed_test_rq1_smoke.csv").exists())

        # Check report.md and report.json contents
        report_md = report_path.read_text(encoding="utf-8")
        self.assertIn("Identity Drift Measurement Report", report_md)
        self.assertIn("Executive Summary", report_md)
        self.assertIn("Pronoun Dynamics", report_md)

        report_json = json.loads((exp_dir / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report_json["total_conversations"], 1)
        self.assertEqual(report_json["total_utterances"], 72)
        self.assertIn("conditions", report_json)


if __name__ == "__main__":
    unittest.main()
