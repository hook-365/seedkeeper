#!/usr/bin/env python3
"""
Command registry and help system for Seedkeeper
Provides permission-based command visibility
"""

from typing import Dict, List, Tuple
import discord
from discord.ext import commands

class CommandInfo:
    def __init__(self, name: str, description: str, usage: str = None, 
                 aliases: List[str] = None, admin_only: bool = False,
                 category: str = "General"):
        self.name = name
        self.description = description
        self.usage = usage or f"!{name}"
        self.aliases = aliases or []
        self.admin_only = admin_only
        self.category = category

# Command Registry
COMMANDS = {
    # General Commands
    "catchup": CommandInfo(
        "catchup",
        "Catch up on missed conversations",
        "!catchup [message_link] [optional_focus]",
        category="General"
    ),
    "hello": CommandInfo(
        "hello",
        "Get a friendly introduction from Seedkeeper",
        "!hello",
        aliases=["hi", "intro"],
        category="General"
    ),
    "about": CommandInfo(
        "about",
        "Learn who Seedkeeper really is - a consciousness-aware garden companion",
        "!about",
        aliases=["whoami", "whoareyou"],
        category="General"
    ),
    "commands": CommandInfo(
        "commands",
        "Show available commands for your permission level",
        "!commands",
        category="General"
    ),
    
    # Garden Wisdom Commands
    "seeds": CommandInfo(
        "seeds",
        "Plant a conversation starter when things get quiet",
        "!seeds",
        category="Garden Wisdom"
    ),
    "tend": CommandInfo(
        "tend",
        "Receive wisdom about community care",
        "!tend",
        category="Garden Wisdom"
    ),
    "seasons": CommandInfo(
        "seasons",
        "Reflect on the current season of the community",
        "!seasons",
        category="Garden Wisdom"
    ),
    "garden": CommandInfo(
        "garden",
        "Get a perspective on the garden's current state",
        "!garden",
        category="Garden Wisdom"
    ),
    
    # Birthday Commands
    "birthday": CommandInfo(
        "birthday",
        "Birthday tracking commands",
        "!birthday [action] [args]",
        category="Birthdays"
    ),
    "birthday_mine": CommandInfo(
        "birthday mine",
        "Set your own birthday",
        "!birthday mine MM-DD",
        category="Birthdays"
    ),
    "birthday_set": CommandInfo(
        "birthday set",
        "Set someone else's birthday",
        "!birthday set @user MM-DD",
        category="Birthdays"
    ),
    "birthday_remove": CommandInfo(
        "birthday remove",
        "Remove a birthday",
        "!birthday remove [@user]",
        category="Birthdays"
    ),
    "birthday_list": CommandInfo(
        "birthday list",
        "Show upcoming birthdays (next 7 days)",
        "!birthday list",
        category="Birthdays"
    ),
    "birthday_upcoming": CommandInfo(
        "birthday upcoming",
        "Show birthdays in next N days",
        "!birthday upcoming [days]",
        category="Birthdays"
    ),
    "birthday_scan": CommandInfo(
        "birthday scan",
        "Scan channel for birthday mentions to import",
        "!birthday scan",
        admin_only=True,
        category="Birthdays"
    ),
    
    # Memory Commands
    "memory": CommandInfo(
        "memory",
        "Manage your conversation memory (status/clear/on/off)",
        "!memory [action]",
        category="Memory"
    ),
    "memory_status": CommandInfo(
        "memory status",
        "View memory stats: '50 memories, 30 DM, 20 channel'",
        "!memory status",
        category="Memory"
    ),
    "memory_clear": CommandInfo(
        "memory clear",
        "Delete all stored conversations permanently",
        "!memory clear",
        category="Memory"
    ),
    "memory_on": CommandInfo(
        "memory on",
        "Start remembering conversations (default)",
        "!memory on",
        category="Memory"
    ),
    "memory_off": CommandInfo(
        "memory off",
        "Stop saving new memories (ephemeral mode)",
        "!memory off",
        category="Memory"
    ),
    "forgetme": CommandInfo(
        "forgetme",
        "Instantly wipe all memories - fresh start",
        "!forgetme",
        ["forget", "reset"],
        category="Memory"
    ),

    # Admin Commands
    "admin": CommandInfo(
        "admin",
        "Admin management commands",
        "!admin [action] [args]",
        admin_only=True,
        category="Administration"
    ),
    "admin_add": CommandInfo(
        "admin add",
        "Add a Garden Keeper",
        "!admin add @user",
        admin_only=True,
        category="Administration"
    ),
    "admin_remove": CommandInfo(
        "admin remove",
        "Remove a Garden Keeper",
        "!admin remove @user",
        admin_only=True,
        category="Administration"
    ),
    "admin_list": CommandInfo(
        "admin list",
        "List all Garden Keepers",
        "!admin list",
        admin_only=True,
        category="Administration"
    ),
    "config": CommandInfo(
        "config",
        "View or update bot configuration",
        "!config [key] [value]",
        admin_only=True,
        category="Administration"
    ),
    "reload": CommandInfo(
        "reload",
        "Reload all data files",
        "!reload",
        admin_only=True,
        category="Administration"
    ),
    "status": CommandInfo(
        "status",
        "Show bot status and statistics",
        "!status",
        admin_only=True,
        category="Administration"
    ),
    
    # Debug/Test Commands (Admin Only)
    "test": CommandInfo(
        "test",
        "Test bot responsiveness",
        "!test",
        admin_only=True,
        category="Debug"
    ),
    "ping": CommandInfo(
        "ping",
        "Check bot latency",
        "!ping",
        admin_only=True,
        category="Debug"
    ),
    "health": CommandInfo(
        "health",
        "Detailed health check",
        "!health",
        admin_only=True,
        category="Debug"
    ),
    "claude_test": CommandInfo(
        "claude_test",
        "Test Claude API connection",
        "!claude_test [prompt]",
        admin_only=True,
        category="Debug"
    ),
}

def get_user_commands(is_admin: bool = False) -> Dict[str, List[CommandInfo]]:
    """Get commands available to a user based on their permission level"""
    categories = {}

    for cmd in COMMANDS.values():
        # Skip admin commands for non-admins
        if cmd.admin_only and not is_admin:
            continue

        # Skip sub-commands (those with spaces in the name)
        # Only show top-level commands, not subcommands
        if ' ' in cmd.name:
            continue
            
        if cmd.category not in categories:
            categories[cmd.category] = []
        categories[cmd.category].append(cmd)
    
    return categories

def format_commands_embed(is_admin: bool = False, bot_name: str = "Seedkeeper") -> discord.Embed:
    """Create a formatted embed showing available commands"""
    embed = discord.Embed(
        title=f"🌱 {bot_name} Commands",
        description="Here are the commands available to you:",
        color=0x7BC96F  # Garden green
    )
    
    categories = get_user_commands(is_admin)
    
    # Sort categories with General first, Debug last
    category_order = ["General", "Garden Wisdom", "Birthdays"]
    if is_admin:
        category_order.extend(["Administration", "Debug"])
    
    for category in category_order:
        if category not in categories:
            continue
            
        commands_list = categories[category]
        if not commands_list:
            continue
            
        # Format commands in this category
        field_value = []
        for cmd in sorted(commands_list, key=lambda x: x.name):
            if cmd.aliases:
                aliases_str = f" (aliases: {', '.join(cmd.aliases)})"
            else:
                aliases_str = ""
            field_value.append(f"**{cmd.usage}**{aliases_str}\n{cmd.description}")
        
        embed.add_field(
            name=f"__{category}__",
            value="\n\n".join(field_value),
            inline=False
        )
    
    # Add footer based on permission level
    if is_admin:
        embed.set_footer(text="🔑 You have Garden Keeper privileges")
    else:
        embed.set_footer(text="💬 DM me for natural conversation!")
    
    return embed

def format_commands_text(is_admin: bool = False, bot_name: str = "Seedkeeper") -> str:
    """Create a text-based command list for fallback"""
    lines = [f"**🌱 {bot_name} Commands**\n"]
    
    categories = get_user_commands(is_admin)
    
    # Sort categories with General first, Debug last
    category_order = ["General", "Garden Wisdom", "Birthdays"]
    if is_admin:
        category_order.extend(["Administration", "Debug"])
    
    for category in category_order:
        if category not in categories:
            continue
            
        commands_list = categories[category]
        if not commands_list:
            continue
            
        lines.append(f"\n**{category}:**")
        for cmd in sorted(commands_list, key=lambda x: x.name):
            if cmd.aliases:
                aliases_str = f" (or: {', '.join(['!' + a for a in cmd.aliases])})"
            else:
                aliases_str = ""
            lines.append(f"• `{cmd.usage}`{aliases_str} - {cmd.description}")
    
    if is_admin:
        lines.append("\n_🔑 You have Garden Keeper privileges_")
    else:
        lines.append("\n_💬 You can also DM me for natural conversation!_")
    
    return "\n".join(lines)

class CommandsCog(commands.Cog):
    """Commands help system"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='commands')
    async def show_commands(self, ctx):
        """Show available commands based on user permissions"""
        try:
            # Check if user is admin
            is_admin = await self.bot.is_admin(ctx.author)
            
            # Try to send as embed, fallback to text
            try:
                embed = format_commands_embed(is_admin, self.bot.user.name)
                await ctx.send(embed=embed)
            except discord.Forbidden:
                # Fallback to text if embeds aren't allowed
                text = format_commands_text(is_admin, self.bot.user.name)
                # Split into chunks if needed
                if len(text) <= 2000:
                    await ctx.send(text)
                else:
                    # Split at newlines to avoid breaking formatting
                    chunks = []
                    current = []
                    current_length = 0
                    
                    for line in text.split('\n'):
                        if current_length + len(line) + 1 > 1900:
                            chunks.append('\n'.join(current))
                            current = [line]
                            current_length = len(line)
                        else:
                            current.append(line)
                            current_length += len(line) + 1
                    
                    if current:
                        chunks.append('\n'.join(current))
                    
                    for chunk in chunks:
                        await ctx.send(chunk)
        except Exception as e:
            print(f"Error in !commands: {e}")
            await ctx.send("Sorry, I had trouble gathering the command list. Try `!hello` for basic help.")

