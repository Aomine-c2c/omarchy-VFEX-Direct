#!/usr/bin/env python3
"""
Persistent Single-Page Workspace Layout Preferences (~/.config/vfex/layout_prefs.json).
Zero external dependencies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PREFS_PATH = Path.home() / ".config" / "vfex" / "layout_prefs.json"

DEFAULT_PREFS: dict[str, Any] = {
    "compact_mode": False,
    "right_dock_open": True,
    "right_dock_width": 230,
    "collapsed": {},
}


def load_prefs(path: Path = PREFS_PATH) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_PREFS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**DEFAULT_PREFS, **data}
    except Exception:
        pass
    return dict(DEFAULT_PREFS)


def save_prefs(updates: dict[str, Any], path: Path = PREFS_PATH) -> dict[str, Any]:
    cur = load_prefs(path)
    cur.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return cur


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "save" and len(args) >= 2:
        saved = save_prefs(json.loads(args[1]))
        print(json.dumps(saved))
    else:
        print(json.dumps(load_prefs()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
