"""Unit tests for clock parser and validator."""

import json
import unittest
from pathlib import Path
import tempfile

from app.clock.parser import load_clock, load_persona, load_all_personas, get_talk_slots
from app.clock.validator import validate_clock_semantics, validate_clock_file
from app.schemas import Clock, Slot, SlotType, Tema, TemaMode


class TestClockParserAndValidator(unittest.TestCase):
    def setUp(self):
        self.valid_clock_data = {
            "show": "Test Show",
            "duration_min": 10,
            "slots": [
                {
                    "id": "s01",
                    "order": 1,
                    "type": "talk",
                    "duration_sec": 300,
                    "tema": {
                        "title": "Morning Discussion",
                        "mode": "improv",
                        "guidance": "Talk about tech news."
                    }
                },
                {
                    "id": "s02",
                    "order": 2,
                    "type": "song_block",
                    "duration_sec": 300,
                    "source": "static_audio",
                    "asset": "music/song.mp3"
                }
            ]
        }

    def test_validate_semantics_success(self):
        clock = Clock.model_validate(self.valid_clock_data)
        issues = validate_clock_semantics(clock)
        self.assertEqual(issues, [])

    def test_validate_semantics_missing_tema(self):
        invalid_data = json.loads(json.dumps(self.valid_clock_data))
        invalid_data["slots"][0]["tema"] = None
        clock = Clock.model_validate(invalid_data)
        issues = validate_clock_semantics(clock)
        self.assertTrue(any("missing a tema" in issue for issue in issues))

    def test_validate_semantics_duplicate_ids(self):
        invalid_data = json.loads(json.dumps(self.valid_clock_data))
        invalid_data["slots"][1]["id"] = "s01"
        clock = Clock.model_validate(invalid_data)
        issues = validate_clock_semantics(clock)
        self.assertTrue(any("Duplicate slot IDs" in issue for issue in issues))

    def test_validate_clock_file(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(self.valid_clock_data, f)
            temp_path = f.name

        try:
            is_valid, issues = validate_clock_file(temp_path)
            self.assertTrue(is_valid)
            self.assertEqual(issues, [])
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_get_talk_slots(self):
        clock = Clock.model_validate(self.valid_clock_data)
        talk_slots = get_talk_slots(clock)
        self.assertEqual(len(talk_slots), 1)
        self.assertEqual(talk_slots[0].id, "s01")


if __name__ == "__main__":
    unittest.main()
