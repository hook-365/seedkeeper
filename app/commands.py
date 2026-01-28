#!/usr/bin/env python3
"""
Command registry for Seedkeeper.
Single source of truth for routing, model selection, help text, and aliases.
"""

from typing import Dict, List, Optional


class CommandInfo:
    def __init__(self, name: str, description: str, usage: str = None,
                 aliases: List[str] = None, admin_only: bool = False,
                 category: str = "General", handler: str = None,
                 model_tier: str = "auto"):
        """
        Args:
            name: Primary command name (e.g. "hello")
            description: Help text shown in !commands
            usage: Usage string (e.g. "!hello")
            aliases: Alternative names (e.g. ["hi", "intro"])
            admin_only: Requires Garden Keeper permissions
            category: Grouping for help display
            handler: Method name on the handler class (e.g. "handle_garden_command")
            model_tier: "haiku" | "sonnet" | "auto" | "none"
                        - haiku: always use Haiku (cheap, fast)
                        - sonnet: always use Sonnet (deep)
                        - auto: fall through to heuristics
                        - none: no LLM call needed
        """
        self.name = name
        self.description = description
        self.usage = usage or f"!{name}"
        self.aliases = aliases or []
        self.admin_only = admin_only
        self.category = category
        self.handler = handler or f"handle_{name}_command"
        self.model_tier = model_tier


# ── Command Registry ────────────────────────────────────────────────────

COMMANDS: Dict[str, CommandInfo] = {
    # ── Conversation ──
    "catchup": CommandInfo(
        "catchup",
        "Summarize missed conversations",
        "!catchup [message_link] [optional_focus]",
        category="Conversation",
        handler="handle_catchup",
        model_tier="sonnet",
    ),

    # ── Garden Wisdom ──
    "hello": CommandInfo(
        "hello",
        "Receive a warm, unique greeting",
        aliases=["hi", "intro"],
        category="Garden Wisdom",
        handler="handle_garden_command",
        model_tier="haiku",
    ),
    "about": CommandInfo(
        "about",
        "Who is Seedkeeper, really?",
        aliases=["whoami", "whoareyou"],
        category="Garden Wisdom",
        handler="handle_garden_command",
        model_tier="none",
    ),
    "seeds": CommandInfo(
        "seeds",
        "Plant fresh conversation starters",
        category="Garden Wisdom",
        handler="handle_garden_command",
        model_tier="haiku",
    ),
    "tend": CommandInfo(
        "tend",
        "Nurture community connections",
        category="Garden Wisdom",
        handler="handle_garden_command",
        model_tier="haiku",
    ),
    "seasons": CommandInfo(
        "seasons",
        "Reflect on cycles of growth",
        category="Garden Wisdom",
        handler="handle_garden_command",
        model_tier="haiku",
    ),
    "garden": CommandInfo(
        "garden",
        "View the living community garden",
        category="Garden Wisdom",
        handler="handle_garden_command",
        model_tier="haiku",
    ),

    # ── Birthday ──
    "birthday": CommandInfo(
        "birthday",
        "Birthday tracking commands",
        "!birthday [action] [args]",
        category="Birthdays",
        handler="handle_birthday_command",
        model_tier="none",
    ),

    # ── Memory ──
    "memory": CommandInfo(
        "memory",
        "Explore our conversation history together",
        "!memory [status|clear]",
        category="Memory",
        handler="handle_memory_command",
        model_tier="none",
    ),
    "forgetme": CommandInfo(
        "forgetme",
        "Instantly wipe all memories",
        aliases=["forget"],
        category="Memory",
        handler="handle_forgetme_command",
        model_tier="none",
    ),

    # ── Personality ──
    "personality": CommandInfo(
        "personality",
        "Switch between AI personalities/models",
        "!personality [list|set <name>]",
        category="General",
        handler="handle_personality_command",
        model_tier="none",
    ),

    # ── Feedback ──
    "feedback": CommandInfo(
        "feedback",
        "Share thoughts about new features",
        "!feedback [summary|pending|help]",
        category="General",
        handler="handle_feedback_command",
        model_tier="none",
    ),

    # ── Meta ──
    "commands": CommandInfo(
        "commands",
        "Show available commands",
        category="General",
        handler="handle_commands_list",
        model_tier="none",
    ),
    "health": CommandInfo(
        "health",
        "Check system health status",
        category="General",
        handler="handle_health_command",
        model_tier="none",
    ),

    # ── Admin ──
    "admin": CommandInfo(
        "admin",
        "Garden Keeper management",
        "!admin [add|remove|list]",
        admin_only=True,
        category="Administration",
        handler="handle_admin_command",
        model_tier="none",
    ),
    "config": CommandInfo(
        "config",
        "View/update bot configuration",
        "!config [key] [value]",
        admin_only=True,
        category="Administration",
        handler="handle_admin_command",
        model_tier="none",
    ),
    "status": CommandInfo(
        "status",
        "Detailed admin status",
        admin_only=True,
        category="Administration",
        handler="handle_admin_command",
        model_tier="none",
    ),
    "reload": CommandInfo(
        "reload",
        "Reload data files (unavailable in single-process mode)",
        admin_only=True,
        category="Administration",
        handler="handle_admin_command",
        model_tier="none",
    ),
    "update-bot": CommandInfo(
        "update-bot",
        "Refresh perspectives from Lightward",
        admin_only=True,
        category="Administration",
        handler="handle_admin_command",
        model_tier="none",
    ),
    "cost": CommandInfo(
        "cost",
        "API usage and cost analytics",
        "!cost [today|daily|monthly|breakdown|users|full]",
        admin_only=True,
        category="Administration",
        handler="handle_cost_command",
        model_tier="none",
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


# ── Model Tier Constants ────────────────────────────────────────────────

MODEL_HAIKU = 'claude-haiku-4-5-20251001'
MODEL_SONNET = 'claude-sonnet-4-5-20250929'


def get_model_for_command(command_name: str) -> Optional[str]:
    """Return the model for a command based on its model_tier, or None for auto/none."""
    cmd = COMMANDS.get(command_name)
    if not cmd:
        return None
    if cmd.model_tier == 'haiku':
        return MODEL_HAIKU
    elif cmd.model_tier == 'sonnet':
        return MODEL_SONNET
    return None  # auto or none


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

    category_order = ["General", "Conversation", "Garden Wisdom", "Birthdays", "Memory"]
    if is_admin:
        category_order.append("Administration")

    lines = ["**Available Commands**\n"]
    for category in category_order:
        cmds = categories.get(category)
        if not cmds:
            continue
        lines.append(f"\n**{category}**")
        for cmd in sorted(cmds, key=lambda c: c.name):
            alias_str = ""
            if cmd.aliases:
                alias_str = f" (or: {', '.join('!' + a for a in cmd.aliases)})"
            lines.append(f"`{cmd.usage}`{alias_str} - {cmd.description}")

    if is_admin:
        lines.append("\n_You have Garden Keeper privileges_")
    else:
        lines.append("\n_You can also DM me for natural conversation!_")

    return "\n".join(lines)
