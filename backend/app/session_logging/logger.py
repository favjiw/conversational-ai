"""JSONL session logger (FR-11).

Every turn produces one line in the session log file. Log files are named
``{session_id}.jsonl`` and written to the configured LOG_DIR.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import TurnLog

logger = logging.getLogger(__name__)


class SessionLogger:
    """Append-only JSONL logger for a single session.

    Args:
        session_id: Unique session identifier.
        log_dir: Directory where log files are written.
    """

    def __init__(self, session_id: str, log_dir: str | Path = "logs"):
        self.session_id = session_id
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / f"{session_id}.jsonl"
        self._turn_count = 0
        logger.info("Session logger initialised: %s", self._log_path)

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def log_turn(self, turn_log: TurnLog) -> None:
        """Append a single turn log entry.

        Args:
            turn_log: Validated TurnLog model instance.
        """
        line = turn_log.model_dump_json() + "\n"
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line)
        self._turn_count += 1
        logger.debug(
            "Logged turn %d for persona %s in session %s",
            turn_log.turn,
            turn_log.persona,
            self.session_id,
        )

    def read_logs(self) -> list[TurnLog]:
        """Read all turn logs from the session file.

        Returns:
            List of TurnLog instances.
        """
        if not self._log_path.exists():
            return []

        logs: list[TurnLog] = []
        with open(self._log_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    logs.append(TurnLog.model_validate(data))
                except Exception as e:
                    logger.warning(
                        "Failed to parse log line %d: %s", line_num, e
                    )
        return logs


def generate_session_id(condition: str = "") -> str:
    """Generate a unique session ID with timestamp and optional condition.

    Format: ``{date}_{time}_{condition}`` e.g. ``20261002_091500_C``
    """
    now = datetime.now(timezone.utc)
    base = now.strftime("%Y%m%d_%H%M%S")
    if condition:
        return f"{base}_{condition}"
    return base
