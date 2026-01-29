#!/usr/bin/env python3
"""
Seedkeeper Bot - Unified Discord bot for The Garden Cafe
Single-process architecture: direct Discord connection with local Ollama API
No Redis, no external APIs - just pure bot love
"""

import asyncio
import discord
from discord.ext import commands
import os
import sys
import time
import random
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from admin_manager import AdminManager
from birthday_manager import BirthdayManager
from nlp_processor import NLPProcessor
from memory_manager import MemoryManager
from usage_tracker import UsageTracker
from prompt_compiler import PromptCompiler
from views_manager import ViewsManager
from feedback_manager import FeedbackManager
from personality_manager import PersonalityManager
from model_client import ModelClient
from rate_limiter import RateLimiter
from commands import COMMANDS, resolve_command, generate_commands_reference
from handlers import (
    GardenHandler, ConversationHandler, CatchupHandler,
    BirthdayHandler, MemoryHandler, AdminHandler,
    CostHandler, FeedbackHandler, PersonalityHandler,
    CommandsListHandler, HealthHandler,
)

load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
BOT_OWNER_ID = os.getenv('BOT_OWNER_ID')

if not DISCORD_TOKEN:
    print("DISCORD_BOT_TOKEN not set in environment")
    exit(1)


class SeedkeeperBot(commands.Bot):
    """Unified Seedkeeper bot - single-process Discord connection with local Ollama API"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.reactions = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)

        # Prompt compiler
        self.prompt_compiler = PromptCompiler()

        # Views manager (replaces PerspectiveCache)
        self._views_manager = ViewsManager()
        self._views_manager.parse_views()

        # Bot components
        self.admin_manager = AdminManager('data')
        self.birthday_manager = BirthdayManager('data')
        self.memory_manager = MemoryManager('data')
        self.feedback_manager = FeedbackManager('data')
        self.nlp_processor = NLPProcessor()
        self.usage_tracker = UsageTracker('data')
        self.personality_manager = PersonalityManager('data')
        self.model_client = ModelClient()
        self.rate_limiter = RateLimiter('data')

        # Set initial owner
        if BOT_OWNER_ID and BOT_OWNER_ID.isdigit():
            self.admin_manager.add_admin(BOT_OWNER_ID)

        # In-memory state (replaces Redis)
        self._dm_conversations = {}  # author_id -> list of messages
        self._temp_state = {}        # key -> (value, expiry_timestamp)

        # Track startup time
        self._started_at = time.time()

        # Initialize handler classes
        self._garden = GardenHandler(self)
        self._conversation = ConversationHandler(self)
        self._catchup = CatchupHandler(self)
        self._birthday = BirthdayHandler(self)
        self._memory = MemoryHandler(self)
        self._admin = AdminHandler(self)
        self._cost = CostHandler(self)
        self._feedback = FeedbackHandler(self)
        self._personality = PersonalityHandler(self)
        self._commands_list = CommandsListHandler(self)
        self._health = HealthHandler(self)

        # Build dispatch map from registry
        handler_objects = [
            self._garden, self._conversation, self._catchup,
            self._birthday, self._memory, self._admin,
            self._cost, self._feedback, self._personality,
            self._commands_list, self._health,
        ]
        self._handler_map = {}
        for cmd_name, cmd_info in COMMANDS.items():
            for handler_obj in handler_objects:
                method = getattr(handler_obj, cmd_info.handler, None)
                if method:
                    self._handler_map[cmd_name] = method
                    break
            else:
                print(f"[WARN] No handler found for command '{cmd_name}' (expected method: {cmd_info.handler})")

    # ── Temp state ───────────────────────────────────────────────

    def _set_temp(self, key: str, value: Any, ttl: int = 300):
        """Store temporary state with TTL"""
        self._temp_state[key] = (value, time.time() + ttl)

    def _get_temp(self, key: str) -> Optional[Any]:
        """Get temporary state if not expired"""
        entry = self._temp_state.get(key)
        if entry and entry[1] > time.time():
            return entry[0]
        self._temp_state.pop(key, None)
        return None

    def _del_temp(self, key: str):
        """Delete temporary state"""
        self._temp_state.pop(key, None)

    async def _cleanup_temp_state(self):
        """Periodically evict expired entries from _temp_state"""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            now = time.time()
            expired = [k for k, (_, expiry) in self._temp_state.items() if expiry <= now]
            for k in expired:
                del self._temp_state[k]
            if expired:
                print(f"[TempState] Evicted {len(expired)} expired entries")

    # ── Helpers ──────────────────────────────────────────────────

    async def _get_guild_members(self, guild_id) -> List[Dict]:
        """Get guild members as dict list, always fetching from API"""
        if not guild_id:
            print("[Guild] No guild_id provided")
            return []

        guild = self.get_guild(int(guild_id))
        if not guild:
            print(f"[Guild] Could not find guild {guild_id}")
            return []

        # Always fetch members from API (requires members intent)
        try:
            members = []
            async for member in guild.fetch_members(limit=None):
                if not member.bot:
                    members.append({
                        'id': str(member.id),
                        'name': member.name,
                        'nick': member.nick or '',
                        'display_name': member.display_name
                    })
            print(f"[Guild] Fetched {len(members)} members from {guild.name}")
            return members
        except Exception as e:
            print(f"[Guild] Error fetching members: {e}")
            # Fall back to cached members
            cached = [{
                'id': str(m.id),
                'name': m.name,
                'nick': m.nick or '',
                'display_name': m.display_name
            } for m in guild.members if not m.bot]
            print(f"[Guild] Falling back to {len(cached)} cached members")
            return cached

    def _get_random_perspectives(self, count: int = 2) -> List[str]:
        """Get random perspectives using ViewsManager"""
        all_perspectives = self._views_manager.get_all_perspectives()
        if not all_perspectives:
            return []
        selected = random.sample(all_perspectives, min(count, len(all_perspectives)))
        return [text for name, text in selected]

    # ── Discord events ───────────────────────────────────────────

    async def on_ready(self):
        """Called when bot connects to Discord"""
        print(f'Seedkeeper Online: {self.user}')
        print(f'Connected to {len(self.guilds)} guilds')
        print(f'User ID: {self.user.id}')
        print(f'Local Ollama architecture (no external APIs)')

        for guild in self.guilds:
            print(f'  - Guild: {guild.name} (ID: {guild.id})')

        # Start background cleanup task for expired temp state
        self.loop.create_task(self._cleanup_temp_state())

        print(f'Ready to serve The Garden Cafe community')

    async def on_message(self, message):
        """Handle all incoming messages"""
        if message.author == self.user:
            return

        content = message.content.strip()
        is_dm = isinstance(message.channel, discord.DMChannel)

        # Build command_data dict (same shape handlers expect)
        command_data = {
            'type': 'message',
            'message_id': str(message.id),
            'channel_id': str(message.channel.id),
            'channel_topic': getattr(message.channel, 'topic', None),
            'guild_id': str(message.guild.id) if message.guild else None,
            'author_id': str(message.author.id),
            'author_name': str(message.author),
            'content': content,
            'is_dm': is_dm,
            'is_mention': self.user.mentioned_in(message),
            'timestamp': message.created_at.isoformat()
        }

        # Handle commands
        if content.startswith('!'):
            parts = content[1:].split(maxsplit=1)
            raw_cmd = parts[0].lower() if parts else ''
            cmd = resolve_command(raw_cmd) or raw_cmd

            command_data['type'] = 'command'
            command_data['command'] = cmd
            command_data['args'] = parts[1] if len(parts) > 1 else ''
            await self.handle_discord_command(command_data)
            return

        # Store user message in memory
        author_id = str(message.author.id)
        if self.memory_manager.is_memory_enabled(author_id):
            channel_type = 'dm' if is_dm else 'guild'
            self.memory_manager.add_memory(
                author_id, content, 'user', channel_type,
                command_data['guild_id'], command_data['channel_id']
            )

        # NLP processing for DMs and mentions
        if (is_dm or command_data['is_mention']) and not content.startswith('!'):
            intent = self.nlp_processor.process_message(content)
            if intent and intent.confidence >= 0.7:
                nlp_data = dict(command_data)
                nlp_data.update({
                    'type': 'command',
                    'command': intent.command,
                    'args': ' '.join(intent.args) if intent.args else '',
                    'is_nlp': True,
                    'original_message': content,
                })
                await self.handle_discord_command(nlp_data)
                return

        # Handle DM conversations
        if is_dm and not content.startswith('!'):
            await self._conversation.handle_dm_conversation(command_data)
            return

        # Handle mentions
        if command_data['is_mention'] and not content.startswith('!'):
            await self._conversation.handle_mention_conversation(command_data)

    # ── Message utilities ────────────────────────────────────────

    def split_message(self, content: str, max_length: int = 1900) -> List[str]:
        """Split long messages into chunks"""
        if len(content) <= max_length:
            return [content]

        chunks = []
        current = ""

        for line in content.split('\n'):
            if len(current) + len(line) + 1 > max_length:
                if current:
                    chunks.append(current)
                current = line
            else:
                if current:
                    current += '\n' + line
                else:
                    current = line

        if current:
            chunks.append(current)

        return chunks

    async def send_message(self, channel_id: str, content: str, is_dm: bool = False,
                          author_id: Optional[str] = None, embed=None):
        """Send message directly to Discord channel"""
        channel = None
        if is_dm and author_id:
            try:
                user = self.get_user(int(author_id)) or await self.fetch_user(int(author_id))
                channel = user.dm_channel or await user.create_dm()
            except Exception as e:
                print(f"Error getting DM channel: {e}")
                return
        else:
            try:
                channel = self.get_channel(int(channel_id))
            except Exception as e:
                print(f"Error getting channel: {e}")
                return

        if not channel:
            print(f"Could not find channel {channel_id}")
            return

        # Auto-split long messages
        if len(content) > 1900:
            chunks = self.split_message(content, 1900)
            for i, chunk in enumerate(chunks):
                kwargs = {'content': chunk}
                if embed and i == 0:
                    if isinstance(embed, dict):
                        kwargs['embed'] = discord.Embed.from_dict(embed)
                    else:
                        kwargs['embed'] = embed
                await channel.send(**kwargs)
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)
        else:
            kwargs = {'content': content}
            if embed:
                if isinstance(embed, dict):
                    kwargs['embed'] = discord.Embed.from_dict(embed)
                else:
                    kwargs['embed'] = embed
            await channel.send(**kwargs)

    async def send_typing(self, channel_id: str, is_dm: bool = False,
                         author_id: Optional[str] = None, duration: int = 3):
        """Show typing indicator"""
        channel = None
        if is_dm and author_id:
            try:
                user = self.get_user(int(author_id)) or await self.fetch_user(int(author_id))
                channel = user.dm_channel or await user.create_dm()
            except:
                pass
        else:
            try:
                channel = self.get_channel(int(channel_id))
            except:
                pass

        if channel:
            async with channel.typing():
                await asyncio.sleep(duration)

    # ── System prompts ───────────────────────────────────────────

    def _get_system_for_personality(self, personality: dict, **kwargs) -> str:
        """Get system prompt for the personality with dynamic injections."""
        # Start with personality's base prompt
        base_prompt = personality.get('system_prompt', 'You are a helpful assistant.')

        # Inject auto-generated commands reference
        commands_ref = generate_commands_reference()
        full_prompt = f"{base_prompt}\n\n{commands_ref}"

        # Add channel context if available
        channel_topic = kwargs.get('channel_topic')
        if channel_topic:
            full_prompt += f"\n\nCurrent channel topic: {channel_topic}"

        return full_prompt

    # ── Usage tracking ───────────────────────────────────────────

    def _record_api_usage_from_result(self, result, command_type: str,
                                      user_id: Optional[str] = None, channel_id: Optional[str] = None):
        """Record API usage from a CompletionResult"""
        try:
            self.usage_tracker.record_usage(
                model=result.model,
                command_type=command_type,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                user_id=user_id,
                channel_id=channel_id,
                is_local=result.is_local,
            )
        except Exception as e:
            print(f"[UsageTracker] Failed to record usage: {e}")

    # ── Command dispatch ─────────────────────────────────────────

    async def handle_discord_command(self, command_data: Dict[str, Any]):
        """Handle Discord commands (!command) using the commands registry."""
        command = command_data.get('command', '')
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)

        # Show typing indicator
        await self.send_typing(channel_id, is_dm=is_dm, author_id=author_id)

        # Look up command in registry
        cmd_info = COMMANDS.get(command)
        if not cmd_info:
            await self._commands_list.handle_unknown_command(command_data)
            return

        # Check admin permissions
        if cmd_info.admin_only and not self.admin_manager.is_admin(str(author_id)):
            await self.send_message(channel_id,
                "You need Garden Keeper permissions for that command.",
                is_dm=is_dm, author_id=str(author_id))
            return

        # Dispatch to handler method
        handler = self._handler_map.get(command)
        if handler:
            await handler(command_data)
        else:
            await self._commands_list.handle_unknown_command(command_data)


async def main():
    """Run the unified bot"""
    bot = SeedkeeperBot()
    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
