"""Commands list and unknown command handlers."""

from typing import Dict, Any

from commands import format_commands_text, suggest_command


class CommandsListHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_commands_list(self, command_data: Dict[str, Any]):
        """Show available commands based on permissions (generated from registry)."""
        author_id = int(command_data.get('author_id'))
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        is_admin = self.bot.admin_manager.is_admin(str(author_id))
        is_nlp = command_data.get('is_nlp', False)

        intro = ""
        if is_nlp:
            intro = "I can help with several things! Here's what I can do:\n\n"

        commands_text = intro + format_commands_text(is_admin)

        if not is_nlp:
            commands_text += "\n\nTip: You can also ask me questions naturally, like 'what can you do?' or 'help me catch up'"

        await self.bot.send_message(channel_id, commands_text, is_dm=is_dm, author_id=str(author_id))

    async def handle_unknown_command(self, command_data: Dict[str, Any]):
        """Handle unknown commands with typo auto-correction."""
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')
        command = command_data.get('command', '')

        # Check for typos
        suggestion = suggest_command(command)
        if suggestion:
            await self.bot.send_message(channel_id,
                f"*I think you meant `!{suggestion}`*",
                is_dm=is_dm, author_id=author_id)
            # Execute the corrected command
            command_data['command'] = suggestion
            await self.bot.handle_discord_command(command_data)
        else:
            await self.bot.send_message(channel_id,
                f"Unknown command: `!{command}` - try `!commands`",
                is_dm=is_dm, author_id=author_id)
