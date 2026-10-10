"""Unit tests for FastAPI endpoints."""

import unittest
from fastapi.testclient import TestClient

from app.main import app


from unittest.mock import patch
from app.tts.provider import MockTTSProvider


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("llm_mode", data)

    def test_get_clock(self):
        response = self.client.get("/api/clock")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["show"], "Pagi Bener")
        self.assertTrue(len(data["slots"]) > 0)

    def test_get_personas(self):
        response = self.client.get("/api/personas")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("persona_a", data)
        self.assertIn("persona_b", data)

    def test_validate_clock_endpoint(self):
        valid_clock = {
            "show": "Test Show",
            "duration_min": 10,
            "slots": [
                {
                    "id": "s01",
                    "order": 1,
                    "type": "talk",
                    "duration_sec": 300,
                    "tema": {
                        "title": "Opening",
                        "mode": "improv",
                        "guidance": "Sapa pendengar",
                    },
                },
                {
                    "id": "s02",
                    "order": 2,
                    "type": "song_block",
                    "duration_sec": 300,
                    "source": "static_audio",
                    "asset": "song.mp3",
                },
            ],
        }
        response = self.client.post("/api/clock/validate", json={"clock": valid_clock})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    def test_tts_endpoint(self):
        with patch("app.main.tts_provider", MockTTSProvider()):
            response = self.client.post("/api/tts", json={"text": "Halo pendengar!", "voice": "male_voice"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "audio/wav")
            self.assertTrue(response.content.startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()
