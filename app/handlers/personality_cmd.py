"""Personality switching command handler."""

from typing import Dict, Any


class PersonalityHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_personality_command(self, command_data: Dict[str, Any]):
        """Handle !personality command - currently local-only mode."""
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        personality = self.bot.personality_manager.get_default()

        # In local-only mode, just show current personality
        await self.bot.send_message(channel_id,
            f"**Current:** {personality['display_name']}\n"
            f"Engine: `{personality.get('model', 'unknown')}`\n\n"
            f"*Personality switching is disabled in local-only mode.*",
            is_dm=is_dm, author_id=author_id)
