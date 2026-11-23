#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Exchange Adapter Architecture & Safe Trade Lifecycle
----------------------------------------------------------------------------------
Independent adapters for VFEX, C-TRADE, and ZSE with honest capability discovery,
multi-provider health & freshness management, idempotent trade workflow with
mandatory human confirmation, portal handoff tickets, and structured audit logging.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_audit_logger(log_path: Path | None = None) -> logging.Logger:
    p = log_path or (Path.home() / ".local" / "state" / "vfex" / "trade_audit.log")
    logger = logging.getLogger(f"vfex.trade_audit.{hashlib.sha1(str(p).encode()).hexdigest()[:8]}")
    if not logger.handlers:
        p.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(p, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ── Secure Secret Store (Linux Secret Service with 0600 atomic fallback) ─────

class SecretStore:
    """Stores credentials securely via `secret-tool` (libsecret) or atomic 0600 file."""

    def __init__(self, fallback_path: Path | None = None) -> None:
        self.fallback_path = fallback_path or (Path.home() / ".config" / "vfex" / ".secrets.json")
        self._has_secret_tool = shutil.which("secret-tool") is not None

    def set_secret(self, provider: str, account: str, secret: str) -> str:
        if self._has_secret_tool:
            try:
                proc = subprocess.run(
                    ["secret-tool", "store", "--label", f"VFEX Terminal ({provider})", "app", "vfex-terminal", "provider", provider, "account", account],
                    input=secret.encode("utf-8"),
                    capture_output=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    return "secret-service"
            except Exception:
                pass
        # Atomic 0600 fallback (no TOCTOU chmod race)
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._read_fallback()
        data[f"{provider}:{account}"] = secret
        fd, tmp = tempfile.mkstemp(dir=str(self.fallback_path.parent), prefix=".sec.")
        try:
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.fallback_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return "atomic-0600"

    def _read_fallback(self) -> dict[str, str]:
        if not self.fallback_path.exists():
            return {}
        try:
            parsed = json.loads(self.fallback_path.read_text(encoding="utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


# ── Exchange Adapter Architecture ────────────────────────────────────────────

@dataclass(frozen=True)
class ExchangeCapabilities:
    exchange_id: str
    display_name: str
    native_currency: str
    portal_url: str
    market_data: bool = True
    security_discovery: bool = True
    price_history: bool = False
    order_book: bool = False
    account_balances: bool = False
    holdings: bool = False
    transaction_history: bool = False
    order_submission: bool = False
    order_status: bool = False
    order_cancellation: bool = False


class BaseExchangeAdapter:
    capabilities: ExchangeCapabilities

    def fetch_market_data(self) -> dict[str, Any]:
        raise NotImplementedError

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if not self.capabilities.order_submission:
            return {
                "status": "PORTAL_HANDOFF",
                "executed": False,
                "portal_url": self.capabilities.portal_url,
                "message": f"{self.capabilities.display_name} does not expose an official automated order execution API. Use the prepared trade ticket on {self.capabilities.portal_url}.",
                "ticket": order,
            }
        raise NotImplementedError


class VFEXDirectAdapter(BaseExchangeAdapter):
    capabilities = ExchangeCapabilities(
        exchange_id="VFEX",
        display_name="VFEX Direct",
        native_currency="USD",
        portal_url="https://vfexdirect.co.zw",
        market_data=True,
        security_discovery=True,
        price_history=False,
        order_book=False,
        account_balances=True,
        holdings=True,
        transaction_history=True,
        order_submission=False,
        order_status=True,
        order_cancellation=False,
    )


class CTradeAdapter(BaseExchangeAdapter):
    capabilities = ExchangeCapabilities(
        exchange_id="CTRADE",
        display_name="C-TRADE",
        native_currency="USD",
        portal_url="https://ctradenew.ctrade.co.zw",
        market_data=True,
        security_discovery=True,
        price_history=False,
        order_book=True,
        account_balances=True,
        holdings=True,
        transaction_history=False,
        order_submission=False,
        order_status=False,
        order_cancellation=False,
    )


class ZSEDirectAdapter(BaseExchangeAdapter):
    capabilities = ExchangeCapabilities(
        exchange_id="ZSE",
        display_name="ZSE Direct",
        native_currency="ZWG",
        portal_url="https://zsedirect.co.zw",
        market_data=True,
        security_discovery=True,
        price_history=False,
        order_book=False,
        account_balances=True,
        holdings=True,
        transaction_history=True,
        order_submission=False,
        order_status=True,
        order_cancellation=False,
    )


# ── Data Provider Health, Priority, Retry & Freshness Manager ────────────────

@dataclass
class ProviderHealth:
    provider_id: str
    status: str = "UNKNOWN"  # HEALTHY | DEGRADED | OFFLINE | UNKNOWN
    last_success_at: str = ""
    last_error: str = ""
    consecutive_failures: int = 0
    latency_ms: float = 0.0


class DataProviderManager:
    """
    Manages prioritized market data providers with retries, health tracking,
    and strict freshness labeling (NEVER labels stale fallback data as LIVE).
    """

    def __init__(self, priorities: dict[str, list[str]] | None = None, max_retries: int = 2) -> None:
        self.priorities = priorities or {
            "VFEX": ["VFEX", "CTRADE"],
            "ZSE": ["ZSE", "CTRADE"],
            "CTRADE": ["CTRADE", "VFEX"],
        }
        self.max_retries = max_retries
        self.health: dict[str, ProviderHealth] = {}

    def fetch_with_fallback(
        self,
        market: str,
        fetchers: dict[str, Callable[[], Any]],
        cached_fallback: Any = None,
        cached_at: str = "",
    ) -> dict[str, Any]:
        order = self.priorities.get(market.upper(), list(fetchers.keys()))
        errors: list[str] = []

        for pid in order:
            fn = fetchers.get(pid)
            if fn is None:
                continue
            ph = self.health.setdefault(pid, ProviderHealth(provider_id=pid))
            for attempt in range(self.max_retries + 1):
                t0 = time.monotonic()
                try:
                    data = fn()
                    ph.status = "HEALTHY"
                    ph.last_success_at = _utc_now()
                    ph.last_error = ""
                    ph.consecutive_failures = 0
                    ph.latency_ms = round((time.monotonic() - t0) * 1000.0, 1)
                    return {
                        "ok": True,
                        "provider": pid,
                        "freshness": "LIVE",
                        "fetched_at": ph.last_success_at,
                        "data": data,
                        "errors": errors,
                    }
                except Exception as exc:
                    ph.consecutive_failures += 1
                    ph.last_error = str(exc)
                    ph.status = "DEGRADED" if ph.consecutive_failures < 3 else "OFFLINE"
                    errors.append(f"{pid} (try {attempt + 1}): {exc}")

        # All live providers failed -> return cached data ONLY with explicit STALE label
        return {
            "ok": cached_fallback is not None,
            "provider": "LOCAL_CACHE",
            "freshness": "STALE",
            "fetched_at": cached_at,
            "data": cached_fallback,
            "errors": errors,
        }


# ── Safe Trade Lifecycle Manager ─────────────────────────────────────────────

VALID_ORDER_STATES = {
    "PREVIEW",
    "PENDING",
    "PARTIALLY_FILLED",
    "EXECUTED",
    "CANCELLED",
    "REJECTED",
    "FAILED",
    "PORTAL_HANDOFF",
}


class TradeWorkflowManager:
    """
    Enforces the 14-step safe trade lifecycle:
    - Validates parameters, balances, and holdings
    - Estimates statutory fees
    - Generates an idempotency key to prevent duplicate submissions
    - Requires explicit `confirmed_by_user=True` (never executes autonomously)
    - Never reports an order as EXECUTED until confirmed by the provider
    - Logs all financial actions to audit log without credentials
    """

    def __init__(self, log_path: Path | None = None) -> None:
        self.adapters: dict[str, BaseExchangeAdapter] = {
            "VFEX": VFEXDirectAdapter(),
            "CTRADE": CTradeAdapter(),
            "ZSE": ZSEDirectAdapter(),
        }
        self.orders: dict[str, dict[str, Any]] = {}
        self.idempotency_keys: set[str] = set()
        self.logger = _get_audit_logger(log_path)

    def preview_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        available_cash: float,
        held_shares: float = 0.0,
    ) -> dict[str, Any]:
        ex = exchange.strip().upper()
        if ex not in self.adapters:
            raise ValueError(f"Unknown exchange: {ex}")
        act = side.strip().upper()
        if act not in ("BUY", "SELL"):
            raise ValueError("Side must be BUY or SELL.")
        if quantity <= 0 or price <= 0:
            raise ValueError("Quantity and price must be strictly positive.")

        adapter = self.adapters[ex]
        cur = adapter.capabilities.native_currency
        gross = round(quantity * price, 4)
        fee_rate = 0.0218 if cur == "ZWG" else 0.0104
        cgt = round(gross * 0.01, 2) if (cur == "ZWG" and act == "SELL") else 0.0
        est_fees = round(gross * fee_rate + cgt, 2)
        net_total = round(gross + est_fees, 2) if act == "BUY" else round(max(0.0, gross - est_fees), 2)

        errors: list[str] = []
        if act == "BUY" and available_cash < net_total:
            errors.append(f"Insufficient {cur} cash: need {net_total:.2f}, available {available_cash:.2f}.")
        if act == "SELL" and held_shares < quantity:
            errors.append(f"Insufficient {symbol} shares: need {quantity}, held {held_shares}.")

        idem_raw = f"{ex}:{symbol.upper()}:{act}:{quantity}:{price}:{uuid.uuid4().hex[:8]}"
        idem_key = hashlib.sha256(idem_raw.encode("utf-8")).hexdigest()[:16]

        return {
            "order_id": uuid.uuid4().hex[:12],
            "idempotency_key": idem_key,
            "exchange": ex,
            "symbol": symbol.strip().upper(),
            "side": act,
            "quantity": float(quantity),
            "price": float(price),
            "currency": cur,
            "estimated_gross": gross,
            "estimated_fees": est_fees,
            "estimated_net": net_total,
            "valid": len(errors) == 0,
            "validation_errors": errors,
            "direct_execution_supported": adapter.capabilities.order_submission,
            "portal_url": adapter.capabilities.portal_url,
            "status": "PREVIEW",
            "created_at": _utc_now(),
        }

    def submit_order(self, preview: dict[str, Any], confirmed_by_user: bool = False) -> dict[str, Any]:
        if not confirmed_by_user:
            raise PermissionError("Explicit user confirmation (`confirmed_by_user=True`) is required before submitting any order.")
        if not preview.get("valid"):
            raise ValueError(f"Cannot submit invalid order: {preview.get('validation_errors')}")

        idem = str(preview.get("idempotency_key") or "")
        if idem in self.idempotency_keys:
            raise ValueError(f"Duplicate order submission blocked (idempotency_key={idem}).")

        adapter = self.adapters[preview["exchange"]]
        self.idempotency_keys.add(idem)
        resp = adapter.submit_order(preview)

        record = {
            **preview,
            "status": resp.get("status", "FAILED"),
            "executed": False,  # Never marked executed until provider confirms
            "provider_response": resp,
            "submitted_at": _utc_now(),
        }
        self.orders[record["order_id"]] = record
        self.logger.info(
            "ORDER_SUBMITTED id=%s ex=%s sym=%s side=%s qty=%s px=%s status=%s idem=%s",
            record["order_id"], record["exchange"], record["symbol"], record["side"],
            record["quantity"], record["price"], record["status"], idem,
        )
        return record
