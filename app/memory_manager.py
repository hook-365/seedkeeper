#!/usr/bin/env python3
"""
Persistent Memory Manager for Seedkeeper
Provides forever-lasting user conversation memory with explicit control
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass, asdict
import hashlib
from persistence import atomic_json_write
from input_validator import InputValidator

@dataclass
class Memory:
    """Represents a single memory/interaction"""
    timestamp: str
    content: str
    author: str  # 'user' or 'bot'
    channel_type: str  # 'dm' or 'guild'
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None  # Add channel_id for proper channel isolation
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # Handle old memories without channel_id
        if 'channel_id' not in data:
            data['channel_id'] = None
        return cls(**data)

class MemoryManager:
    """Manages persistent user memories across sessions"""

    MAX_CACHE_KEYS = 200

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.memory_dir = self.data_dir / "memories"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Memory settings file
        self.settings_file = self.data_dir / "memory_settings.json"
        self.settings = self.load_settings()

        # In-memory cache (replaces Redis)
        self._cache: Dict[str, str] = {}

        # Warm cache from disk on startup
        self._warm_cache()

    def load_settings(self) -> Dict[str, Any]:
        """Load memory settings (which users have opted in/out)"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except:
                return self.get_default_settings()
        return self.get_default_settings()

    def get_default_settings(self) -> Dict[str, Any]:
        """Default memory settings"""
        return {
            "enabled_users": {},  # user_id: {"enabled": bool, "max_memories": int, "auto_summarize": bool}
            "default_max_memories": 100,  # Per user
            "default_auto_summarize": True,
            "summary_threshold": 50,  # Summarize older memories after this many
            "retention_days": None,  # None means forever
        }

    def save_settings(self):
        """Save memory settings to disk"""
        atomic_json_write(self.settings_file, self.settings, indent=2)

    def get_user_file(self, user_id: str) -> Path:
        """Get the memory file path for a user"""
        # Validate user_id is numeric (Discord snowflake)
        if not user_id.isdigit():
            raise ValueError(f"Invalid user_id: {user_id}")
        # Hash the user ID for privacy
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        return self.memory_dir / f"user_{user_id}_{user_hash}.json"

    def is_memory_enabled(self, user_id: str) -> bool:
        """Check if memory is enabled for a user"""
        user_settings = self.settings["enabled_users"].get(user_id, {})
        return user_settings.get("enabled", True)  # Default to enabled

    def enable_memory(self, user_id: str, max_memories: Optional[int] = None):
        """Enable memory for a user"""
        self.settings["enabled_users"][user_id] = {
            "enabled": True,
            "max_memories": max_memories or self.settings["default_max_memories"],
            "auto_summarize": self.settings["default_auto_summarize"],
            "enabled_at": datetime.utcnow().isoformat()
        }
        self.save_settings()

    def disable_memory(self, user_id: str, keep_existing: bool = True):
        """Disable memory for a user"""
        self.settings["enabled_users"][user_id] = {
            "enabled": False,
            "disabled_at": datetime.utcnow().isoformat(),
            "keep_existing": keep_existing
        }
        self.save_settings()

        if not keep_existing:
            # Clear all memories for this user
            self.clear_user_memory(user_id)

    def _evict_cache(self):
        """Evict oldest entries if cache exceeds size limit"""
        if len(self._cache) <= self.MAX_CACHE_KEYS:
            return
        # Remove oldest entries (FIFO order via dict insertion order)
        excess = len(self._cache) - self.MAX_CACHE_KEYS
        keys_to_remove = list(self._cache.keys())[:excess]
        for key in keys_to_remove:
            del self._cache[key]

    def add_memory(self, user_id: str, content: str, author: str = "user",
                   channel_type: str = "dm", guild_id: Optional[str] = None,
                   channel_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a memory for a user - optimized streaming approach"""
        if not self.is_memory_enabled(user_id):
            return False

        # Sanitize content before storage
        safe_content = InputValidator.sanitize_string(content, max_length=2000)

        memory = Memory(
            timestamp=datetime.utcnow().isoformat(),
            content=safe_content,
            author=author,
            channel_type=channel_type,
            guild_id=guild_id,
            channel_id=channel_id,
            metadata=metadata or {}
        )

        # Get memory settings
        user_settings = self.settings["enabled_users"].get(user_id, {})
        max_memories = user_settings.get("max_memories", self.settings["default_max_memories"])

        # Streaming approach: only load recent memories if file exists
        user_file = self.get_user_file(user_id)

        if user_file.exists():
            # Load only the tail of the file for efficiency
            memories = self.load_user_memories_tail(user_id, max_memories - 1)
            memories.append(memory.to_dict())
        else:
            # New user, start fresh
            memories = [memory.to_dict()]

        # Ensure we don't exceed the limit
        if len(memories) > max_memories:
            memories = memories[-max_memories:]

        # Save to disk (only the memories we need to keep)
        self.save_user_memories(user_id, memories)

        # Update in-memory cache (keep recent 20 for quick access)
        cache_key = f"memory:{user_id}"
        recent_memories = memories[-20:]
        self._cache[cache_key] = json.dumps(recent_memories)
        self._evict_cache()

        return True

    def load_user_memories_tail(self, user_id: str, limit: int) -> List[Dict]:
        """Load only the last N memories for a user (memory efficient)"""
        user_file = self.get_user_file(user_id)

        if not user_file.exists():
            return []

        try:
            with open(user_file, 'r') as f:
                memories = json.load(f)
                # Only return the tail to avoid loading everything into memory
                return memories[-limit:] if len(memories) > limit else memories
        except:
            return []

    def load_user_memories(self, user_id: str) -> List[Dict]:
        """Load all memories for a user from disk"""
        user_file = self.get_user_file(user_id)

        if user_file.exists():
            try:
                with open(user_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_user_memories(self, user_id: str, memories: List[Dict]):
        """Save user memories to disk"""
        user_file = self.get_user_file(user_id)
        atomic_json_write(user_file, memories, indent=2)

    def get_recent_memories(self, user_id: str, limit: int = 10, channel_type: Optional[str] = None,
                           guild_id: Optional[str] = None, channel_id: Optional[str] = None) -> List[Dict]:
        """Get recent memories for a user, optionally filtered by context

        Args:
            user_id: The user ID
            limit: Maximum number of memories to return
            channel_type: Optional filter - 'dm' for DMs only, 'guild' for channels only
            guild_id: Optional filter - specific guild ID for channel memories
            channel_id: Optional filter - specific channel ID for channel-specific memories
        """
        if not self.is_memory_enabled(user_id):
            return []

        # Build cache key with context
        cache_key_parts = [f"memory:{user_id}"]
        if channel_type:
            cache_key_parts.append(channel_type)
        if guild_id:
            cache_key_parts.append(guild_id)
        if channel_id:
            cache_key_parts.append(channel_id)
        cache_key = ":".join(cache_key_parts)

        # Try cache first
        cached = self._cache.get(cache_key)

        if cached:
            memories = json.loads(cached)
            return memories[-limit:]

        # Load from disk
        all_memories = self.load_user_memories(user_id)

        # Filter by context if specified
        if channel_type or guild_id or channel_id:
            filtered = []
            for mem in all_memories:
                # Filter by channel type
                if channel_type and mem.get('channel_type') != channel_type:
                    continue
                # Filter by guild ID for channel messages
                if guild_id and mem.get('guild_id') != guild_id:
                    continue
                # Filter by specific channel ID
                if channel_id and mem.get('channel_id') != channel_id:
                    continue
                # Filter out guild messages if we want DMs only
                if channel_type == 'dm' and mem.get('guild_id'):
                    continue
                filtered.append(mem)
            memories = filtered
        else:
            memories = all_memories

        # Cache recent filtered memories
        if memories:
            recent = memories[-20:]
            self._cache[cache_key] = json.dumps(recent)
            self._evict_cache()

        return memories[-limit:]

    def get_mixed_memories(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get recent memories mixing both DM and channel contexts
        WARNING: This mixes private and public contexts - use carefully!
        """
        return self.get_recent_memories(user_id, limit, channel_type=None)

    def get_context_memories(self, user_id: str, context: str, limit: int = 5) -> List[Dict]:
        """Get memories relevant to a specific context"""
        if not self.is_memory_enabled(user_id):
            return []

        memories = self.load_user_memories(user_id)

        # Simple relevance scoring based on keyword matching
        context_lower = context.lower()
        context_words = set(context_lower.split())

        scored_memories = []
        for memory in memories:
            content_lower = memory.get("content", "").lower()
            content_words = set(content_lower.split())

            # Score based on word overlap
            overlap = len(context_words & content_words)
            if overlap > 0:
                scored_memories.append((overlap, memory))

        # Sort by relevance and recency
        scored_memories.sort(key=lambda x: (x[0], x[1]["timestamp"]), reverse=True)

        return [m[1] for m in scored_memories[:limit]]

    def summarize_memories(self, user_id: str, older_than_days: int = 30) -> Optional[str]:
        """Create a summary of older memories (for Claude to generate)"""
        memories = self.load_user_memories(user_id)

        if not memories:
            return None

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        older_memories = [
            m for m in memories
            if datetime.fromisoformat(m["timestamp"]) < cutoff
        ]

        if not older_memories:
            return None

        # Format memories for summarization
        summary_text = "Previous conversations to summarize:\n\n"
        for memory in older_memories[-20:]:  # Last 20 older memories
            author = "User" if memory["author"] == "user" else "Bot"
            summary_text += f"[{memory['timestamp']}] {author}: {memory['content']}\n"

        return summary_text

    def clear_user_memory(self, user_id: str) -> bool:
        """Clear all memories for a user"""
        # Remove from disk
        user_file = self.get_user_file(user_id)
        if user_file.exists():
            user_file.unlink()

        # Remove from cache
        cache_key = f"memory:{user_id}"
        self._cache.pop(cache_key, None)
        # Also remove any filtered cache entries for this user
        keys_to_remove = [k for k in self._cache if k.startswith(f"memory:{user_id}:")]
        for key in keys_to_remove:
            del self._cache[key]

        # Update settings
        if user_id in self.settings["enabled_users"]:
            self.settings["enabled_users"][user_id]["last_cleared"] = datetime.utcnow().isoformat()
            self.save_settings()

        return True

    def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Get memory statistics for a user"""
        memories = self.load_user_memories(user_id)
        user_settings = self.settings["enabled_users"].get(user_id, {})

        if not memories:
            return {
                "enabled": self.is_memory_enabled(user_id),
                "total_memories": 0,
                "oldest_memory": None,
                "newest_memory": None,
                "max_memories": user_settings.get("max_memories", self.settings["default_max_memories"]),
                "auto_summarize": user_settings.get("auto_summarize", self.settings["default_auto_summarize"])
            }

        oldest = memories[0]["timestamp"]
        newest = memories[-1]["timestamp"]

        # Calculate time span
        oldest_dt = datetime.fromisoformat(oldest)
        newest_dt = datetime.fromisoformat(newest)
        days_span = (newest_dt - oldest_dt).days

        return {
            "enabled": self.is_memory_enabled(user_id),
            "total_memories": len(memories),
            "oldest_memory": oldest,
            "newest_memory": newest,
            "days_of_history": days_span,
            "max_memories": user_settings.get("max_memories", self.settings["default_max_memories"]),
            "auto_summarize": user_settings.get("auto_summarize", self.settings["default_auto_summarize"]),
            "dm_memories": sum(1 for m in memories if m.get("channel_type") == "dm"),
            "guild_memories": sum(1 for m in memories if m.get("channel_type") == "guild")
        }

    def _warm_cache(self):
        """Load recent memories from disk into cache on startup"""
        for memory_file in self.memory_dir.glob("user_*.json"):
            # Extract user_id from filename
            parts = memory_file.stem.split("_")
            if len(parts) >= 2:
                user_id = parts[1]

                # Load recent memories and cache
                memories = self.load_user_memories(user_id)
                if memories:
                    recent = memories[-20:]
                    cache_key = f"memory:{user_id}"
                    try:
                        self._cache[cache_key] = json.dumps(recent)
                    except Exception as e:
                        print(f"Could not cache memories for user {user_id}: {e}")

        self._evict_cache()
        print(f"Memory cache warmed: {len(self._cache)} entries")

    def export_user_memories(self, user_id: str, format: str = "json") -> Optional[str]:
        """Export user memories in various formats"""
        memories = self.load_user_memories(user_id)

        if not memories:
            return None

        if format == "json":
            return json.dumps(memories, indent=2)

        elif format == "text":
            output = f"Memory Export for User {user_id}\n"
            output += f"{'='*50}\n\n"

            for memory in memories:
                timestamp = memory["timestamp"]
                author = "You" if memory["author"] == "user" else "Seedkeeper"
                content = memory["content"]
                output += f"[{timestamp}] {author}:\n{content}\n\n"

            return output

        elif format == "markdown":
            output = f"# Memory Export\n\n"
            output += f"**User ID:** {user_id}\n"
            output += f"**Total Memories:** {len(memories)}\n\n"

            current_date = None
            for memory in memories:
                timestamp = datetime.fromisoformat(memory["timestamp"])
                date_str = timestamp.strftime("%Y-%m-%d")

                if date_str != current_date:
                    output += f"\n## {date_str}\n\n"
                    current_date = date_str

                time_str = timestamp.strftime("%H:%M:%S")
                author = "You" if memory["author"] == "user" else "Seedkeeper"
                content = memory["content"]

                output += f"**[{time_str}] {author}:**\n> {content}\n\n"

            return output

        return None
