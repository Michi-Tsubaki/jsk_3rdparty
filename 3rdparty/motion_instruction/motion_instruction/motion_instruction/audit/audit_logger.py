from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, base_dir: Path | None = None, enabled: bool = True) -> None:
        self.base_dir = base_dir or Path.home() / ".ros" / "motion_instruction" / "audit"
        self.enabled = enabled

    def write(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.base_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        record = {"timestamp": now.isoformat(), **event}
        path = self.base_dir / f"{now.date().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
