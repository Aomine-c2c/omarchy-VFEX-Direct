#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Omarchy Linux Notification Manager
----------------------------------------------------------------
Priority-aware, quiet-hours-aware, deduplicated desktop notifications via
native `notify-send` (libnotify / mako / swaync on Omarchy Linux).
Zero external dependencies.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PRIORITY_MAP = {
    "price_change": "normal",
    "market_hours": "low",
    "announcement": "normal",
    "dividend": "normal",
    "threshold_breach": "critical",
    "agent_complete": "low",
    "provider_failure": "normal",
    "order_status": "critical",
}


class DesktopNotifier:
    def __init__(
        self,
        dedup_path: Path | None = None,
        quiet_start_hour: int = 22,
        quiet_end_hour: int = 7,
        dedup_ttl_sec: int = 1800,
    ) -> None:
        self.dedup_path = dedup_path or (Path.home() / ".local" / "state" / "vfex" / "notify_dedup.json")
        self.quiet_start_hour = quiet_start_hour
        self.quiet_end_hour = quiet_end_hour
        self.dedup_ttl_sec = dedup_ttl_sec
        self._has_notify_send = shutil.which("notify-send") is not None

    def is_quiet_hours(self, now_hour: int | None = None) -> bool:
        h = datetime.now().hour if now_hour is None else int(now_hour)
        if self.quiet_start_hour > self.quiet_end_hour:
            return h >= self.quiet_start_hour or h < self.quiet_end_hour
        return self.quiet_start_hour <= h < self.quiet_end_hour

    def _load_dedup(self) -> dict[str, float]:
        if not self.dedup_path.exists():
            return {}
        try:
            data = json.loads(self.dedup_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_dedup(self, data: dict[str, float]) -> None:
        try:
            self.dedup_path.parent.mkdir(parents=True, exist_ok=True)
            self.dedup_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def send(
        self,
        category: str,
        title: str,
        body: str,
        priority: str | None = None,
        now_hour: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        prio = (priority or PRIORITY_MAP.get(category, "normal")).lower()
        if prio not in ("low", "normal", "critical"):
            prio = "normal"

        # Respect quiet hours for non-critical notifications
        if self.is_quiet_hours(now_hour) and prio != "critical":
            return {"sent": False, "reason": "quiet_hours", "priority": prio}

        # Deduplicate identical notifications within TTL
        fp = hashlib.sha1(f"{category}:{title}:{body}".encode("utf-8")).hexdigest()[:16]
        now_ts = time.time()
        cache = {k: v for k, v in self._load_dedup().items() if (now_ts - float(v)) < self.dedup_ttl_sec}
        if fp in cache:
            return {"sent": False, "reason": "duplicate", "priority": prio}

        cache[fp] = now_ts
        self._save_dedup(cache)

        if not dry_run and self._has_notify_send:
            try:
                subprocess.run(
                    ["notify-send", "-u", prio, "-a", "NOTHING Investment Terminal", title, body],
                    check=False,
                    timeout=3,
                )
            except Exception:
                pass
        return {"sent": True, "reason": "dispatched", "priority": prio, "category": category}
