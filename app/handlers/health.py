"""Health check command handler."""

from datetime import datetime
from typing import Dict, Any


class HealthHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_health_command(self, command_data: Dict[str, Any]):
        """Handle !health command."""
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        perspective_count = len(self.bot._views_manager.get_all_perspectives())

        health_text = f"""🌱 **Seedkeeper Health Status**

**System**
- Bot: {"Online" if self.bot.is_ready() else "Offline"}
- Latency: {self.bot.latency*1000:.0f}ms
- Guilds: {len(self.bot.guilds)}

**Knowledge Base**
- Perspectives: {perspective_count} Lightward views loaded

**Architecture**: Single-process direct connection
**Last Check**: {datetime.utcnow().strftime('%H:%M UTC')}

*Use `!commands` to see available commands*"""

        await self.bot.send_message(channel_id, health_text, is_dm=is_dm, author_id=author_id)
