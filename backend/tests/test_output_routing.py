"""Tests for WebSocket client roles and audio-owner routing (console vs stage)."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def _output_status(ws):
    """Read messages until the next output_status event."""
    while True:
        msg = ws.receive_json()
        if msg["type"] == "output_status":
            return msg["data"]


class TestOutputRouting(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_console_alone_owns_audio(self):
        with self.client.websocket_connect("/ws/session?role=console") as console:
            self.assertEqual(console.receive_json()["type"], "status")
            data = _output_status(console)
            self.assertEqual(data["role"], "console")
            self.assertTrue(data["is_audio_owner"])
            self.assertFalse(data["stage_connected"])

    def test_unknown_role_falls_back_to_console(self):
        with self.client.websocket_connect("/ws/session?role=hacker") as ws:
            ws.receive_json()
            self.assertEqual(_output_status(ws)["role"], "console")

    def test_stage_takes_audio_from_console_and_returns_it(self):
        with self.client.websocket_connect("/ws/session?role=console") as console:
            console.receive_json()
            self.assertTrue(_output_status(console)["is_audio_owner"])

            with self.client.websocket_connect("/ws/session?role=stage") as stage:
                stage.receive_json()
                stage_view = _output_status(stage)
                self.assertTrue(stage_view["is_audio_owner"])
                self.assertEqual(stage_view["role"], "stage")

                console_view = _output_status(console)
                self.assertFalse(console_view["is_audio_owner"])
                self.assertTrue(console_view["stage_connected"])
                self.assertEqual(console_view["audio_owner_role"], "stage")

            # Stage closed: console becomes the owner again.
            console_view = _output_status(console)
            self.assertTrue(console_view["is_audio_owner"])
            self.assertFalse(console_view["stage_connected"])

    def test_only_owner_feedback_reaches_clock_runner(self):
        runner = MagicMock()
        with patch.object(main, "clock_runner_instance", runner):
            with self.client.websocket_connect("/ws/session?role=console") as console, \
                 self.client.websocket_connect("/ws/session?role=stage") as stage:
                feedback = {"action": "playback_feedback", "data": {"playback_id": "1:1", "state": "ended"}}

                console.send_json(feedback)
                console.send_json({"action": "ping"})
                while console.receive_json()["type"] != "pong":
                    pass
                runner.playback_feedback.assert_not_called()

                stage.send_json(feedback)
                stage.send_json({"action": "ping"})
                while stage.receive_json()["type"] != "pong":
                    pass
                runner.playback_feedback.assert_called_once_with(feedback["data"])

    def test_speaking_is_relayed_only_from_owner(self):
        with self.client.websocket_connect("/ws/session?role=console") as console, \
             self.client.websocket_connect("/ws/session?role=stage") as stage:
            console.send_json({"action": "speaking", "data": {"persona": "persona_b"}})
            stage.send_json({"action": "speaking", "data": {"persona": "persona_a"}})
            while True:
                msg = console.receive_json()
                if msg["type"] == "speaking":
                    break
            self.assertEqual(msg["data"], {"persona": "persona_a"})

    def test_owner_change_releases_pending_playback(self):
        runner = MagicMock()
        with patch.object(main, "clock_runner_instance", runner):
            with self.client.websocket_connect("/ws/session?role=console") as console:
                console.receive_json()
                _output_status(console)
                runner.release_pending_playback.reset_mock()

                # A second console does not change the owner.
                with self.client.websocket_connect("/ws/session?role=console") as other:
                    other.receive_json()
                    _output_status(other)
                runner.release_pending_playback.assert_not_called()

                with self.client.websocket_connect("/ws/session?role=stage") as stage:
                    stage.receive_json()
                    _output_status(stage)
                    runner.release_pending_playback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
