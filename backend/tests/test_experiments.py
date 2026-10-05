import unittest
import tempfile
from pathlib import Path

from experiment.config import ExperimentConfig, ConditionConfig, ModelDefinition
from experiment.run import run_experiment, estimate_calls


class TestExperiments(unittest.IsolatedAsyncioTestCase):
    async def test_run_experiment_smoke(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = ExperimentConfig(
                experiment_id="test_exp_smoke",
                profile="pilot",
                models=[ModelDefinition(id="mock", provider="mock", model_name="mock")],
                conditions=[
                    ConditionConfig(
                        condition_id="smoke_cond",
                        model_id="mock",
                        n_runs=1,
                    )
                ],
            )
            config.runtime.log_dir = tmp_dir
            config.questionnaire.repeats = 1
            config.questionnaire.include = ["bfi"]

            report_path = await run_experiment(config, force_mock=True)
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()

