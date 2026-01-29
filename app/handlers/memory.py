"""Memory command handlers: memory toggle/status/clear and forgetme."""

from typing import Dict, Any


class MemoryHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_memory_command(self, command_data: Dict[str, Any]):
        """Handle memory-related commands."""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        args = command_data.get('args', '').strip().split()
        is_dm = command_data.get('is_dm', False)

        if not args:
            if self.bot.memory_manager.is_memory_enabled(author_id):
                self.bot.memory_manager.disable_memory(author_id)
                await self.bot.send_message(channel_id,
                    "🧠 Memory disabled. Our conversation history won't be saved anymore.",
                    is_dm=is_dm, author_id=author_id)
            else:
                self.bot.memory_manager.enable_memory(author_id)
                await self.bot.send_message(channel_id,
                    "🧠 Memory enabled! I'll remember our conversations to provide better context.",
                    is_dm=is_dm, author_id=author_id)
        elif args[0] == 'clear':
            self.bot.memory_manager.clear_user_memory(author_id)
            await self.bot.send_message(channel_id,
                "🌱 Memory cleared. Starting fresh!",
                is_dm=is_dm, author_id=author_id)
        elif args[0] == 'status':
            enabled = self.bot.memory_manager.is_memory_enabled(author_id)
            dm_count = len(self.bot.memory_manager.get_recent_memories(author_id, limit=100, channel_type='dm'))
            guild_count = len(self.bot.memory_manager.get_recent_memories(author_id, limit=100, channel_type='guild'))
            total_count = dm_count + guild_count
            status = "enabled" if enabled else "disabled"
            await self.bot.send_message(channel_id,
                f"🧠 Memory is {status}\n"
                f"- Private (DM) memories: {dm_count}\n"
                f"- Public (channel) memories: {guild_count}\n"
                f"- Total: {total_count}\n\n"
                f"🔒 **Privacy:**\n"
                f"- In DMs: I can see both your private and public history\n"
                f"- In channels: I only see public channel conversations\n"
                f"- Your DM conversations never appear in public channels",
                is_dm=is_dm, author_id=author_id)
        else:
            await self.bot.send_message(channel_id,
                "🧠 **Memory Commands**\n"
                "`!memory` - Toggle memory on/off\n"
                "`!memory clear` - Clear conversation history\n"
                "`!memory status` - Check memory status",
                is_dm=is_dm, author_id=author_id)

    async def handle_forgetme_command(self, command_data: Dict[str, Any]):
        """Handle !forgetme command."""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)

        self.bot.memory_manager.clear_user_memory(author_id)
        await self.bot.send_message(channel_id,
            "🌱 I've forgotten everything we've discussed. We're starting fresh, like meeting for the first time.\n\n"
            "*The garden gate swings open to new possibilities...*",
            is_dm=is_dm, author_id=author_id)
