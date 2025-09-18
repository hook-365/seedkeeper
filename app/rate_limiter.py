#!/usr/bin/env python3
"""
Rate Limiter for Seedkeeper
Gentle rate limiting to prevent abuse while allowing normal usage
"""

import time
from collections import defaultdict, deque
from typing import Dict, Tuple, Optional
import json
from pathlib import Path
from discord.ext import commands

class RateLimiter:
    """Manages rate limiting for bot commands"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.limits_file = self.data_dir / "rate_limits.json"
        
        # Track command usage per user
        self.user_commands = defaultdict(deque)
        
        # Track global command usage
        self.global_commands = deque()
        
        # Load custom limits or use defaults
        self.limits = self.load_limits()
        
        # Track when users hit limits (for friendly messages)
        self.limit_warnings = defaultdict(float)
    
    def load_limits(self) -> Dict:
        """Load rate limits from file or use defaults"""
        if self.limits_file.exists():
            try:
                with open(self.limits_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default limits - very generous for normal use
        defaults = {
            # Per-user limits
            "catchup_per_hour": 10,        # 10 catchups per hour per user
            "catchup_per_day": 50,         # 50 catchups per day per user
            "birthday_per_hour": 20,       # 20 birthday commands per hour
            "general_per_minute": 10,      # 10 commands per minute for other commands
            
            # Global limits (across all users)
            "global_catchup_per_hour": 100,     # 100 total catchups per hour
            "global_catchup_per_day": 500,      # 500 total catchups per day
            
            # Cooldowns (seconds between uses)
            "catchup_cooldown": 10,        # 10 seconds between catchups for same user
            "birthday_cooldown": 2,        # 2 seconds between birthday commands
            
            # Admin bypass
            "admins_bypass_limits": True,
            
            # Grace period for warnings
            "warning_cooldown": 300        # 5 minutes between warning messages
        }
        
        self.save_limits(defaults)
        return defaults
    
    def save_limits(self, limits: Dict):
        """Save rate limits to file"""
        with open(self.limits_file, 'w') as f:
            json.dump(limits, f, indent=2)
    
    def update_limit(self, key: str, value: int) -> bool:
        """Update a specific rate limit"""
        if key in self.limits:
            self.limits[key] = value
            self.save_limits(self.limits)
            return True
        return False
    
    def check_rate_limit(self, user_id: str, command: str, is_admin: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Check if a command is rate limited
        Returns (allowed, reason_if_denied)
        """
        # Admins bypass if configured
        if is_admin and self.limits.get("admins_bypass_limits", True):
            return True, None
        
        current_time = time.time()
        
        # Clean old entries
        self._clean_old_entries(current_time)
        
        # Check cooldown for specific commands
        if command == "catchup":
            cooldown = self.limits.get("catchup_cooldown", 10)
            if self._check_cooldown(user_id, "catchup", cooldown, current_time):
                return False, f"*The garden needs a moment to breathe... Please wait {cooldown} seconds between catchup requests.*"
        
        elif command.startswith("birthday"):
            cooldown = self.limits.get("birthday_cooldown", 2)
            if self._check_cooldown(user_id, "birthday", cooldown, current_time):
                return False, f"*Patience, dear gardener... Wait {cooldown} seconds between birthday commands.*"
        
        # Check per-user rate limits
        user_key = f"{user_id}:{command}"
        
        if command == "catchup":
            # Check hourly limit
            hourly_limit = self.limits.get("catchup_per_hour", 10)
            hour_ago = current_time - 3600
            recent_uses = [t for t in self.user_commands[user_key] if t > hour_ago]
            
            if len(recent_uses) >= hourly_limit:
                return False, (
                    f"*The garden needs time to regenerate... "
                    f"You've reached the hourly limit of {hourly_limit} catchups. "
                    f"Please return in a while.*"
                )
            
            # Check daily limit
            daily_limit = self.limits.get("catchup_per_day", 50)
            day_ago = current_time - 86400
            daily_uses = [t for t in self.user_commands[user_key] if t > day_ago]
            
            if len(daily_uses) >= daily_limit:
                return False, (
                    f"*You've tended the garden thoroughly today... "
                    f"You've reached the daily limit of {daily_limit} catchups. "
                    f"Please return tomorrow.*"
                )
            
            # Check global limits
            global_hourly = self.limits.get("global_catchup_per_hour", 100)
            global_recent = [t for t in self.global_commands if t > hour_ago and t]
            
            if len(global_recent) >= global_hourly:
                return False, (
                    "*The Garden is overwhelmed with returning souls... "
                    "Please wait a moment while we tend to others.*"
                )
        
        elif command.startswith("birthday"):
            # Check birthday command limits
            hourly_limit = self.limits.get("birthday_per_hour", 20)
            hour_ago = current_time - 3600
            recent_uses = [t for t in self.user_commands[user_key] if t > hour_ago]
            
            if len(recent_uses) >= hourly_limit:
                return False, (
                    f"*So many celebrations! You've reached the limit of {hourly_limit} "
                    f"birthday commands per hour. The garden needs a moment to rest.*"
                )
        
        else:
            # General command limits
            minute_limit = self.limits.get("general_per_minute", 10)
            minute_ago = current_time - 60
            recent_uses = [t for t in self.user_commands[user_key] if t > minute_ago]
            
            if len(recent_uses) >= minute_limit:
                return False, (
                    "*The garden paths need a moment to clear... "
                    "Please slow down your requests.*"
                )
        
        # Record the usage
        self.user_commands[user_key].append(current_time)
        if command == "catchup":
            self.global_commands.append(current_time)
        
        return True, None
    
    def _check_cooldown(self, user_id: str, command: str, cooldown: int, current_time: float) -> bool:
        """Check if user is still in cooldown for a command"""
        user_key = f"{user_id}:{command}"
        if self.user_commands[user_key]:
            last_use = self.user_commands[user_key][-1]
            if current_time - last_use < cooldown:
                return True
        return False
    
    def _clean_old_entries(self, current_time: float):
        """Remove old entries from tracking to save memory"""
        day_ago = current_time - 86400
        
        # Clean user commands
        for key in list(self.user_commands.keys()):
            self.user_commands[key] = deque(
                [t for t in self.user_commands[key] if t > day_ago],
                maxlen=100
            )
            if not self.user_commands[key]:
                del self.user_commands[key]
        
        # Clean global commands
        self.global_commands = deque(
            [t for t in self.global_commands if t > day_ago],
            maxlen=500
        )
    
    def get_user_status(self, user_id: str, command: str) -> Dict:
        """Get current usage status for a user"""
        current_time = time.time()
        user_key = f"{user_id}:{command}"
        
        hour_ago = current_time - 3600
        day_ago = current_time - 86400
        
        hourly_uses = [t for t in self.user_commands[user_key] if t > hour_ago]
        daily_uses = [t for t in self.user_commands[user_key] if t > day_ago]
        
        if command == "catchup":
            return {
                "hourly_used": len(hourly_uses),
                "hourly_limit": self.limits.get("catchup_per_hour", 10),
                "daily_used": len(daily_uses),
                "daily_limit": self.limits.get("catchup_per_day", 50),
                "cooldown": self.limits.get("catchup_cooldown", 10)
            }
        elif command.startswith("birthday"):
            return {
                "hourly_used": len(hourly_uses),
                "hourly_limit": self.limits.get("birthday_per_hour", 20),
                "cooldown": self.limits.get("birthday_cooldown", 2)
            }
        else:
            minute_ago = current_time - 60
            minute_uses = [t for t in self.user_commands[user_key] if t > minute_ago]
            return {
                "minute_used": len(minute_uses),
                "minute_limit": self.limits.get("general_per_minute", 10)
            }
    
    def reset_user_limits(self, user_id: str):
        """Reset all limits for a specific user"""
        keys_to_remove = [k for k in self.user_commands.keys() if k.startswith(f"{user_id}:")]
        for key in keys_to_remove:
            del self.user_commands[key]
    
    def reset_all_limits(self):
        """Reset all rate limit tracking"""
        self.user_commands.clear()
        self.global_commands.clear()
        self.limit_warnings.clear()


def rate_limit():
    """Discord.py check decorator for rate limiting"""
    async def predicate(ctx):
        if not hasattr(ctx.bot, 'rate_limiter'):
            return True  # No rate limiter configured
        
        # Check if user is admin
        is_admin = False
        if hasattr(ctx.bot, 'admin_manager'):
            is_admin = ctx.bot.admin_manager.is_admin(str(ctx.author.id))
        
        # Get command name
        command = ctx.command.name if ctx.command else "general"
        
        # Check rate limit
        allowed, reason = ctx.bot.rate_limiter.check_rate_limit(
            str(ctx.author.id),
            command,
            is_admin
        )
        
        if not allowed:
            await ctx.send(reason)
            return False
        
        return True
    
    return commands.check(predicate)