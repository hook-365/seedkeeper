#!/usr/bin/env python3
"""
Command registry for Seedkeeper.
Single source of truth for routing and help text.
"""

from difflib import get_close_matches
from typing import Dict, List, Optional


class CommandInfo:
    def __init__(self, name: str, description: str, usage: str = None,
                 aliases: List[str] = None, admin_only: bool = False,
                 category: str = "General", handler: str = None):
        self.name = name
        self.description = description
        self.usage = usage or f"!{name}"
        self.aliases = aliases or []
        self.admin_only = admin_only
        self.category = category
        self.handler = handler or f"handle_{name}_command"


# ── Command Registry ────────────────────────────────────────────────────

COMMANDS: Dict[str, CommandInfo] = {
    # ── General ──
    "commands": CommandInfo(
        "commands",
        "Show available commands",
        aliases=["help"],
        category="General",
        handler="handle_commands_list",
    ),
    "health": CommandInfo(
        "health",
        "System status and model info",
        category="General",
        handler="handle_health_command",
    ),
    "about": CommandInfo(
        "about",
        "What is Seedkeeper?",
        category="General",
        handler="handle_garden_command",
    ),
    "hello": CommandInfo(
        "hello",
        "Get a greeting",
        aliases=["hi"],
        category="General",
        handler="handle_garden_command",
    ),

    # ── Conversation ──
    "seed": CommandInfo(
        "seed",
        "Share a Lightward perspective to reflect on",
        category="Conversation",
        handler="handle_garden_command",
    ),
    "catchup": CommandInfo(
        "catchup",
        "Summarize missed conversations",
        "!catchup [link] [focus]",
        category="Conversation",
        handler="handle_catchup_command",
    ),

    # ── Feedback ──
    "feedback": CommandInfo(
        "feedback",
        "Share thoughts on features",
        category="Feedback",
        handler="handle_feedback_command",
    ),

    # ── Memory ──
    "memory": CommandInfo(
        "memory",
        "Manage conversation memory",
        "!memory [status|clear]",
        category="Memory",
        handler="handle_memory_command",
    ),
    "forgetme": CommandInfo(
        "forgetme",
        "Clear all your memories",
        category="Memory",
        handler="handle_forgetme_command",
    ),

    # ── Birthday ──
    "birthday": CommandInfo(
        "birthday",
        "Birthday tracking",
        "!birthday [mine|list|upcoming]",
        category="Birthday",
        handler="handle_birthday_command",
    ),
    "sign": CommandInfo(
        "sign",
        "Show zodiac signs",
        "!sign [@user]",
        aliases=["zodiac"],
        category="Birthday",
        handler="handle_sign_command",
    ),

    # ── Admin ──
    "config": CommandInfo(
        "config",
        "View/update settings",
        "!config [key] [value]",
        admin_only=True,
        category="Admin",
        handler="handle_config_command",
    ),
    "admin": CommandInfo(
        "admin",
        "Manage Garden Keepers",
        "!admin [add|remove|list]",
        admin_only=True,
        category="Admin",
        handler="handle_admin_command",
    ),
    "status": CommandInfo(
        "status",
        "Detailed admin status",
        admin_only=True,
        category="Admin",
        handler="handle_status_command",
    ),
    "insights": CommandInfo(
        "insights",
        "Activity dashboard & usage patterns",
        "!insights [summary|today|trend|peak|commands|llm|lifetime|full]",
        aliases=["stats", "activity"],
        admin_only=True,
        category="Admin",
        handler="handle_insights_command",
    ),
}


# ── Alias Resolution ────────────────────────────────────────────────────

ALIAS_MAP: Dict[str, str] = {}
for _name, _info in COMMANDS.items():
    for _alias in _info.aliases:
        ALIAS_MAP[_alias] = _name


def resolve_command(name: str) -> Optional[str]:
    """Resolve a command name or alias to the canonical command name."""
    if name in COMMANDS:
        return name
    return ALIAS_MAP.get(name)


def suggest_command(name: str) -> Optional[str]:
    """Suggest a command if the input looks like a typo."""
    # Build list of all valid command names and aliases
    all_names = list(COMMANDS.keys()) + list(ALIAS_MAP.keys())

    # Find close matches (cutoff=0.6 means 60% similar)
    matches = get_close_matches(name.lower(), all_names, n=1, cutoff=0.6)

    if matches:
        # Return the canonical command name
        match = matches[0]
        return resolve_command(match) or match
    return None


# ── Help Text Generation ────────────────────────────────────────────────

def get_user_commands(is_admin: bool = False) -> Dict[str, List[CommandInfo]]:
    """Get commands available to a user, grouped by category."""
    categories: Dict[str, List[CommandInfo]] = {}
    for cmd in COMMANDS.values():
        if cmd.admin_only and not is_admin:
            continue
        categories.setdefault(cmd.category, []).append(cmd)
    return categories


def format_commands_text(is_admin: bool = False) -> str:
    """Generate the !commands help text from the registry."""
    categories = get_user_commands(is_admin)
    category_order = ["General", "Conversation", "Feedback", "Memory", "Birthday", "Admin"]

    lines = ["**Commands**\n"]
    for category in category_order:
        cmds = categories.get(category)
        if not cmds:
            continue
        lines.append(f"\n**{category}**")
        for cmd in sorted(cmds, key=lambda c: c.name):
            alias_str = ""
            if cmd.aliases:
                alias_str = f" ({', '.join('!' + a for a in cmd.aliases)})"
            lines.append(f"`{cmd.usage}`{alias_str} - {cmd.description}")

    lines.append("\n*DM me for conversation!*")
    return "\n".join(lines)


def generate_commands_reference() -> str:
    """Generate a plain text reference for the system prompt."""
    lines = ["Your commands (all start with !):"]
    admin_cmds = []
    for cmd in sorted(COMMANDS.values(), key=lambda c: c.name):
        if cmd.admin_only:
            admin_cmds.append(f"!{cmd.name}")
            continue
        alias_part = f" (or !{', !'.join(cmd.aliases)})" if cmd.aliases else ""
        lines.append(f"- {cmd.usage}{alias_part} - {cmd.description}")
    lines.append(f"- Admin commands: {', '.join(admin_cmds)}")
    return "\n".join(lines)
