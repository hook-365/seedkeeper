"""Admin command handlers: admin management, config, status, update-bot, reload."""

import asyncio
import time
from datetime import timedelta
from typing import Dict, Any

from prompt_compiler import PromptCompiler
from views_manager import ViewsManager, format_update_message


class AdminHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_admin_command(self, command_data: Dict[str, Any]):
        """Handle !admin add/remove/list subcommands."""
        author_id = int(command_data.get('author_id'))
        channel_id = command_data['channel_id']
        is_dm = command_data.get('is_dm', False)
        args = command_data.get('args', '').strip().split()

        if not args:
            help_text = """🌿 **Garden Keeper Commands**

- `!admin add @user` - Grant Garden Keeper powers
- `!admin remove @user` - Remove Garden Keeper powers
- `!admin list` - List all Garden Keepers
- `!config` - View bot configuration
- `!config [key] [value]` - Update configuration
- `!update-bot` - Refresh perspectives
- `!status` - Show admin status and statistics

*With great gardens come great responsibility* 🌱"""
            await self.bot.send_message(channel_id, help_text, is_dm=is_dm, author_id=str(author_id))
            return

        subcommand = args[0].lower()

        if subcommand == 'list':
            admin_ids = self.bot.admin_manager.list_admins()
            if not admin_ids:
                text = "*The Garden tends itself for now - no Keepers have been named.*"
            else:
                text = "🌿 **Garden Keepers**\n\n"
                for admin_id in admin_ids:
                    text += f"- <@{admin_id}>\n"
                text += "\n*These souls help tend The Garden with special care.*"
            await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'add' and len(args) > 1:
            user_id = args[1].strip('<@!>')
            if user_id.isdigit():
                if self.bot.admin_manager.add_admin(user_id):
                    text = f"🌱 <@{user_id}> has been entrusted with Garden Keeper responsibilities.\n*May they tend The Garden with wisdom and care.*"
                else:
                    text = f"<@{user_id}> is already a Garden Keeper."
            else:
                text = "Please mention a user or provide their ID to add as Garden Keeper."
            await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'remove' and len(args) > 1:
            user_id = args[1].strip('<@!>')
            if user_id.isdigit():
                if self.bot.admin_manager.remove_admin(user_id):
                    text = f"🍂 <@{user_id}>'s Garden Keeper role has returned to the soil.\n*Their contributions remain part of The Garden's memory.*"
                else:
                    text = f"<@{user_id}> is not a Garden Keeper."
            else:
                text = "Please mention a user or provide their ID to remove from Garden Keepers."
            await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

    async def handle_reload_command(self, command_data: Dict[str, Any]):
        """Handle !reload command."""
        channel_id = command_data['channel_id']
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        await self.bot.send_message(channel_id,
            "⚠️ Module reloading is not available in single-process mode.\n"
            "Restart the container to pick up changes:\n"
            "`docker compose restart seedkeeper`",
            is_dm=is_dm, author_id=str(author_id))

    async def handle_status_command(self, command_data: Dict[str, Any]):
        """Handle !status command."""
        channel_id = command_data['channel_id']
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        uptime_seconds = time.time() - self.bot._started_at
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))

        status_text = f"""🔧 **Admin Status**
**Bot**: {self.bot.user} (ID: {self.bot.user.id})
**Guilds**: {len(self.bot.guilds)}
**Latency**: {self.bot.latency*1000:.0f}ms
**Uptime**: {uptime_str}
**Architecture**: Single-process
**Admin Count**: {len(self.bot.admin_manager.admins)}"""

        await self.bot.send_message(channel_id, status_text, is_dm=is_dm, author_id=str(author_id))

    async def handle_config_command(self, command_data: Dict[str, Any]):
        """Handle !config command."""
        channel_id = command_data['channel_id']
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')
        args = command_data.get('args', '').strip().split(maxsplit=1)

        if not args:
            config = self.bot.admin_manager.config
            config_msg = "🌱 **Garden Configuration**\n\n"
            for k, v in config.items():
                readable_key = k.replace('_', ' ').title()
                config_msg += f"- **{readable_key}**: {v}\n"
            config_msg += "\n*To change: `!config [key] [value]`*"
            await self.bot.send_message(channel_id, config_msg, is_dm=is_dm, author_id=str(author_id))

        elif len(args) == 1:
            key = args[0]
            current = self.bot.admin_manager.get_config(key)
            if current is not None:
                await self.bot.send_message(channel_id, f"**{key}**: {current}",
                    is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"Configuration key '{key}' not found.",
                    is_dm=is_dm, author_id=str(author_id))
        else:
            key = args[0]
            value = args[1]
            if value.lower() in ['true', 'yes', 'on']:
                value = True
            elif value.lower() in ['false', 'no', 'off']:
                value = False
            elif value.isdigit():
                value = int(value)

            if self.bot.admin_manager.update_config(key, value):
                await self.bot.send_message(channel_id,
                    f"✨ Configuration updated\n**{key}** is now: {value}\n\n*The Garden adapts to your tending.*",
                    is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"Configuration key '{key}' not found.",
                    is_dm=is_dm, author_id=str(author_id))

    async def handle_update_bot_command(self, command_data: Dict[str, Any]):
        """Handle !update-bot command."""
        channel_id = command_data['channel_id']
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        await self.bot.send_message(channel_id,
            "🌱 *Reaching out to Lightward for fresh perspectives...*",
            is_dm=is_dm, author_id=str(author_id))
        asyncio.create_task(self._run_perspective_update(channel_id, is_dm, str(author_id)))

    async def _run_perspective_update(self, channel_id: str, is_dm: bool, author_id: str):
        """Run the perspective update process in background."""
        start_time = time.time()
        try:
            await self.bot.send_typing(channel_id, is_dm=is_dm, author_id=author_id, duration=10)

            manager = ViewsManager()
            result = await asyncio.to_thread(manager.download_views)

            message = format_update_message(result)
            elapsed = time.time() - start_time
            message += f"\n\nUpdate completed in {elapsed:.1f} seconds"

            await self.bot.send_message(channel_id, message, is_dm=is_dm, author_id=author_id)

            if result.get('success'):
                self.bot.prompt_compiler = PromptCompiler()
                self.bot._views_manager = ViewsManager()
                self.bot._views_manager.parse_views()
                print(f"Reloaded prompt compiler with updated perspectives")

        except Exception as e:
            print(f"Error in perspective update: {e}")
            import traceback
            traceback.print_exc()
            await self.bot.send_message(channel_id,
                f"❌ **Update Error**\n\n{str(e)}\n\n*The Garden remains unchanged.*",
                is_dm=is_dm, author_id=author_id)
