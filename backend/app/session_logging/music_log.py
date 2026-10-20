"""Log JSONL rekomendasi lagu dan komentar penonton (data eksperimen latensi).

Ditulis ke ``{LOG_DIR}/{session_id}.music.jsonl``, terpisah dari log giliran ``{session_id}.jsonl``
supaya ``SessionLogger.read_logs`` tetap hanya membaca TurnLog. Komentar yang masuk saat tidak ada
sesi live dicatat ke sesi ``offair_YYYYMMDD``.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _offair_session() -> str:
    return "offair_" + datetime.now(timezone.utc).strftime("%Y%m%d")


class MusicEventLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self._log_dir = Path(log_dir)
        self._session_id = ""
        self._lock = threading.Lock()

    @property
    def session_id(self) -> str:
        return self._session_id or _offair_session()

    def set_session(self, session_id: str) -> None:
        self._session_id = session_id

    def end_session(self) -> None:
        self._session_id = ""

    def path(self) -> Path:
        return self._log_dir / f"{self.session_id}.music.jsonl"

    def log(self, event: str, **data: Any) -> None:
        """Tambah satu baris. Kegagalan menulis log tidak boleh mengganggu live."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "event": event,
            **data,
        }
        try:
            with self._lock:
                self._log_dir.mkdir(parents=True, exist_ok=True)
                with open(self.path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            logger.warning("Music event log failed: %s", exc)
