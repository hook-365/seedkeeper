#!/usr/bin/env python3
"""
Usage Tracker - Records and analyzes LLM usage patterns.
Thread-safe JSON persistence with 90-day auto-pruning.

Note: With local Ollama models, there are no API costs.
Token tracking is maintained for monitoring usage patterns.
"""

import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


def _empty_bucket() -> Dict[str, Any]:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}


class UsageTracker:
    """Tracks LLM usage patterns with JSON persistence."""

    def __init__(self, data_dir: str = "data"):
        self._lock = threading.Lock()
        self._path = os.path.join(data_dir, "usage_stats.json")
        os.makedirs(data_dir, exist_ok=True)
        self._data = self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[UsageTracker] Error loading {self._path}: {e}")
        return self._default_data()

    def _save(self):
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self._path)
        except IOError as e:
            print(f"[UsageTracker] Error saving: {e}")

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        return {
            "lifetime": {
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,  # Always 0 for local models
                "first_tracked": None,
            },
            "daily": {},
            "models": {},
            "commands": {},
            "users": {},
        }

    # ── recording ────────────────────────────────────────────────

    def record_usage(
        self,
        model: str,
        command_type: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        is_local: bool = True,  # Default True - local models have no cost
    ):
        # Local models are free - no cost calculation needed
        cost = 0.0
        today = datetime.utcnow().strftime("%Y-%m-%d")

        with self._lock:
            d = self._data

            # lifetime
            lt = d["lifetime"]
            lt["total_calls"] += 1
            lt["total_input_tokens"] += input_tokens
            lt["total_output_tokens"] += output_tokens
            lt["total_cost"] += cost
            if lt["first_tracked"] is None:
                lt["first_tracked"] = today

            # daily
            day = d["daily"].setdefault(today, {
                **_empty_bucket(),
                "models": {},
                "commands": {},
            })
            day["calls"] += 1
            day["input_tokens"] += input_tokens
            day["output_tokens"] += output_tokens
            day["cost"] += cost

            # daily -> model
            dm = day["models"].setdefault(model, _empty_bucket())
            dm["calls"] += 1
            dm["input_tokens"] += input_tokens
            dm["output_tokens"] += output_tokens
            dm["cost"] += cost

            # daily -> command
            dc = day["commands"].setdefault(command_type, _empty_bucket())
            dc["calls"] += 1
            dc["input_tokens"] += input_tokens
            dc["output_tokens"] += output_tokens
            dc["cost"] += cost

            # all-time model
            am = d["models"].setdefault(model, _empty_bucket())
            am["calls"] += 1
            am["input_tokens"] += input_tokens
            am["output_tokens"] += output_tokens
            am["cost"] += cost

            # all-time command
            ac = d["commands"].setdefault(command_type, _empty_bucket())
            ac["calls"] += 1
            ac["input_tokens"] += input_tokens
            ac["output_tokens"] += output_tokens
            ac["cost"] += cost

            # per-user
            if user_id:
                au = d["users"].setdefault(str(user_id), _empty_bucket())
                au["calls"] += 1
                au["input_tokens"] += input_tokens
                au["output_tokens"] += output_tokens
                au["cost"] += cost

            # prune old daily entries
            self._prune_daily(d, 90)

            self._save()

    # ── pruning ──────────────────────────────────────────────────

    @staticmethod
    def _prune_daily(data: Dict, keep_days: int):
        cutoff = (datetime.utcnow() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        keys_to_remove = [k for k in data["daily"] if k < cutoff]
        for k in keys_to_remove:
            del data["daily"][k]

    # ── queries ──────────────────────────────────────────────────

    def get_today_summary(self) -> Dict[str, Any]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        with self._lock:
            day = self._data["daily"].get(today, _empty_bucket())
            return {
                "date": today,
                **day,
                "lifetime": dict(self._data["lifetime"]),
            }

    def get_daily_trend(self, days: int = 7) -> list:
        with self._lock:
            result = []
            for i in range(days - 1, -1, -1):
                date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
                day = self._data["daily"].get(date, _empty_bucket())
                result.append({"date": date, **day})
            return result

    def get_rolling_summary(self, days: int = 30) -> Dict[str, Any]:
        with self._lock:
            totals = _empty_bucket()
            cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            count = 0
            for date, day in self._data["daily"].items():
                if date >= cutoff:
                    totals["calls"] += day.get("calls", 0)
                    totals["input_tokens"] += day.get("input_tokens", 0)
                    totals["output_tokens"] += day.get("output_tokens", 0)
                    totals["cost"] += day.get("cost", 0.0)
                    count += 1
            totals["active_days"] = count
            totals["period_days"] = days
            return totals

    def get_model_breakdown(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data.get("models", {}))

    def get_command_breakdown(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data.get("commands", {}))

    def get_user_breakdown(self, top_n: int = 10) -> list:
        with self._lock:
            users = self._data.get("users", {})
            sorted_users = sorted(users.items(), key=lambda x: x[1].get("calls", 0), reverse=True)
            return sorted_users[:top_n]
