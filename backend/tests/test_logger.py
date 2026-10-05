"""Unit tests for SessionLogger and JSONL format (FR-11, PRD Sec 10)."""

import json
import unittest
from pathlib import Path
import tempfile

from app.schemas import (
    Emotion,
    ExperimentCondition,
    LatencyMs,
    ModelsUsed,
    TurnLog,
)
from app.session_logging.logger import SessionLogger, generate_session_id


class TestSessionLogger(unittest.TestCase):
    def test_session_id_format(self):
        sess_id = generate_session_id("C")
        self.assertIn("_C", sess_id)
        # Should be format YYYYMMDD_HHMMSS_C
        parts = sess_id.split("_")
        self.assertEqual(len(parts), 3)

    def test_write_and_read_log(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sess_id = generate_session_id("C")
            logger = SessionLogger(sess_id, log_dir=tmp_dir)

            turn_log = TurnLog(
                session_id=sess_id,
                condition=ExperimentCondition.C,
                slot_id="s01",
                turn=1,
                persona="penyiar_a",
                raw_reply='{"text": "Halo Bandung! / Semangat ya!", "emotion": "happy"}',
                final_text="Halo Bandung! / Semangat ya!",
                emotion=Emotion.HAPPY,
                regenerations=0,
                verdict=None,
                latency_ms=LatencyMs(persona=200, supervisor=150, tts=300, total=650),
                models=ModelsUsed(persona="gemini-mock", supervisor="gemini-mock"),
            )

            logger.log_turn(turn_log)

            log_file = Path(tmp_dir) / f"{sess_id}.jsonl"
            self.assertTrue(log_file.exists())

            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 1)
                data = json.loads(lines[0])
                self.assertEqual(data["session_id"], sess_id)
                self.assertEqual(data["turn"], 1)
                self.assertEqual(data["persona"], "penyiar_a")


if __name__ == "__main__":
    unittest.main()
