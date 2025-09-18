#!/usr/bin/env python3
"""
Memory Commands for Seedkeeper
User commands for managing persistent conversation memory
"""

import discord
from discord.ext import commands
from typing import Optional
import json
from datetime import datetime
from .memory_manager import MemoryManager

class MemoryCommands(commands.Cog):
    """Commands for managing persistent user memory"""
    
    def __init__(self, bot, redis_client):
        self.bot = bot
        self.memory_manager = MemoryManager(redis_client)
        
        # Store reference in bot for other cogs to use
        if not hasattr(bot, 'memory_manager'):
            bot.memory_manager = self.memory_manager
    
    @commands.group(name='memory', invoke_without_command=True)
    async def memory(self, ctx):
        """
        Manage your persistent conversation memory
        """
        # Show memory status and help
        user_id = str(ctx.author.id)
        stats = self.memory_manager.get_memory_stats(user_id)
        
        if stats["enabled"]:
            status_msg = "🧠 **Your Memory Status**\n\n"
            status_msg += f"✅ Memory is **enabled** for you\n"
            status_msg += f"📚 Total memories: **{stats['total_memories']}** / {stats['max_memories']}\n"
            
            if stats["total_memories"] > 0:
                oldest_dt = datetime.fromisoformat(stats["oldest_memory"])
                newest_dt = datetime.fromisoformat(stats["newest_memory"])
                
                status_msg += f"📅 Oldest memory: {oldest_dt.strftime('%Y-%m-%d')}\n"
                status_msg += f"📅 Latest memory: {newest_dt.strftime('%Y-%m-%d')}\n"
                status_msg += f"⏰ History span: {stats['days_of_history']} days\n"
                status_msg += f"💬 DM memories: {stats['dm_memories']}\n"
                status_msg += f"🏛️ Server memories: {stats['guild_memories']}\n"
            
            status_msg += "\n**Available Commands:**\n"
            status_msg += "• `!memory disable` - Turn off memory (keeps existing)\n"
            status_msg += "• `!memory clear` - Clear all your memories\n"
            status_msg += "• `!memory export` - Export your memories\n"
            status_msg += "• `!memory recent [n]` - Show last n memories\n"
            status_msg += "• `!memory search [text]` - Search your memories\n"
            status_msg += "• `!memory settings` - View/change settings\n"
        else:
            status_msg = "🧠 **Memory is currently disabled for you**\n\n"
            status_msg += "I'm not storing our conversations long-term.\n\n"
            status_msg += "**Enable memory to:**\n"
            status_msg += "• Have me remember our conversations forever\n"
            status_msg += "• Build a relationship over time\n"
            status_msg += "• Get personalized responses based on our history\n\n"
            status_msg += "**Commands:**\n"
            status_msg += "• `!memory enable` - Start remembering\n"
            status_msg += "• `!memory info` - Learn more about memory\n"
        
        status_msg += "\n*Your memories are private and only accessible by you.*"
        await ctx.send(status_msg)
    
    @memory.command(name='enable')
    async def memory_enable(self, ctx, max_memories: Optional[int] = None):
        """Enable persistent memory for your conversations"""
        user_id = str(ctx.author.id)
        
        if self.memory_manager.is_memory_enabled(user_id):
            await ctx.send("🧠 Memory is already enabled for you!")
            return
        
        self.memory_manager.enable_memory(user_id, max_memories)
        
        await ctx.send(
            "🌱 **Memory Enabled!**\n\n"
            "I'll now remember our conversations permanently.\n"
            "Our shared history will grow deeper over time.\n\n"
            "• Memories are stored privately and securely\n"
            "• You can clear them anytime with `!memory clear`\n"
            "• Check status anytime with `!memory`\n\n"
            "*Let's build something beautiful together.* 🌿"
        )
    
    @memory.command(name='disable')
    async def memory_disable(self, ctx, delete: Optional[str] = None):
        """
        Disable memory (optionally delete existing memories)
        Use: !memory disable [delete]
        """
        user_id = str(ctx.author.id)
        
        if not self.memory_manager.is_memory_enabled(user_id):
            await ctx.send("🧠 Memory is already disabled for you.")
            return
        
        delete_existing = delete and delete.lower() in ['delete', 'clear', 'remove']
        
        self.memory_manager.disable_memory(user_id, keep_existing=not delete_existing)
        
        if delete_existing:
            await ctx.send(
                "🍂 **Memory Disabled & Cleared**\n\n"
                "I've stopped remembering and cleared our past conversations.\n"
                "We'll start fresh each time we talk.\n\n"
                "*Sometimes letting go creates space for new growth.* 🌱"
            )
        else:
            await ctx.send(
                "🍂 **Memory Disabled**\n\n"
                "I've stopped adding new memories.\n"
                "Your existing memories are preserved and can be re-enabled.\n\n"
                "Use `!memory enable` to resume remembering.\n"
                "*Taking a break is perfectly okay.* 🌿"
            )
    
    @memory.command(name='clear')
    async def memory_clear(self, ctx):
        """Clear all your stored memories"""
        user_id = str(ctx.author.id)
        stats = self.memory_manager.get_memory_stats(user_id)
        
        if stats["total_memories"] == 0:
            await ctx.send("🌱 You don't have any memories stored yet.")
            return
        
        # Confirm before clearing
        confirm_msg = await ctx.send(
            f"⚠️ **Confirm Memory Clear**\n\n"
            f"This will permanently delete {stats['total_memories']} memories "
            f"spanning {stats['days_of_history']} days.\n\n"
            f"React with ✅ to confirm or ❌ to cancel."
        )
        
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in ["✅", "❌"] and
                   reaction.message.id == confirm_msg.id)
        
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                self.memory_manager.clear_user_memory(user_id)
                await ctx.send(
                    "🌊 **Memories Cleared**\n\n"
                    "Your conversation history has been washed clean.\n"
                    "We begin anew, carrying only this moment forward.\n\n"
                    "*Every garden needs fresh soil sometimes.* 🌱"
                )
            else:
                await ctx.send("*Memory clear cancelled. Your memories remain safe.* 🌿")
        
        except:
            await ctx.send("*Memory clear cancelled (timeout). Your memories remain safe.* 🌿")
    
    @memory.command(name='recent')
    async def memory_recent(self, ctx, limit: Optional[int] = 5):
        """Show your recent memories"""
        user_id = str(ctx.author.id)
        
        if not self.memory_manager.is_memory_enabled(user_id):
            await ctx.send("🧠 Memory is disabled. Use `!memory enable` to start remembering.")
            return
        
        memories = self.memory_manager.get_recent_memories(user_id, min(limit, 10))
        
        if not memories:
            await ctx.send("🌱 No memories found yet. Let's create some together!")
            return
        
        msg = "🧠 **Recent Memories**\n\n"
        
        for memory in memories:
            timestamp = datetime.fromisoformat(memory["timestamp"])
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
            author = "You" if memory["author"] == "user" else "Me"
            content = memory["content"]
            
            # Truncate long messages
            if len(content) > 100:
                content = content[:97] + "..."
            
            channel_type = "DM" if memory["channel_type"] == "dm" else "Server"
            msg += f"**[{time_str}]** ({channel_type}) {author}: {content}\n"
        
        msg += "\n*These moments form the tapestry of our connection.* 🌿"
        
        # Split into multiple messages if too long
        if len(msg) > 1900:
            chunks = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(msg)
    
    @memory.command(name='search')
    async def memory_search(self, ctx, *, query: str):
        """Search through your memories"""
        user_id = str(ctx.author.id)
        
        if not self.memory_manager.is_memory_enabled(user_id):
            await ctx.send("🧠 Memory is disabled. Use `!memory enable` to start remembering.")
            return
        
        memories = self.memory_manager.get_context_memories(user_id, query, limit=5)
        
        if not memories:
            await ctx.send(f"🔍 No memories found matching '{query}'")
            return
        
        msg = f"🔍 **Memories matching '{query}'**\n\n"
        
        for memory in memories:
            timestamp = datetime.fromisoformat(memory["timestamp"])
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
            author = "You" if memory["author"] == "user" else "Me"
            content = memory["content"]
            
            # Highlight matching parts (simple approach)
            for word in query.split():
                if word.lower() in content.lower():
                    content = content.replace(word, f"**{word}**")
            
            # Truncate if needed
            if len(content) > 150:
                content = content[:147] + "..."
            
            msg += f"[{time_str}] {author}: {content}\n\n"
        
        msg += "*Found these echoes in our shared history.* 🌿"
        await ctx.send(msg)
    
    @memory.command(name='export')
    async def memory_export(self, ctx, format: Optional[str] = "text"):
        """
        Export your memories
        Formats: text, json, markdown
        """
        user_id = str(ctx.author.id)
        stats = self.memory_manager.get_memory_stats(user_id)
        
        if stats["total_memories"] == 0:
            await ctx.send("🌱 You don't have any memories to export yet.")
            return
        
        format = format.lower()
        if format not in ["text", "json", "markdown"]:
            await ctx.send("Format must be: text, json, or markdown")
            return
        
        export_data = self.memory_manager.export_user_memories(user_id, format)
        
        if not export_data:
            await ctx.send("❌ Failed to export memories.")
            return
        
        # Determine file extension
        extensions = {"text": "txt", "json": "json", "markdown": "md"}
        ext = extensions.get(format, "txt")
        
        # Create file
        filename = f"memories_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        
        # Send as file (Discord has 8MB limit, our export should be well under)
        file = discord.File(
            io.BytesIO(export_data.encode()),
            filename=filename
        )
        
        await ctx.send(
            f"📚 **Memory Export Complete**\n\n"
            f"Format: {format}\n"
            f"Memories: {stats['total_memories']}\n"
            f"Time span: {stats['days_of_history']} days\n\n"
            f"*Your story, preserved in digital amber.* 🌿",
            file=file
        )
    
    @memory.command(name='settings')
    async def memory_settings(self, ctx, setting: Optional[str] = None, value: Optional[str] = None):
        """
        View or change memory settings
        Settings: max_memories, auto_summarize
        """
        user_id = str(ctx.author.id)
        
        if not self.memory_manager.is_memory_enabled(user_id):
            await ctx.send("🧠 Memory is disabled. Use `!memory enable` first.")
            return
        
        user_settings = self.memory_manager.settings["enabled_users"].get(user_id, {})
        
        if not setting:
            # Show current settings
            msg = "⚙️ **Your Memory Settings**\n\n"
            msg += f"• **Max memories**: {user_settings.get('max_memories', 100)}\n"
            msg += f"• **Auto-summarize**: {user_settings.get('auto_summarize', True)}\n"
            
            if "enabled_at" in user_settings:
                enabled_dt = datetime.fromisoformat(user_settings["enabled_at"])
                msg += f"• **Enabled since**: {enabled_dt.strftime('%Y-%m-%d')}\n"
            
            msg += "\n**To change:**\n"
            msg += "• `!memory settings max_memories [number]`\n"
            msg += "• `!memory settings auto_summarize [true/false]`\n"
            
            await ctx.send(msg)
            return
        
        setting = setting.lower()
        
        if setting == "max_memories":
            if not value or not value.isdigit():
                await ctx.send("Please provide a number (e.g., `!memory settings max_memories 200`)")
                return
            
            new_max = int(value)
            if new_max < 10:
                await ctx.send("Minimum is 10 memories.")
                return
            if new_max > 1000:
                await ctx.send("Maximum is 1000 memories.")
                return
            
            user_settings["max_memories"] = new_max
            self.memory_manager.settings["enabled_users"][user_id] = user_settings
            self.memory_manager.save_settings()
            
            await ctx.send(f"✅ Max memories set to **{new_max}**")
        
        elif setting == "auto_summarize":
            if not value or value.lower() not in ["true", "false", "yes", "no", "on", "off"]:
                await ctx.send("Please use true/false (e.g., `!memory settings auto_summarize false`)")
                return
            
            enabled = value.lower() in ["true", "yes", "on"]
            user_settings["auto_summarize"] = enabled
            self.memory_manager.settings["enabled_users"][user_id] = user_settings
            self.memory_manager.save_settings()
            
            status = "enabled" if enabled else "disabled"
            await ctx.send(f"✅ Auto-summarization **{status}**")
        
        else:
            await ctx.send(f"Unknown setting '{setting}'. Available: max_memories, auto_summarize")
    
    @memory.command(name='info')
    async def memory_info(self, ctx):
        """Learn about how memory works"""
        info_msg = """
🧠 **How Memory Works in Seedkeeper**

**What is stored:**
• Your messages and my responses
• Timestamps and context
• Whether it was in DM or server

**What is NOT stored:**
• Deleted messages
• Messages from other users to me
• Sensitive data (automatically filtered)

**Privacy & Security:**
• Your memories are private to you
• Stored locally on the server
• You can delete them anytime
• Admins cannot read your memories

**How it enhances our interaction:**
• I remember past conversations
• I can reference shared experiences  
• Our relationship grows over time
• Context carries between sessions

**Limits:**
• Default: 100 memories per user
• Older memories auto-summarize
• You can adjust limits in settings

*Memory makes our garden grow deeper roots.* 🌿
        """
        await ctx.send(info_msg)

# Import for easier access
import io