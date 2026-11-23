#!/usr/bin/env python3
"""
NOTHING Investment Terminal — Central Multi-Provider AI Gateway
---------------------------------------------------------------
Supports OpenAI, Anthropic, Google Gemini, DeepSeek, OpenRouter, and Ollama
simultaneously with:
- Multiple API keys per provider (stored in SecretStore, never in logs/UI/prompts)
- Model registry & explicit capability validation (tools, structured outputs, context)
- 8 task-based routing profiles + agent-specific model assignments
- Configurable fallback chains with retry & latency/performance tracking
- Daily, monthly, and per-provider spending budgets (never silently exceeded)
- Sanitized request audit logging (zero sensitive payloads).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from exchange_adapters import SecretStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini", "cost_per_1k_in": 0.00015, "cost_per_1k_out": 0.00060, "requires_key": True},
    "anthropic": {"name": "Anthropic", "base_url": "https://api.anthropic.com/v1", "default_model": "claude-3-5-sonnet-latest", "cost_per_1k_in": 0.003, "cost_per_1k_out": 0.015, "requires_key": True},
    "gemini": {"name": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta", "default_model": "gemini-2.5-flash", "cost_per_1k_in": 0.0001, "cost_per_1k_out": 0.0004, "requires_key": True},
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat", "cost_per_1k_in": 0.00014, "cost_per_1k_out": 0.00028, "requires_key": True},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "default_model": "openai/gpt-4o-mini", "cost_per_1k_in": 0.0002, "cost_per_1k_out": 0.0008, "requires_key": True},
    "ollama": {"name": "Ollama (Local)", "base_url": "http://127.0.0.1:11434", "default_model": "llama3.1:8b", "cost_per_1k_in": 0.0, "cost_per_1k_out": 0.0, "requires_key": False},
}

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "gpt-4o-mini": {"provider": "openai", "supports_tools": True, "supports_structured": True, "max_context": 128000, "reasoning": "standard"},
    "claude-3-5-sonnet-latest": {"provider": "anthropic", "supports_tools": True, "supports_structured": True, "max_context": 200000, "reasoning": "deep"},
    "gemini-2.5-flash": {"provider": "gemini", "supports_tools": True, "supports_structured": True, "max_context": 1000000, "reasoning": "standard"},
    "deepseek-chat": {"provider": "deepseek", "supports_tools": True, "supports_structured": True, "max_context": 64000, "reasoning": "standard"},
    "openai/gpt-4o-mini": {"provider": "openrouter", "supports_tools": True, "supports_structured": True, "max_context": 128000, "reasoning": "standard"},
    "llama3.1:8b": {"provider": "ollama", "supports_tools": True, "supports_structured": True, "max_context": 32000, "reasoning": "basic"},
    "tiny-local-no-tools": {"provider": "ollama", "supports_tools": False, "supports_structured": False, "max_context": 4096, "reasoning": "basic"},
}

ROUTING_PROFILES: dict[str, dict[str, Any]] = {
    "news_analysis": {"requires_tools": False, "requires_structured": True, "min_context": 8000},
    "company_research": {"requires_tools": False, "requires_structured": True, "min_context": 16000},
    "fundamental_analysis": {"requires_tools": False, "requires_structured": True, "min_context": 32000},
    "portfolio_analysis": {"requires_tools": False, "requires_structured": True, "min_context": 16000},
    "risk_analysis": {"requires_tools": False, "requires_structured": True, "min_context": 16000},
    "investment_strategy": {"requires_tools": False, "requires_structured": True, "min_context": 16000},
    "paper_trading_decisions": {"requires_tools": True, "requires_structured": True, "min_context": 8000},
    "document_processing": {"requires_tools": False, "requires_structured": True, "min_context": 32000},
}


class AIProviderManager:
    """Central multi-provider AI gateway with capability validation, budgets, and fallback."""

    def __init__(self, config_path: Path | None = None, secret_store: SecretStore | None = None) -> None:
        self.config_path = config_path or (Path.home() / ".config" / "vfex" / "ai_providers.json")
        self.secret_store = secret_store or SecretStore()
        self.state = self._load()

    def _default_state(self) -> dict[str, Any]:
        return {
            "daily_budget_usd": 2.0,
            "monthly_budget_usd": 10.0,
            "max_requests_per_day": 500,
            "fallback_order": ["ollama", "gemini", "openai", "anthropic", "deepseek", "openrouter"],
            "agent_models": {},
            "providers": {
                pid: {
                    "enabled": pid == "ollama",
                    "base_url": cfg["base_url"],
                    "model": cfg["default_model"],
                    "key_configured": not cfg["requires_key"],
                    "key_labels": [],
                    "provider_budget_usd": 5.0,
                    "spent_month_usd": 0.0,
                    "status": "UNKNOWN",
                    "last_checked": "",
                    "last_error": "",
                }
                for pid, cfg in SUPPORTED_PROVIDERS.items()
            },
            "model_perf": {},  # model -> {requests, failures, avg_latency_ms}
            "usage": {
                "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "month": datetime.now(timezone.utc).strftime("%Y-%m"),
                "daily_cost_usd": 0.0,
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "estimated_cost_usd": 0.0,
            },
            "task_audit": [],
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

    def register_api_key(self, provider_id: str, api_key: str, key_label: str = "primary") -> dict[str, Any]:
        pid = provider_id.strip().lower()
        if pid not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported AI provider: {pid}")
        if not api_key or len(api_key.strip()) < 6:
            raise ValueError("API key appears invalid.")
        storage_mode = self.secret_store.set_secret(f"ai_{pid}", key_label, api_key.strip())
        p = self.state["providers"][pid]
        p["key_configured"] = True
        p["enabled"] = True
        labels = list(p.get("key_labels") or [])
        if key_label not in labels:
            labels.append(key_label)
        p["key_labels"] = labels
        self.save()
        return {"provider": pid, "key_label": key_label, "key_configured": True, "storage": storage_mode}

    @staticmethod
    def validate_capabilities(model: str, task_type: str | None = None) -> tuple[bool, str]:
        if not task_type or task_type not in ROUTING_PROFILES:
            return True, "OK"
        req = ROUTING_PROFILES[task_type]
        caps = MODEL_REGISTRY.get(model)
        if not caps:
            return True, "Unregistered model (assumed compatible)"
        if req["requires_tools"] and not caps["supports_tools"]:
            return False, f"Model {model} does not support tools required by {task_type}."
        if req["requires_structured"] and not caps["supports_structured"]:
            return False, f"Model {model} does not support structured outputs required by {task_type}."
        if caps["max_context"] < req["min_context"]:
            return False, f"Model {model} context ({caps['max_context']}) < required ({req['min_context']})."
        return True, "OK"

    def assign_agent_model(self, agent_id: str, provider_id: str, model: str, task_type: str | None = None) -> None:
        pid = provider_id.strip().lower()
        if pid not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported AI provider: {pid}")
        ok, reason = self.validate_capabilities(model, task_type)
        if not ok:
            raise ValueError(reason)
        self.state.setdefault("agent_models", {})[agent_id] = {"provider": pid, "model": model}
        self.save()

    def check_budget(self, provider_id: str | None = None) -> tuple[bool, str]:
        u = self.state["usage"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cur_m = today[:7]
        if u.get("day") != today:
            u["day"] = today
            u["daily_cost_usd"] = 0.0
            u["requests"] = 0
        if u.get("month") != cur_m:
            u.update({"month": cur_m, "estimated_cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0})
            for p in self.state["providers"].values():
                p["spent_month_usd"] = 0.0

        daily_lim = float(self.state.get("daily_budget_usd") or 0.0)
        monthly_lim = float(self.state.get("monthly_budget_usd") or 0.0)
        if daily_lim > 0 and float(u.get("daily_cost_usd", 0.0)) >= daily_lim:
            return False, f"Daily AI budget (${daily_lim:.2f}) reached."
        if monthly_lim > 0 and float(u.get("estimated_cost_usd", 0.0)) >= monthly_lim:
            return False, f"Monthly AI budget (${monthly_lim:.2f}) reached."
        if int(u.get("requests", 0)) >= int(self.state.get("max_requests_per_day") or 500):
            return False, "Daily AI request limit reached."
        if provider_id and provider_id in self.state["providers"]:
            p = self.state["providers"][provider_id]
            p_lim = float(p.get("provider_budget_usd") or 0.0)
            if p_lim > 0 and float(p.get("spent_month_usd", 0.0)) >= p_lim:
                return False, f"Provider {provider_id} monthly budget (${p_lim:.2f}) reached."
        return True, "OK"

    def record_usage(self, agent_id: str, provider_id: str, model: str, tokens_in: int, tokens_out: int, latency_ms: float = 0.0, fallback_used: bool = False, task_type: str = "") -> float:
        cfg = SUPPORTED_PROVIDERS.get(provider_id, {})
        cost = (tokens_in / 1000.0) * float(cfg.get("cost_per_1k_in", 0.0)) + (tokens_out / 1000.0) * float(cfg.get("cost_per_1k_out", 0.0))
        u = self.state["usage"]
        u["requests"] = int(u.get("requests", 0)) + 1
        u["tokens_in"] = int(u.get("tokens_in", 0)) + int(tokens_in)
        u["tokens_out"] = int(u.get("tokens_out", 0)) + int(tokens_out)
        u["daily_cost_usd"] = round(float(u.get("daily_cost_usd", 0.0)) + cost, 6)
        u["estimated_cost_usd"] = round(float(u.get("estimated_cost_usd", 0.0)) + cost, 6)
        if provider_id in self.state["providers"]:
            self.state["providers"][provider_id]["spent_month_usd"] = round(float(self.state["providers"][provider_id].get("spent_month_usd", 0.0)) + cost, 6)

        mp = self.state.setdefault("model_perf", {}).setdefault(model, {"requests": 0, "failures": 0, "avg_latency_ms": 0.0})
        n = mp["requests"] + 1
        mp["avg_latency_ms"] = round(((mp["avg_latency_ms"] * mp["requests"]) + latency_ms) / n, 1)
        mp["requests"] = n

        self.state.setdefault("task_audit", []).append({
            "timestamp": _utc_now(),
            "agent_id": agent_id,
            "task_type": task_type,
            "provider": provider_id,
            "model": model,
            "fallback_used": fallback_used,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 6),
            "latency_ms": round(latency_ms, 1),
        })
        self.state["task_audit"] = self.state["task_audit"][-100:]
        self.save()
        return round(cost, 6)

    def invoke_with_fallback(
        self,
        agent_id: str,
        executors: dict[str, Callable[[str], tuple[str, int, int]]],
        task_type: str | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
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
            ok_pb, p_reason = self.check_budget(pid)
            if not ok_pb:
                errors.append(p_reason)
                continue
            p_cfg = self.state["providers"].get(pid) or {}
            model = assigned["model"] if (idx == 0 and assigned) else str(p_cfg.get("model") or SUPPORTED_PROVIDERS[pid]["default_model"])
            cap_ok, cap_msg = self.validate_capabilities(model, task_type)
            if not cap_ok:
                errors.append(cap_msg)
                continue
            for attempt in range(max_retries + 1):
                t0 = time.monotonic()
                try:
                    text, tin, tout = fn(model)
                    lat = (time.monotonic() - t0) * 1000.0
                    cost = self.record_usage(agent_id, pid, model, tin, tout, latency_ms=lat, fallback_used=(idx > 0), task_type=task_type or "")
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
                        "latency_ms": round(lat, 1),
                        "errors": errors,
                    }
                except Exception as exc:
                    mp = self.state.setdefault("model_perf", {}).setdefault(model, {"requests": 0, "failures": 0, "avg_latency_ms": 0.0})
                    mp["failures"] += 1
                    p_cfg["status"] = "ERROR"
                    p_cfg["last_error"] = str(exc)
                    errors.append(f"{pid} (try {attempt+1}): {exc}")

        self.save()
        raise RuntimeError(f"All AI providers failed: {'; '.join(errors)}")

    def status_summary(self) -> dict[str, Any]:
        return {
            "daily_budget_usd": self.state.get("daily_budget_usd", 2.0),
            "monthly_budget_usd": self.state.get("monthly_budget_usd", 10.0),
            "usage": self.state["usage"],
            "routing_profiles": list(ROUTING_PROFILES.keys()),
            "providers": [
                {
                    "id": pid,
                    "name": SUPPORTED_PROVIDERS[pid]["name"],
                    "enabled": bool(p.get("enabled")),
                    "model": str(p.get("model") or ""),
                    "key_configured": bool(p.get("key_configured")),
                    "key_count": len(p.get("key_labels") or []),
                    "status": str(p.get("status") or "UNKNOWN"),
                }
                for pid, p in self.state["providers"].items()
                if pid in SUPPORTED_PROVIDERS
            ],
            "recent_tasks": (self.state.get("task_audit") or [])[-10:],
        }
