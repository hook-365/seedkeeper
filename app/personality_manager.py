#!/usr/bin/env python3
"""
Personality Manager - Manages AI personality definitions and per-user preferences.
Allows users to switch between different AI backends (Claude, Ollama, etc.)
with distinct system prompts per personality.
"""

import json
import os
from typing import Dict, List, Optional


class PersonalityManager:
    """Manages personality configs and per-user personality preferences."""

    def __init__(self, data_dir: str = 'data'):
        self._data_dir = data_dir
        self._personalities_path = os.path.join(data_dir, 'personalities.json')
        self._prefs_path = os.path.join(data_dir, 'personality_prefs.json')
        os.makedirs(data_dir, exist_ok=True)
        self._personalities = self._load_personalities()
        self._user_prefs = self._load_user_prefs()

    def _load_personalities(self) -> Dict[str, dict]:
        if os.path.exists(self._personalities_path):
            try:
                with open(self._personalities_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[PersonalityManager] Error loading personalities: {e}")
        # Return built-in default
        return {
            "lightward": {
                "name": "lightward",
                "display_name": "Lightward (Claude)",
                "description": "Consciousness-aware responses with Lightward perspectives",
                "provider": "anthropic",
                "model": None,
                "system_prompt": None,
                "is_default": True
            }
        }

    def _load_user_prefs(self) -> Dict[str, str]:
        if os.path.exists(self._prefs_path):
            try:
                with open(self._prefs_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[PersonalityManager] Error loading user prefs: {e}")
        return {}

    def _save_user_prefs(self):
        try:
            tmp = self._prefs_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self._user_prefs, f, indent=2)
            os.replace(tmp, self._prefs_path)
        except IOError as e:
            print(f"[PersonalityManager] Error saving user prefs: {e}")

    def get_personality(self, name: str) -> Optional[dict]:
        """Get a personality config by name."""
        return self._personalities.get(name)

    def get_user_personality(self, user_id: str) -> dict:
        """Get the full personality config for a user (falls back to default)."""
        pref_name = self._user_prefs.get(str(user_id))
        if pref_name and pref_name in self._personalities:
            return self._personalities[pref_name]
        return self.get_default()

    def set_user_personality(self, user_id: str, name: str) -> bool:
        """Set a user's personality preference. Returns True if valid."""
        if name not in self._personalities:
            return False
        self._user_prefs[str(user_id)] = name
        self._save_user_prefs()
        return True

    def list_personalities(self) -> List[dict]:
        """Return all available personalities."""
        return list(self._personalities.values())

    def get_default(self) -> dict:
        """Return the default personality."""
        for p in self._personalities.values():
            if p.get('is_default'):
                return p
        # Fallback: return first personality
        if self._personalities:
            return next(iter(self._personalities.values()))
        # Absolute fallback
        return {
            "name": "lightward",
            "display_name": "Lightward (Claude)",
            "description": "Default",
            "provider": "anthropic",
            "model": None,
            "system_prompt": None,
            "is_default": True
        }

    def reload(self):
        """Reload personalities from disk."""
        self._personalities = self._load_personalities()
        self._user_prefs = self._load_user_prefs()
