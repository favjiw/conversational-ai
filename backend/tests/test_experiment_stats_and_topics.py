"""Tests for Statistical Analysis, Table Generation, and Topic Modeling (Milestone 3)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
import numpy as np

from experiment.stats import (
    compute_factor_drift,
    analyze_condition_drift,
    export_table_3_summary,
    export_table_detailed,
)
from experiment.topics import count_pronouns, run_topic_modeling


class TestStatsAndTopics(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_factor_drift_stable(self):
        # Stable data across 12, 24, 36 for 5 conversations
        records = []
        for c in range(1, 6):
            conv_id = f"conv_{c:02d}"
            for snap in (12, 24, 36):
                records.append({
                    "conv_id": conv_id,
                    "snapshot": snap,
                    "scores": {"extraversion": 3.5 + (0.01 * np.random.randn())},
                })

        res = compute_factor_drift(records, "extraversion", "personality", alpha=0.05)
        self.assertTrue(res["consistent"])
        self.assertGreaterEqual(res["omnibus_p"], 0.05)
        self.assertIn("12", res["means"])
        self.assertIn("24", res["means"])
        self.assertIn("36", res["means"])

    def test_compute_factor_drift_significant_shift(self):
        # Monotonically increasing shift: snapshot 12 -> 2.0, 24 -> 3.5, 36 -> 5.0
        records = []
        for c in range(1, 10):
            conv_id = f"conv_{c:02d}"
            records.append({"conv_id": conv_id, "snapshot": 12, "scores": {"neuroticism": 2.0 + 0.05 * c}})
            records.append({"conv_id": conv_id, "snapshot": 24, "scores": {"neuroticism": 3.5 + 0.05 * c}})
            records.append({"conv_id": conv_id, "snapshot": 36, "scores": {"neuroticism": 5.0 + 0.05 * c}})

        res = compute_factor_drift(records, "neuroticism", "personality", alpha=0.05)
        self.assertFalse(res["consistent"])
        self.assertLess(res["omnibus_p"], 0.05)

    def test_export_table_3_and_detailed(self):
        all_summary = {
            "test_rq1": {
                "summary": {
                    "personality": "10/12",
                    "interpersonal": "15/17",
                    "motivation": "5/5",
                    "emotion": "6/6",
                    "total": "36/40",
                }
            }
        }
        csv_p = Path(self.temp_dir) / "table3.csv"
        md_p = Path(self.temp_dir) / "table3.md"
        df3 = export_table_3_summary(all_summary, csv_p, md_p)
        self.assertTrue(csv_p.exists())
        self.assertTrue(md_p.exists())
        self.assertEqual(df3["Total (40)"].iloc[0], "36/40")

        factors = [
            {
                "factor": "extraversion",
                "aspect": "personality",
                "test_type": "RM-ANOVA",
                "omnibus_stat": 0.5,
                "omnibus_p": 0.62,
                "consistent": True,
                "means": {"12": 3.5, "24": 3.5, "36": 3.6},
                "posthoc": {"12_24": {"p_adj": 1.0}, "24_36": {"p_adj": 1.0}, "12_36": {"p_adj": 0.8}},
            }
        ]
        det_csv = Path(self.temp_dir) / "detailed.csv"
        df_det = export_table_detailed("test_rq1", factors, det_csv)
        self.assertTrue(det_csv.exists())
        self.assertEqual(df_det["Consistent"].iloc[0], "✓")

    def test_pronoun_counting(self):
        utterances = [
            "I feel that my perspective is quite clear. We should collaborate together.",
            "You are doing very well. Our experience matches what you said.",
        ]
        res = count_pronouns(utterances)
        self.assertGreater(res["pronouns"]["first_singular"]["count"], 0)
        self.assertGreater(res["pronouns"]["first_plural"]["count"], 0)
        self.assertGreater(res["pronouns"]["second_person"]["count"], 0)

    def test_topic_modeling(self):
        sample_utterances = [
            {"text": "I really enjoy reading books about philosophy and personal ethics in quiet times."},
            {"text": "Friendship means having deep conversations and sharing our mutual thoughts honestly."},
            {"text": "My family taught me the value of discipline and pursuing meaningful creative goals."},
        ]
        res = run_topic_modeling(sample_utterances, top_n_topics=3)
        self.assertEqual(res["num_utterances"], 3)
        self.assertIn("pronouns", res)
        self.assertIn("topics", res)


if __name__ == "__main__":
    unittest.main()
