#!/usr/bin/env python3
"""
Activity Tracker - Comprehensive activity insights for Seedkeeper.
Privacy-preserving: tracks counts only, no message content.
Thread-safe JSON persistence with 90-day retention.
"""

import json
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set


class ActivityTracker:
    """Tracks bot activity patterns with hourly granularity."""

    def __init__(self, data_dir: str = "data"):
        self._lock = threading.Lock()
        self._path = os.path.join(data_dir, "activity_stats.json")
        os.makedirs(data_dir, exist_ok=True)
        self._data = self._load()

        # In-memory response time tracking (not persisted)
        self._response_times: List[float] = []
        self._response_times_max = 100  # Keep last 100

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    data = json.load(f)
                    # Migration: ensure all expected fields exist
                    return self._migrate(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[ActivityTracker] Error loading {self._path}: {e}")
        return self._default_data()

    def _save(self):
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self._path)
        except IOError as e:
            print(f"[ActivityTracker] Error saving: {e}")

    def _migrate(self, data: Dict) -> Dict:
        """Ensure data has all required fields."""
        default = self._default_data()
        for key in default:
            if key not in data:
                data[key] = default[key]
        return data

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        return {
            "lifetime": {
                "total_messages": 0,
                "total_commands": 0,
                "total_dms": 0,
                "total_mentions": 0,
                "total_responses": 0,
                "first_tracked": None,
            },
            "daily": {},  # date -> daily stats
            "hourly_distribution": {str(h): 0 for h in range(24)},  # All-time hourly pattern
        }

    # ── Recording ────────────────────────────────────────────────────

    def record_message(
        self,
        user_id: str,
        is_dm: bool = False,
        is_mention: bool = False,
        is_command: bool = False,
        command_name: Optional[str] = None,
        guild_id: Optional[str] = None,
    ):
        """Record a message event (privacy-preserving: no content stored)."""
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")
        hour = str(now.hour)

        with self._lock:
            d = self._data

            # Lifetime stats
            lt = d["lifetime"]
            lt["total_messages"] += 1
            if is_dm:
                lt["total_dms"] += 1
            if is_mention:
                lt["total_mentions"] += 1
            if is_command:
                lt["total_commands"] += 1
            if lt["first_tracked"] is None:
                lt["first_tracked"] = today

            # Hourly distribution (all-time pattern)
            d["hourly_distribution"][hour] = d["hourly_distribution"].get(hour, 0) + 1

            # Daily stats
            day = d["daily"].setdefault(today, self._empty_day())
            day["messages"] += 1
            day["unique_users"].append(user_id) if user_id not in day["unique_users"] else None

            if is_dm:
                day["dms"] += 1
            if is_mention:
                day["mentions"] += 1
            if is_command:
                day["commands"] += 1
                if command_name:
                    day["command_counts"][command_name] = day["command_counts"].get(command_name, 0) + 1

            # Hourly breakdown for today
            day["hourly"][hour] = day["hourly"].get(hour, 0) + 1

            # Guild activity
            if guild_id:
                day["guilds"].append(guild_id) if guild_id not in day["guilds"] else None

            # Prune old data
            self._prune_daily(d, 90)
            self._save()

    def record_response(self, response_time_ms: float):
        """Record a bot response and its latency."""
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")

        with self._lock:
            self._data["lifetime"]["total_responses"] += 1

            day = self._data["daily"].setdefault(today, self._empty_day())
            day["responses"] += 1
            day["response_times"].append(response_time_ms)

            # Keep only last 50 response times per day
            if len(day["response_times"]) > 50:
                day["response_times"] = day["response_times"][-50:]

            self._save()

        # In-memory for quick avg calculation
        self._response_times.append(response_time_ms)
        if len(self._response_times) > self._response_times_max:
            self._response_times = self._response_times[-self._response_times_max:]

    @staticmethod
    def _empty_day() -> Dict[str, Any]:
        return {
            "messages": 0,
            "commands": 0,
            "dms": 0,
            "mentions": 0,
            "responses": 0,
            "unique_users": [],  # List of user IDs (for counting)
            "guilds": [],  # List of guild IDs seen
            "hourly": {},  # hour -> count
            "command_counts": {},  # command -> count
            "response_times": [],  # List of response times in ms
        }

    @staticmethod
    def _prune_daily(data: Dict, keep_days: int):
        cutoff = (datetime.utcnow() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        keys_to_remove = [k for k in data["daily"] if k < cutoff]
        for k in keys_to_remove:
            del data["daily"][k]

    # ── Queries ──────────────────────────────────────────────────────

    def get_24h_summary(self) -> Dict[str, Any]:
        """Get activity summary for the last 24 hours."""
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        with self._lock:
            today_data = self._data["daily"].get(today, self._empty_day())
            yesterday_data = self._data["daily"].get(yesterday, self._empty_day())

            # Combine last 24h (simplified: today + partial yesterday based on hour)
            current_hour = now.hour

            messages = today_data["messages"]
            unique_users = set(today_data["unique_users"])
            commands = today_data["commands"]
            dms = today_data["dms"]
            mentions = today_data["mentions"]

            # Add yesterday's hours after current hour
            for h in range(current_hour, 24):
                messages += yesterday_data["hourly"].get(str(h), 0)
            unique_users.update(yesterday_data["unique_users"])

            return {
                "messages": messages,
                "unique_users": len(unique_users),
                "commands": commands,
                "dms": dms,
                "mentions": mentions,
                "period": "24h",
            }

    def get_today_detailed(self) -> Dict[str, Any]:
        """Get detailed stats for today."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        with self._lock:
            day = self._data["daily"].get(today, self._empty_day())

            # Calculate average response time
            avg_response = 0
            if day["response_times"]:
                avg_response = sum(day["response_times"]) / len(day["response_times"])

            return {
                "date": today,
                "messages": day["messages"],
                "unique_users": len(day["unique_users"]),
                "commands": day["commands"],
                "dms": day["dms"],
                "mentions": day["mentions"],
                "responses": day["responses"],
                "avg_response_ms": round(avg_response, 1),
                "hourly": dict(day["hourly"]),
                "top_commands": self._top_n(day["command_counts"], 5),
            }

    def get_peak_hours(self) -> Dict[str, Any]:
        """Get peak activity hours (all-time pattern)."""
        with self._lock:
            hourly = self._data["hourly_distribution"]

            if not any(hourly.values()):
                return {"peak_hour": None, "quiet_hour": None, "distribution": hourly}

            sorted_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)
            peak = sorted_hours[0]
            quiet = sorted_hours[-1] if sorted_hours[-1][1] > 0 else None

            # Find quiet hour (lowest non-zero, or lowest)
            for h, c in reversed(sorted_hours):
                if c > 0:
                    quiet = (h, c)
                    break
            if quiet is None:
                quiet = sorted_hours[-1]

            return {
                "peak_hour": int(peak[0]),
                "peak_count": peak[1],
                "quiet_hour": int(quiet[0]),
                "quiet_count": quiet[1],
                "distribution": {int(k): v for k, v in hourly.items()},
            }

    def get_weekly_trend(self) -> List[Dict[str, Any]]:
        """Get daily stats for the last 7 days."""
        with self._lock:
            result = []
            for i in range(6, -1, -1):
                date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
                day = self._data["daily"].get(date, self._empty_day())
                result.append({
                    "date": date,
                    "messages": day["messages"],
                    "unique_users": len(day["unique_users"]),
                    "commands": day["commands"],
                })
            return result

    def get_sparkline(self, days: int = 7) -> str:
        """Generate a text sparkline of message activity."""
        bars = "▁▂▃▄▅▆▇█"
        trend = self.get_weekly_trend()
        values = [d["messages"] for d in trend[-days:]]

        if not values or max(values) == 0:
            return "▁" * days

        max_val = max(values)
        return "".join(bars[min(int(v / max_val * 7), 7)] if max_val > 0 else bars[0] for v in values)

    def get_lifetime_stats(self) -> Dict[str, Any]:
        """Get all-time statistics."""
        with self._lock:
            lt = dict(self._data["lifetime"])

            # Calculate total unique users across all days
            all_users = set()
            for day_data in self._data["daily"].values():
                all_users.update(day_data.get("unique_users", []))

            lt["total_unique_users"] = len(all_users)
            lt["days_tracked"] = len(self._data["daily"])

            return lt

    def get_avg_response_time(self) -> float:
        """Get average response time from in-memory buffer."""
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)

    def get_command_leaderboard(self, days: int = 30) -> Dict[str, int]:
        """Get command usage over the specified period."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        with self._lock:
            totals: Dict[str, int] = defaultdict(int)
            for date, day in self._data["daily"].items():
                if date >= cutoff:
                    for cmd, count in day.get("command_counts", {}).items():
                        totals[cmd] += count

            return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def _top_n(d: Dict[str, int], n: int) -> List[tuple]:
        """Get top N items from a dict by value."""
        return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]

    def format_hour(self, hour: int) -> str:
        """Format hour for display (12-hour with AM/PM)."""
        if hour == 0:
            return "12 AM"
        elif hour < 12:
            return f"{hour} AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"
