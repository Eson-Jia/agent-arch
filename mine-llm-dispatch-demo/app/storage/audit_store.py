from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.models.audit import AuditEvent


class AuditStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def reset(self) -> None:
        with self._lock:
            self.path.write_text("", encoding="utf-8")

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def list_events(self, limit: int = 100) -> list[dict]:
        with self._lock:
            lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [json.loads(line) for line in lines[-limit:]]
