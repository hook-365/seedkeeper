#!/usr/bin/env python3
"""
Centralized configuration constants for Seedkeeper.
Change values here to tune bot behavior without hunting through code.
"""

# ── Context Window Settings ─────────────────────────────────────────
# These control how much conversation history Seedkeeper remembers

# Messages to include in LLM context (sent to the model)
CONVERSATION_HISTORY_LIMIT = 15

# Messages to keep in in-memory session storage (survives within session)
CONVERSATION_STORAGE_LIMIT = 30

# Persistent memories to retrieve from disk
PERSISTENT_MEMORY_LIMIT = 10


# ── Response Settings ───────────────────────────────────────────────

# Default max tokens for responses (can be overridden in personalities.json)
DEFAULT_MAX_TOKENS = 800

# Max message length before splitting (Discord limit is 2000)
MAX_MESSAGE_LENGTH = 2000


# ── Birthday Settings ───────────────────────────────────────────────

# Default time for birthday announcements (24h format)
DEFAULT_BIRTHDAY_ANNOUNCEMENT_TIME = "09:00"
