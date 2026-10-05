import sys
import unittest
from pathlib import Path
import tempfile

# Ensure root directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.schemas import ExperimentCondition
from experiments.run import ExperimentRunner


class TestExperiments(unittest.IsolatedAsyncioTestCase):
    async def test_run_single_session_and_export_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = ExperimentRunner(output_dir=tmp_dir)

            sess_id, turns, metrics = await runner.run_single_session(
                condition=ExperimentCondition.C,
                turns=2,
            )

            self.assertTrue(sess_id.startswith("2026"))
            self.assertEqual(len(turns), 2)
            self.assertEqual(metrics["total_turns"], 2)
            self.assertEqual(metrics["condition"], "C")

            # Test CSV export
            csv_path = Path(tmp_dir) / "summary.csv"
            runner.export_summary_csv([metrics], csv_path)
            self.assertTrue(csv_path.exists())

            with open(csv_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("session_id,condition,total_turns", content)
                self.assertIn(sess_id, content)


if __name__ == "__main__":
    unittest.main()
