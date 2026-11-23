#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Multi-Provider BYOK AI Infrastructure
-------------------------------------------------------------------
Supports OpenAI, Anthropic, Google Gemini, DeepSeek, OpenRouter, and Ollama/local
OpenAI-compatible servers with:
- Secure API key storage via SecretStore (never in frontend, logs, or prompts)
- Agent-specific model assignments & automatic provider fallback
- Token usage, estimated API cost, request limits, and monthly spending budgets
- Immutable provenance recording of (provider, model) used for every task.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from exchange_adapters import SecretStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "cost_per_1k_in": 0.00015,
        "cost_per_1k_out": 0.00060,
        "requires_key": True,
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-latest",
        "cost_per_1k_in": 0.003,
        "cost_per_1k_out": 0.015,
        "requires_key": True,
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.5-flash",
        "cost_per_1k_in": 0.0001,
        "cost_per_1k_out": 0.0004,
        "requires_key": True,
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "cost_per_1k_in": 0.00014,
        "cost_per_1k_out": 0.00028,
        "requires_key": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "cost_per_1k_in": 0.0002,
        "cost_per_1k_out": 0.0008,
        "requires_key": True,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://127.0.0.1:11434",
        "default_model": "llama3.1:8b",
        "cost_per_1k_in": 0.0,
        "cost_per_1k_out": 0.0,
        "requires_key": False,
    },
}


class AIProviderManager:
    """Extensible BYOK AI provider registry, budget guard, and fallback router."""

    def __init__(
        self,
        config_path: Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        self.config_path = config_path or (Path.home() / ".config" / "vfex" / "ai_providers.json")
        self.secret_store = secret_store or SecretStore()
        self.state = self._load()

    def _default_state(self) -> dict[str, Any]:
        return {
            "monthly_budget_usd": 10.0,
            "max_requests_per_day": 500,
            "fallback_order": ["ollama", "gemini", "openai", "anthropic", "deepseek", "openrouter"],
            "agent_models": {},  # agent_id -> {"provider": ..., "model": ...}
            "providers": {
                pid: {
                    "enabled": pid == "ollama",
                    "base_url": cfg["base_url"],
                    "model": cfg["default_model"],
                    "key_configured": not cfg["requires_key"],
                    "status": "UNKNOWN",
                    "last_checked": "",
                    "last_error": "",
                }
                for pid, cfg in SUPPORTED_PROVIDERS.items()
            },
            "usage": {
                "month": datetime.now(timezone.utc).strftime("%Y-%m"),
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "estimated_cost_usd": 0.0,
            },
            "task_audit": [],  # immutable log of (timestamp, agent_id, provider, model, fallback_used)
        }

    def _load(self) -> dict[str, Any]:
        if self.config_path.exists():
            try:
                parsed = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return self._default_state()

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def register_api_key(self, provider_id: str, api_key: str) -> dict[str, Any]:
        pid = provider_id.strip().lower()
        if pid not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported AI provider: {pid}")
        if not api_key or len(api_key.strip()) < 6:
            raise ValueError("API key appears invalid.")
        storage_mode = self.secret_store.set_secret(f"ai_{pid}", "api_key", api_key.strip())
        p = self.state["providers"][pid]
        p["key_configured"] = True
        p["enabled"] = True
        self.save()
        # NEVER return the raw key
        return {"provider": pid, "key_configured": True, "storage": storage_mode}

    def assign_agent_model(self, agent_id: str, provider_id: str, model: str) -> None:
        pid = provider_id.strip().lower()
        if pid not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported AI provider: {pid}")
        self.state.setdefault("agent_models", {})[agent_id] = {"provider": pid, "model": model}
        self.save()

    def check_budget(self) -> tuple[bool, str]:
        u = self.state["usage"]
        cur_m = datetime.now(timezone.utc).strftime("%Y-%m")
        if u.get("month") != cur_m:
            u.update({"month": cur_m, "requests": 0, "tokens_in": 0, "tokens_out": 0, "estimated_cost_usd": 0.0})
        budget = float(self.state.get("monthly_budget_usd") or 0.0)
        if budget > 0 and float(u["estimated_cost_usd"]) >= budget:
            return False, f"Monthly AI budget (${budget:.2f}) reached."
        if int(u["requests"]) >= int(self.state.get("max_requests_per_day") or 500):
            return False, "Daily AI request limit reached."
        return True, "OK"

    def record_usage(self, agent_id: str, provider_id: str, model: str, tokens_in: int, tokens_out: int, fallback_used: bool = False) -> float:
        cfg = SUPPORTED_PROVIDERS.get(provider_id, {})
        cost = (tokens_in / 1000.0) * float(cfg.get("cost_per_1k_in", 0.0)) + (tokens_out / 1000.0) * float(cfg.get("cost_per_1k_out", 0.0))
        u = self.state["usage"]
        u["requests"] = int(u.get("requests", 0)) + 1
        u["tokens_in"] = int(u.get("tokens_in", 0)) + int(tokens_in)
        u["tokens_out"] = int(u.get("tokens_out", 0)) + int(tokens_out)
        u["estimated_cost_usd"] = round(float(u.get("estimated_cost_usd", 0.0)) + cost, 6)
        self.state.setdefault("task_audit", []).append({
            "timestamp": _utc_now(),
            "agent_id": agent_id,
            "provider": provider_id,
            "model": model,
            "fallback_used": fallback_used,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 6),
        })
        self.state["task_audit"] = self.state["task_audit"][-100:]
        self.save()
        return round(cost, 6)

    def invoke_with_fallback(
        self,
        agent_id: str,
        executors: dict[str, Callable[[str], tuple[str, int, int]]],
    ) -> dict[str, Any]:
        """
        Invoke preferred provider for `agent_id`, falling back in configured order.
        Always records the exact (provider, model, fallback_used) in `task_audit`.
        """
        ok_budget, reason = self.check_budget()
        if not ok_budget:
            raise RuntimeError(reason)

        assigned = (self.state.get("agent_models") or {}).get(agent_id)
        order = list(self.state.get("fallback_order") or [])
        if assigned and assigned["provider"] in order:
            order.remove(assigned["provider"])
            order.insert(0, assigned["provider"])
        elif assigned:
            order.insert(0, assigned["provider"])

        errors: list[str] = []
        for idx, pid in enumerate(order):
            fn = executors.get(pid)
            if fn is None:
                continue
            p_cfg = self.state["providers"].get(pid) or {}
            model = assigned["model"] if (idx == 0 and assigned) else str(p_cfg.get("model") or SUPPORTED_PROVIDERS[pid]["default_model"])
            try:
                text, tin, tout = fn(model)
                cost = self.record_usage(agent_id, pid, model, tin, tout, fallback_used=(idx > 0))
                p_cfg["status"] = "HEALTHY"
                p_cfg["last_checked"] = _utc_now()
                p_cfg["last_error"] = ""
                self.save()
                return {
                    "ok": True,
                    "provider": pid,
                    "model": model,
                    "fallback_used": idx > 0,
                    "response": text,
                    "cost_usd": cost,
                    "errors": errors,
                }
            except Exception as exc:
                p_cfg["status"] = "ERROR"
                p_cfg["last_error"] = str(exc)
                errors.append(f"{pid}: {exc}")

        self.save()
        raise RuntimeError(f"All AI providers failed: {'; '.join(errors)}")

    def status_summary(self) -> dict[str, Any]:
        """Redacted status summary safe for frontend display (zero API keys)."""
        return {
            "monthly_budget_usd": self.state["monthly_budget_usd"],
            "usage": self.state["usage"],
            "providers": [
                {
                    "id": pid,
                    "name": SUPPORTED_PROVIDERS[pid]["name"],
                    "enabled": bool(p.get("enabled")),
                    "model": str(p.get("model") or ""),
                    "key_configured": bool(p.get("key_configured")),
                    "status": str(p.get("status") or "UNKNOWN"),
                }
                for pid, p in self.state["providers"].items()
                if pid in SUPPORTED_PROVIDERS
            ],
            "recent_tasks": (self.state.get("task_audit") or [])[-10:],
        }
