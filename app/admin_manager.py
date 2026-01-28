#!/usr/bin/env python3
"""
Admin Manager for Seedkeeper
Handles bot administration and permissions
"""

import json
import os
from pathlib import Path
from typing import List, Set, Optional
import discord
from discord.ext import commands
from persistence import atomic_json_write

class AdminManager:
    """Manages admin users and permissions for the bot"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.admin_file = self.data_dir / "admins.json"
        self.config_file = self.data_dir / "bot_config.json"
        self.admins = self.load_admins()
        self.config = self.load_config()
    
    def load_admins(self) -> Set[str]:
        """Load admin user IDs from file"""
        if self.admin_file.exists():
            try:
                with open(self.admin_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('admins', []))
            except:
                return set()
        
        # Initialize with owner from environment if no admin file exists
        owner_id = os.getenv('BOT_OWNER_ID')
        if owner_id:
            initial_admins = {owner_id}
            self.save_admins(initial_admins)
            return initial_admins
        return set()
    
    def load_config(self) -> dict:
        """Load bot configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return self.get_default_config()
        return self.get_default_config()
    
    def get_default_config(self) -> dict:
        """Get default bot configuration"""
        return {
            'require_admin_for_birthday_remove': True,
            'require_admin_for_birthday_set': False,
            'allow_birthday_learning': True,
            'birthday_announcement_time': '09:00',
            'max_catchup_messages': 500,
            'allow_dm_commands': False
        }
    
    def save_admins(self, admins: Set[str]):
        """Save admin list to file"""
        atomic_json_write(self.admin_file, {'admins': list(admins)}, indent=2)
        self.admins = admins

    def save_config(self):
        """Save configuration to file"""
        atomic_json_write(self.config_file, self.config, indent=2)
    
    def is_admin(self, user_id: str) -> bool:
        """Check if a user is an admin"""
        return user_id in self.admins
    
    def add_admin(self, user_id: str) -> bool:
        """Add a user as admin"""
        if user_id not in self.admins:
            self.admins.add(user_id)
            self.save_admins(self.admins)
            return True
        return False
    
    def remove_admin(self, user_id: str) -> bool:
        """Remove a user from admins"""
        if user_id in self.admins:
            self.admins.remove(user_id)
            self.save_admins(self.admins)
            return True
        return False
    
    def list_admins(self) -> List[str]:
        """Get list of admin user IDs"""
        return list(self.admins)
    
    def update_config(self, key: str, value) -> bool:
        """Update a configuration value"""
        if key in self.config:
            self.config[key] = value
            self.save_config()
            return True
        return False
    
    def get_config(self, key: str, default=None):
        """Get a configuration value"""
        return self.config.get(key, default)


def is_admin():
    """Discord.py check decorator for admin-only commands"""
    async def predicate(ctx):
        # Check if user is bot owner (always admin)
        app_info = await ctx.bot.application_info()
        if ctx.author.id == app_info.owner.id:
            return True
        
        # Check if user is in admin list
        if hasattr(ctx.bot, 'admin_manager'):
            return ctx.bot.admin_manager.is_admin(str(ctx.author.id))
        
        # Check for Discord server admin/mod roles
        if ctx.guild:
            # Check for administrator permission
            if ctx.author.guild_permissions.administrator:
                return True
            
            # Check for specific roles (customizable)
            admin_roles = ['Admin', 'Moderator', 'Garden Keeper', 'admin', 'mod']
            user_roles = [role.name for role in ctx.author.roles]
            if any(role in user_roles for role in admin_roles):
                return True
        
        return False
    
    return commands.check(predicate)


def is_admin_or_self():
    """Check if user is admin or targeting themselves"""
    async def predicate(ctx):
        # First check if they're an admin
        if await is_admin().predicate(ctx):
            return True
        
        # Then check if they're targeting themselves
        # This works for commands where the user is the first mention or no mention means self
        if not ctx.message.mentions or ctx.message.mentions[0] == ctx.author:
            return True
        
        return False
    
    return commands.check(predicate)


class AdminCommands(commands.Cog):
    """Admin commands for Seedkeeper"""
    
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, 'admin_manager'):
            bot.admin_manager = AdminManager()
    
    @commands.command(name='admin')
    @is_admin()
    async def admin(self, ctx, action: str = None, *, args: str = None):
        """
        Admin management commands
        Usage:
        - !admin - Show admin help
        - !admin add @user - Add an admin
        - !admin remove @user - Remove an admin
        - !admin list - List all admins
        """
        if not action:
            await ctx.send(
                "🌿 **Garden Keeper Commands**\n\n"
                "• `!admin add @user` - Grant Garden Keeper powers\n"
                "• `!admin remove @user` - Remove Garden Keeper powers\n"
                "• `!admin list` - List all Garden Keepers\n"
                "• `!config` - View bot configuration\n"
                "• `!config [key] [value]` - Update configuration\n"
                "• `!reload` - Reload data files\n"
                "• `!restart` - Restart the bot (applies code changes)\n"
                "• `!status` - Show bot status\n"
                "• `!broadcast [message]` - Send announcement to servers & active DMs\n\n"
                "*With great gardens come great responsibility* 🌱"
            )
            return
        
        action = action.lower()
        
        if action == "add":
            if not ctx.message.mentions:
                await ctx.send("Please mention a user to add as Garden Keeper.")
                return
            
            user = ctx.message.mentions[0]
            if self.bot.admin_manager.add_admin(str(user.id)):
                await ctx.send(
                    f"🌱 {user.mention} has been entrusted with Garden Keeper responsibilities.\n"
                    f"*May they tend The Garden with wisdom and care.*"
                )
            else:
                await ctx.send(f"{user.mention} is already a Garden Keeper.")
        
        elif action == "remove":
            if not ctx.message.mentions:
                await ctx.send("Please mention a user to remove from Garden Keepers.")
                return
            
            user = ctx.message.mentions[0]
            if self.bot.admin_manager.remove_admin(str(user.id)):
                await ctx.send(
                    f"🍂 {user.mention}'s Garden Keeper role has returned to the soil.\n"
                    f"*Their contributions remain part of The Garden's memory.*"
                )
            else:
                await ctx.send(f"{user.mention} is not a Garden Keeper.")
        
        elif action == "list":
            admin_ids = self.bot.admin_manager.list_admins()
            if not admin_ids:
                await ctx.send("*The Garden tends itself for now - no Keepers have been named.*")
                return
            
            admin_list = "🌿 **Garden Keepers**\n\n"
            for admin_id in admin_ids:
                user = self.bot.get_user(int(admin_id))
                if user:
                    admin_list += f"• {user.mention} ({user.name})\n"
                else:
                    admin_list += f"• User ID: {admin_id} (not in server)\n"
            
            admin_list += "\n*These souls help tend The Garden with special care.*"
            await ctx.send(admin_list)
        
        else:
            await ctx.send(f"Unknown action '{action}'. Use `!admin` to see available commands.")
    
    @commands.command(name='config')
    @is_admin()
    async def config(self, ctx, key: str = None, *, value: str = None):
        """
        View or update bot configuration
        """
        if not key:
            # Show current configuration
            config = self.bot.admin_manager.config
            config_msg = "🌱 **Garden Configuration**\n\n"
            
            for k, v in config.items():
                # Make key names more readable
                readable_key = k.replace('_', ' ').title()
                config_msg += f"• **{readable_key}**: {v}\n"
            
            config_msg += "\n*To change: `!config [key] [value]`*"
            await ctx.send(config_msg)
            return
        
        if value is None:
            # Show specific config value
            current = self.bot.admin_manager.get_config(key)
            if current is not None:
                await ctx.send(f"**{key}**: {current}")
            else:
                await ctx.send(f"Configuration key '{key}' not found.")
            return
        
        # Update configuration
        # Convert value to appropriate type
        if value.lower() in ['true', 'yes', 'on']:
            value = True
        elif value.lower() in ['false', 'no', 'off']:
            value = False
        elif value.isdigit():
            value = int(value)
        
        if self.bot.admin_manager.update_config(key, value):
            await ctx.send(
                f"✨ Configuration updated\n"
                f"**{key}** is now: {value}\n\n"
                f"*The Garden adapts to your tending.*"
            )
        else:
            await ctx.send(f"Configuration key '{key}' not found.")
    
    @commands.command(name='reload')
    @is_admin()
    async def reload_data(self, ctx):
        """Reload bot data files (birthdays, admins, config)"""
        try:
            # Reload admin data
            self.bot.admin_manager.admins = self.bot.admin_manager.load_admins()
            self.bot.admin_manager.config = self.bot.admin_manager.load_config()
            
            # Reload birthday data if available
            if hasattr(self.bot, 'birthday_manager'):
                self.bot.birthday_manager.birthdays = self.bot.birthday_manager.load_birthdays()
                self.bot.birthday_manager.pending_confirmations = self.bot.birthday_manager.load_pending()
            
            await ctx.send(
                "🌿 *The Garden's memory refreshes like morning dew...*\n\n"
                "All data files have been reloaded.\n"
                f"• Admins: {len(self.bot.admin_manager.admins)}\n"
                f"• Birthdays: {len(self.bot.birthday_manager.birthdays) if hasattr(self.bot, 'birthday_manager') else 0}\n"
                f"• Configuration: Refreshed\n\n"
                "*The Garden continues with renewed clarity.*"
            )
        except Exception as e:
            await ctx.send(f"Error reloading data: {e}")
    
    @commands.command(name='status')
    @is_admin()
    async def status_cmd(self, ctx):
        """Show bot status and statistics"""
        import datetime
        import psutil
        import platform
        
        # Get bot uptime
        uptime = datetime.datetime.utcnow() - self.bot.start_time if hasattr(self.bot, 'start_time') else None
        
        # Get system info
        try:
            process = psutil.Process()
            memory = process.memory_info().rss / 1024 / 1024  # MB
        except:
            memory = "Unknown"
        
        status_msg = "🌱 **Seedkeeper Status**\n\n"
        status_msg += f"**Connected Servers**: {len(self.bot.guilds)}\n"
        status_msg += f"**Total Members**: {sum(g.member_count for g in self.bot.guilds)}\n"
        
        if hasattr(self.bot, 'birthday_manager'):
            status_msg += f"**Birthdays Tracked**: {len(self.bot.birthday_manager.birthdays)}\n"
        
        status_msg += f"**Loaded Perspectives**: {len(self.bot.perspectives.perspectives) if hasattr(self.bot, 'perspectives') else 0}\n"
        status_msg += f"**Garden Keepers**: {len(self.bot.admin_manager.admins)}\n"
        
        if uptime:
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            status_msg += f"**Tending Since**: {days} days, {hours} hours, {minutes} minutes\n"
        
        if memory != "Unknown":
            status_msg += f"**Memory Usage**: {memory:.1f} MB\n"
        
        status_msg += f"**Python**: {platform.python_version()}\n"
        status_msg += f"**Discord.py**: {discord.__version__}\n"
        
        status_msg += "\n*The Garden thrives under watchful care.* 🌿"
        await ctx.send(status_msg)
    
    @commands.command(name='restart')
    @is_admin()
    async def restart_bot(self, ctx):
        """Trigger hot reload of all modules (doesn't rebuild Docker)"""
        await ctx.send(
            "🌱 **Hot Reloading Seedkeeper Modules**\n\n"
            "*The garden refreshes its understanding without sleeping...*\n\n"
            "All Python modules will reload with latest code changes.\n"
            "Note: This doesn't rebuild Docker containers - use manual rebuild for that."
        )
        
        try:
            # In the new architecture, we can't restart from here
            # But we can suggest the proper way
            await ctx.send(
                "🔄 **Hot Reload Instructions**\n\n"
                "The worker automatically reloads when files change.\n"
                "Just edit any Python file and save it!\n\n"
                "For full Docker rebuild, run on host:\n"
                "`/storage/docker/seedkeeper/rebuild.sh`\n\n"
                "*The garden adapts continuously to your changes.*"
            )
        except Exception as e:
            print(f"[ERROR] Restart info failed: {e}")
            await ctx.send(f"*The garden had trouble explaining...* Error: {str(e)[:200]}")
    
    @commands.command(name='broadcast')
    @is_admin()
    async def broadcast(self, ctx, *, message: str = None):
        """Broadcast a message to all servers and active DMs"""
        if not message:
            # Count active DM users
            active_dm_count = len(self.bot.recent_dm_users) if hasattr(self.bot, 'recent_dm_users') else 0
            
            await ctx.send(
                "📢 **Broadcast System**\n\n"
                "Send announcements to all servers and currently active DMs.\n\n"
                "**Usage:** `!broadcast [message]`\n\n"
                "**Example:** `!broadcast 🌱 Seedkeeper will be offline for maintenance at 3 PM EST for approximately 15 minutes.`\n\n"
                "**Current Stats:**\n"
                f"• Servers: {len(self.bot.guilds)}\n"
                f"• Active DM conversations (last 10 minutes): {active_dm_count}\n\n"
                "*DMs are only sent to users actively chatting with the bot (within last 10 minutes) to notify those currently using it.*"
            )
            return
        
        # Count active DM users
        active_dm_count = len(self.bot.recent_dm_users) if hasattr(self.bot, 'recent_dm_users') else 0
        
        # Ask for confirmation
        confirm_msg = await ctx.send(
            "⚠️ **Broadcast Confirmation**\n\n"
            f"You're about to broadcast to:\n"
            f"• {len(self.bot.guilds)} servers\n"
            f"• {active_dm_count} users currently in DM conversations (last 10 min)\n\n"
            f"**Message:**\n{message[:500]}{'...' if len(message) > 500 else ''}\n\n"
            f"React with ✅ to confirm or ❌ to cancel."
        )
        
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in ["✅", "❌"] and
                   reaction.message.id == confirm_msg.id)
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await confirm_msg.edit(content="*Broadcast cancelled.*")
                return
            
            await confirm_msg.edit(content="*Broadcasting message across The Garden...*")
            
        except asyncio.TimeoutError:
            await confirm_msg.edit(content="*Broadcast timed out - no message sent.*")
            return
        
        # Prepare broadcast message with header
        broadcast_content = (
            "🌱 **Garden Announcement** 🌱\n\n"
            f"{message}\n\n"
            f"*~ Message from the Garden Keepers*"
        )
        
        # Track results
        servers_sent = 0
        channels_sent = 0
        dms_sent = 0
        dms_failed = 0
        
        # Broadcast to all servers
        for guild in self.bot.guilds:
            sent_to_guild = False
            
            # Try to find appropriate channel (announcement, general, or first available)
            target_channel = None
            
            # First priority: announcement channels
            for channel in guild.text_channels:
                if 'announce' in channel.name.lower() or 'news' in channel.name.lower():
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
            
            # Second priority: general channels
            if not target_channel:
                for channel in guild.text_channels:
                    if 'general' in channel.name.lower() or 'chat' in channel.name.lower():
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break
            
            # Last resort: first channel we can write to
            if not target_channel:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
            
            if target_channel:
                try:
                    await target_channel.send(broadcast_content)
                    servers_sent += 1
                    channels_sent += 1
                    sent_to_guild = True
                except Exception as e:
                    print(f"Failed to send to {guild.name} - {channel.name}: {e}")
        
        # Broadcast to active DMs
        # We'll track recent DM users through a simple cache
        if hasattr(self.bot, 'recent_dm_users'):
            for user_id in list(self.bot.recent_dm_users):
                try:
                    user = self.bot.get_user(user_id)
                    if user and not user.bot:
                        await user.send(broadcast_content)
                        dms_sent += 1
                        await asyncio.sleep(0.1)  # Rate limiting
                except discord.Forbidden:
                    dms_failed += 1
                except Exception as e:
                    print(f"Failed to DM user {user_id}: {e}")
                    dms_failed += 1
        
        # Report results
        result_msg = (
            "🌿 **Broadcast Complete** 🌿\n\n"
            f"• Servers reached: {servers_sent}/{len(self.bot.guilds)}\n"
            f"• Channels used: {channels_sent}\n"
            f"• DMs sent: {dms_sent}\n"
        )
        
        if dms_failed > 0:
            result_msg += f"• DMs failed: {dms_failed}\n"
        
        result_msg += "\n*The message has been carried on the garden's winds.*"
        
        await ctx.send(result_msg)