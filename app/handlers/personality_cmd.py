"""Personality switching command handler."""

from typing import Dict, Any


class PersonalityHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_personality_command(self, command_data: Dict[str, Any]):
        """Handle !personality command."""
        args = command_data.get('args', '').strip().split()
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        if not args:
            personality = self.bot.personality_manager.get_user_personality(str(author_id))
            await self.bot.send_message(channel_id,
                f"**Current Personality:** {personality['display_name']}\n"
                f"*{personality['description']}*\n\n"
                f"Use `!personality list` to see available options.\n"
                f"Use `!personality set <name>` to switch.",
                is_dm=is_dm, author_id=author_id)
            return

        subcommand = args[0].lower()

        if subcommand == 'list':
            personalities = self.bot.personality_manager.list_personalities()
            current = self.bot.personality_manager.get_user_personality(str(author_id))
            text = "**Available Personalities**\n\n"
            for p in personalities:
                marker = " (active)" if p['name'] == current['name'] else ""
                provider_label = "Claude API" if p['provider'] == 'anthropic' else p.get('model', 'local')
                text += f"**{p['display_name']}**{marker}\n"
                text += f"  Name: `{p['name']}` | Provider: {provider_label}\n"
                text += f"  {p['description']}\n\n"
            text += "Switch with: `!personality set <name>`"
            await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=author_id)

        elif subcommand == 'set' and len(args) >= 2:
            name = args[1].lower()
            if self.bot.personality_manager.set_user_personality(str(author_id), name):
                personality = self.bot.personality_manager.get_personality(name)
                await self.bot.send_message(channel_id,
                    f"Switched to **{personality['display_name']}**.\n"
                    f"*{personality['description']}*",
                    is_dm=is_dm, author_id=author_id)
            else:
                available = [p['name'] for p in self.bot.personality_manager.list_personalities()]
                await self.bot.send_message(channel_id,
                    f"Unknown personality `{name}`.\n"
                    f"Available: {', '.join(f'`{n}`' for n in available)}",
                    is_dm=is_dm, author_id=author_id)
        else:
            await self.bot.send_message(channel_id,
                "**Personality Commands**\n"
                "`!personality` - Show current personality\n"
                "`!personality list` - List available personalities\n"
                "`!personality set <name>` - Switch personality",
                is_dm=is_dm, author_id=author_id)
