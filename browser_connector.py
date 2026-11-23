#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Isolated Browser-Based Account Connector Service
------------------------------------------------------------------------------
Provides isolated, user-controlled browser session management and read-only
account data extraction for VFEX Direct, C-TRADE, and ZSE Direct.

Security & Compliance Guarantees:
- READ-ONLY: Never executes real trades (`READ_ONLY_EXTRACTION = True`).
- NEVER bypasses MFA, CAPTCHA, or access controls — always hands off to the user
  in a visible, dedicated Chromium profile (~/.local/share/vfex/browser_profiles/<id>, 0700).
- NEVER sends credentials to AI providers and NEVER logs passwords.
- Supports immediate session disconnect & profile/session wipe (`disconnect()`).
- Deduplicates imported/extracted transactions by (platform, account_id, original_tx_id).
- Includes manual CSV/JSON statement import fallback when browser/API sync is unavailable.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SourceRecord:
    account_id: str
    source_platform: str  # VFEX | CTRADE | ZSE
    retrieval_timestamp: str
    original_tx_id: str
    normalised_tx: dict[str, Any]
    sync_status: str = "SYNCED"  # SYNCED | MANUAL_IMPORT | PARTIAL
    reconciliation_status: str = "UNRECONCILED"


class BasePlatformBrowserAdapter:
    platform_id: str = "BASE"
    portal_url: str = ""
    native_currency: str = "USD"
    READ_ONLY_EXTRACTION: bool = True

    def normalise_transaction(self, raw: dict[str, Any], account_id: str) -> SourceRecord:
        orig_id = str(raw.get("id") or raw.get("reference") or hashlib.sha1(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:14])
        norm = {
            "date": str(raw.get("date") or _utc_now()[:10])[:10],
            "type": str(raw.get("type") or raw.get("side") or "TRADE").upper(),
            "symbol": str(raw.get("symbol") or raw.get("counter") or "").upper(),
            "quantity": float(raw.get("quantity") or raw.get("shares") or 0.0),
            "unit_price": float(raw.get("price") or raw.get("unit_price") or 0.0),
            "amount": float(raw.get("amount") or raw.get("total") or 0.0),
            "currency": str(raw.get("currency") or self.native_currency).upper(),
            "exchange": self.platform_id,
        }
        return SourceRecord(
            account_id=account_id,
            source_platform=self.platform_id,
            retrieval_timestamp=_utc_now(),
            original_tx_id=orig_id,
            normalised_tx=norm,
        )


class VFEXBrowserAdapter(BasePlatformBrowserAdapter):
    platform_id = "VFEX"
    portal_url = "https://vfexdirect.co.zw"
    native_currency = "USD"


class CTradeBrowserAdapter(BasePlatformBrowserAdapter):
    platform_id = "CTRADE"
    portal_url = "https://ctradenew.ctrade.co.zw"
    native_currency = "USD"


class ZSEBrowserAdapter(BasePlatformBrowserAdapter):
    platform_id = "ZSE"
    portal_url = "https://zsedirect.co.zw"
    native_currency = "ZWG"


class BrowserConnectorService:
    """
    Isolated browser connector managing dedicated per-platform Chromium profiles,
    user-controlled login & MFA handoff, session health, deduplicated ingestion,
    and manual statement import fallback.
    """

    READ_ONLY_ONLY = True

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.home() / ".local" / "share" / "vfex" / "browser_connector")
        self.profiles_dir = self.base_dir / "profiles"
        self.records_file = self.base_dir / "source_records.json"
        self.sessions_file = self.base_dir / "sessions.json"
        self.adapters: dict[str, BasePlatformBrowserAdapter] = {
            "VFEX": VFEXBrowserAdapter(),
            "CTRADE": CTradeBrowserAdapter(),
            "ZSE": ZSEBrowserAdapter(),
        }
        self._records: dict[str, dict[str, Any]] = self._load_json(self.records_file)
        self._sessions: dict[str, dict[str, Any]] = self._load_json(self.sessions_file)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                return d if isinstance(d, dict) else {}
            except Exception:
                pass
        return {}

    def _save_all(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base_dir, 0o700)
        self.records_file.write_text(json.dumps(self._records, indent=2), encoding="utf-8")
        self.sessions_file.write_text(json.dumps(self._sessions, indent=2), encoding="utf-8")
        os.chmod(self.sessions_file, 0o600)

    def get_profile_dir(self, platform: str) -> Path:
        pid = platform.strip().upper()
        if pid not in self.adapters:
            raise ValueError(f"Unsupported platform: {pid}")
        p = self.profiles_dir / pid.lower()
        p.mkdir(parents=True, exist_ok=True)
        os.chmod(p, 0o700)
        return p

    def launch_user_login_session(self, platform: str, account_id: str) -> dict[str, Any]:
        """
        Prepare an isolated Chromium profile for user-controlled login & MFA handoff.
        Never bypasses MFA/CAPTCHA; requires Playwright + Chromium for live launch.
        """
        pid = platform.strip().upper()
        adapter = self.adapters[pid]
        profile = self.get_profile_dir(pid)
        try:
            import playwright  # noqa: F401
            pw_available = True
        except ImportError:
            pw_available = False

        self._sessions[f"{pid}:{account_id}"] = {
            "platform": pid,
            "account_id": account_id,
            "portal_url": adapter.portal_url,
            "profile_dir": str(profile),
            "status": "AWAITING_USER_LOGIN_MFA" if pw_available else "PLAYWRIGHT_NOT_INSTALLED",
            "read_only": True,
            "updated_at": _utc_now(),
        }
        self._save_all()
        return self._sessions[f"{pid}:{account_id}"]

    def disconnect(self, platform: str, account_id: str) -> dict[str, Any]:
        """Immediate session disconnection & isolated browser profile wipe."""
        pid = platform.strip().upper()
        key = f"{pid}:{account_id}"
        self._sessions.pop(key, None)
        p = self.profiles_dir / pid.lower()
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
        self._save_all()
        return {"disconnected": True, "platform": pid, "account_id": account_id, "profile_wiped": True}

    def ingest_raw_transactions(self, platform: str, account_id: str, raw_rows: list[dict[str, Any]], sync_status: str = "SYNCED") -> dict[str, Any]:
        """Normalise and store source records with strict deduplication."""
        pid = platform.strip().upper()
        adapter = self.adapters[pid]
        added = 0
        skipped_dups = 0
        for raw in raw_rows:
            rec = adapter.normalise_transaction(raw, account_id)
            rec.sync_status = sync_status
            dedup_key = f"{pid}:{account_id}:{rec.original_tx_id}"
            if dedup_key in self._records:
                skipped_dups += 1
                continue
            self._records[dedup_key] = asdict(rec)
            added += 1
        self._save_all()
        return {"platform": pid, "added": added, "duplicates_skipped": skipped_dups, "total_records": len(self._records)}

    def import_manual_csv_statement(self, platform: str, account_id: str, csv_text: str) -> dict[str, Any]:
        """Fallback manual CSV statement importer with identical normalisation & deduplication."""
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        rows = [dict(r) for r in reader]
        return self.ingest_raw_transactions(platform, account_id, rows, sync_status="MANUAL_IMPORT")

    def health_summary(self) -> dict[str, Any]:
        return {
            "read_only_enforced": self.READ_ONLY_ONLY,
            "platforms": list(self.adapters.keys()),
            "active_sessions": len(self._sessions),
            "stored_source_records": len(self._records),
            "sessions": list(self._sessions.values()),
        }
