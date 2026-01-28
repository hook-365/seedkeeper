#!/usr/bin/env python3
"""
Seedkeeper Bot - Unified Discord bot for The Garden Cafe
Single-process architecture: direct Discord connection with Claude API
No Redis, no worker queue - just pure bot love
"""

import asyncio
import discord
from discord.ext import commands
import json
import os
import sys
import time
import re
import random
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from collections import defaultdict

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

load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
BOT_OWNER_ID = os.getenv('BOT_OWNER_ID')

if not DISCORD_TOKEN:
    print("❌ DISCORD_BOT_TOKEN not set in environment")
    exit(1)

# Import Anthropic
try:
    import anthropic
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
except ImportError:
    print("❌ Anthropic not installed: pip install anthropic")
    anthropic_client = None


class SeedkeeperBot(commands.Bot):
    """Unified Seedkeeper bot - single-process Discord connection with Claude API"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.reactions = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)

        # Claude API
        self.anthropic = anthropic_client

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

        # Set initial owner
        if BOT_OWNER_ID and BOT_OWNER_ID.isdigit():
            self.admin_manager.add_admin(BOT_OWNER_ID)

        # In-memory state (replaces Redis)
        self._dm_conversations = {}  # author_id -> list of messages
        self._temp_state = {}        # key -> (value, expiry_timestamp)

        # Track startup time
        self._started_at = time.time()

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

    def _get_guild_members(self, guild_id: int) -> List[Dict]:
        """Get guild members as dict list"""
        guild = self.get_guild(int(guild_id))
        if not guild:
            return []
        return [{
            'id': str(m.id),
            'name': m.name,
            'nick': m.nick or '',
            'display_name': m.display_name
        } for m in guild.members if not m.bot]

    def _get_random_perspectives(self, count: int = 2) -> List[str]:
        """Get random perspectives using ViewsManager"""
        all_perspectives = self._views_manager.get_all_perspectives()
        if not all_perspectives:
            return []
        selected = random.sample(all_perspectives, min(count, len(all_perspectives)))
        return [text for name, text in selected]

    async def on_ready(self):
        """Called when bot connects to Discord"""
        print(f'🌱 Seedkeeper Online: {self.user}')
        print(f'📡 Connected to {len(self.guilds)} guilds')
        print(f'🔍 User ID: {self.user.id}')
        print(f'🎯 Single-process architecture (no Redis)')

        for guild in self.guilds:
            print(f'  └─ Guild: {guild.name} (ID: {guild.id})')

        print(f'✅ Ready to serve The Garden Cafe community')

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
            cmd = parts[0].lower() if parts else ''

            COMMAND_ALIASES = {
                'whoami': 'about', 'whoareyou': 'about',
                'hi': 'hello', 'intro': 'hello'
            }
            if cmd in COMMAND_ALIASES:
                cmd = COMMAND_ALIASES[cmd]

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
                nlp_data = {
                    'command': intent.command,
                    'args': ' '.join(intent.args) if intent.args else '',
                    'author_id': author_id,
                    'channel_id': str(message.channel.id),
                    'is_dm': is_dm,
                    'is_nlp': True,
                    'original_message': content,
                    'guild_id': command_data['guild_id'],
                    'channel_topic': command_data['channel_topic']
                }
                await self.handle_discord_command(nlp_data)
                return

        # Handle DM conversations
        if is_dm and not content.startswith('!'):
            await self.handle_dm_conversation(command_data)
            return

        # Handle mentions
        if command_data['is_mention'] and not content.startswith('!'):
            await self.handle_mention_conversation(command_data)

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

    def _select_model(self, message_content: str, is_dm: bool = False, is_command: bool = False) -> str:
        """
        Select appropriate model based on interaction complexity.

        Haiku (~73% cheaper): Simple commands, short messages, template responses
        Sonnet (full depth): Deep conversations, complex queries, emergence needed
        """
        # Simple commands always use Haiku
        simple_commands = ['!hello', '!hi', '!seeds', '!garden', '!tend', '!help']
        if any(message_content.strip().lower().startswith(cmd) for cmd in simple_commands):
            return 'claude-haiku-4-5-20251001'

        # Complex commands use Sonnet
        complex_commands = ['!catchup', '!feedback', '!admin', '!birthday scan']
        if any(message_content.strip().lower().startswith(cmd) for cmd in complex_commands):
            return 'claude-sonnet-4-5-20250929'

        # Memory status is factual - use Haiku
        if message_content.strip().lower().startswith('!memory status'):
            return 'claude-haiku-4-5-20251001'

        # Short messages (<10 words) use Haiku unless they're questions
        word_count = len(message_content.split())
        if word_count < 10:
            if '?' in message_content:
                return 'claude-sonnet-4-5-20250929'
            return 'claude-haiku-4-5-20251001'

        # DMs with depth use Sonnet
        if is_dm and word_count > 15:
            return 'claude-sonnet-4-5-20250929'

        # Questions and deeper engagement use Sonnet
        depth_indicators = ['?', 'how', 'why', 'what if', 'help me', 'i feel', 'i am', "i'm", 'tell me about']
        if any(indicator in message_content.lower() for indicator in depth_indicators):
            return 'claude-sonnet-4-5-20250929'

        # Default to Haiku for efficiency
        return 'claude-haiku-4-5-20251001'

    def _record_api_usage(self, response, model: str, command_type: str,
                          user_id: Optional[str] = None, channel_id: Optional[str] = None):
        """Record API usage from a Claude response"""
        try:
            usage = response.usage
            self.usage_tracker.record_usage(
                model=model,
                command_type=command_type,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                user_id=user_id,
                channel_id=channel_id,
            )
        except Exception as e:
            print(f"[UsageTracker] Failed to record usage: {e}")

    def _create_system_messages(self, channel_topic: Optional[str] = None, is_dm: bool = False) -> list:
        """Create layered system messages for multi-block caching"""
        background_context = {}
        if channel_topic:
            background_context['channel_topic'] = channel_topic

        return self.prompt_compiler.compile_messages(
            background_context=background_context,
            foreground_context=None
        )

    async def handle_discord_command(self, command_data: Dict[str, Any]):
        """Handle Discord commands (!command)"""
        command = command_data.get('command', '')
        args = command_data.get('args', '')
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)

        # Show typing indicator
        await self.send_typing(channel_id, is_dm=is_dm, author_id=author_id)

        # Route command to appropriate handler
        if command == 'catchup':
            await self.handle_catchup(command_data)
        elif command == 'birthday':
            await self.handle_birthday_command(command_data)
        elif command in ['admin', 'config', 'reload', 'status', 'health', 'update-bot']:
            await self.handle_admin_command(command_data)
        elif command in ['seeds', 'tend', 'seasons', 'garden', 'hello', 'about']:
            await self.handle_garden_command(command_data)
        elif command == 'memory':
            await self.handle_memory_command(command_data)
        elif command == 'forgetme':
            await self.handle_forgetme_command(command_data)
        elif command == 'cost':
            await self.handle_cost_command(command_data)
        elif command == 'feedback':
            await self.handle_feedback_command(command_data)
        elif command == 'commands':
            await self.handle_commands_list(command_data)
        else:
            await self.handle_unknown_command(command_data)

    async def handle_dm_conversation(self, message_data: Dict[str, Any]):
        """Handle natural DM conversations"""
        author_id = message_data.get('author_id')
        content = message_data.get('content', '')
        channel_id = message_data.get('channel_id')

        # Send typing indicator while processing
        await self.send_typing(channel_id, is_dm=True, author_id=author_id, duration=5)

        # Check if there's an active feedback session
        if author_id in self.feedback_manager.sessions:
            # Check for cancel command
            if content.lower() in ['cancel', 'stop', 'exit', 'quit']:
                self.feedback_manager.cancel_session(author_id)
                await self.send_message(channel_id,
                    "🌿 Feedback session cancelled. Feel free to start a new one anytime with `!feedback`",
                    is_dm=True, author_id=author_id)
                return

            result = self.feedback_manager.process_feedback_response(author_id, content)

            if result.get('complete'):
                await self.send_message(channel_id, result['message'], is_dm=True, author_id=author_id)

                if result.get('success') and os.getenv('BOT_OWNER_ID') == author_id:
                    pending = self.feedback_manager.get_pending_feedback_for_owner()
                    if pending:
                        feedback_text = "📬 **New Anonymous Feedback:**\n"
                        for item in pending:
                            feedback_text += f"\n**Feature:** {item['feature']}\n"
                            feedback_text += f"**Interest:** {item['interest']}\n"
                            feedback_text += f"**Details:** {item['details']}\n"
                            feedback_text += "---\n"
                        await self.send_message(channel_id, feedback_text[:1900], is_dm=True, author_id=author_id)
            else:
                await self.send_message(channel_id, result.get('next_prompt', result.get('message')),
                                      is_dm=True, author_id=author_id)
            return

        # Get conversation history from in-memory store
        conversation = self._dm_conversations.get(author_id, [])

        # Add persistent memories if enabled
        persistent_memories = []
        if self.memory_manager.is_memory_enabled(author_id):
            memories = self.memory_manager.get_recent_memories(author_id, limit=10)
            for mem in memories:
                role = 'user' if mem['author'] == 'user' else 'assistant'
                persistent_memories.append({
                    'role': role,
                    'content': mem['content']
                })

        # Check if this looks like birthday info
        birthday_keywords = ['birthday', 'born', 'birth', 'bday', 'born on', 'celebrate']
        if any(keyword in content.lower() for keyword in birthday_keywords):
            parsed_results = self.birthday_manager.parse_birthday_advanced(content)
            if parsed_results:
                for result in parsed_results:
                    if result.get('month') and result.get('day'):
                        success, message = self.birthday_manager.set_birthday(
                            str(author_id), result['month'], result['day'], str(author_id), method="auto"
                        )
                        if success:
                            formatted = self.birthday_manager.format_birthday_date(result['month'], result['day'])
                            await self.send_message(channel_id,
                                f"✨ I've noted your birthday as {formatted}! "
                                f"I'll remember to celebrate with you. 🎂",
                                is_dm=True, author_id=author_id)
                        else:
                            await self.send_message(channel_id, f"🌱 {message}",
                                is_dm=True, author_id=author_id)
                        return

        # Generate natural response using Claude
        if self.anthropic:
            try:
                context_messages = []

                if persistent_memories:
                    context_messages.extend(persistent_memories[:5])
                for msg in conversation[-5:]:
                    context_messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })

                context_messages.append({
                    "role": "user",
                    "content": content
                })

                selected_model = self._select_model(content, is_dm=True, is_command=False)
                system_messages = self._create_system_messages(is_dm=True)

                response = self.anthropic.messages.create(
                    model=selected_model,
                    max_tokens=800,
                    temperature=float(os.getenv('SEEDKEEPER_TEMPERATURE', '1.0')),
                    system=system_messages,
                    messages=context_messages
                )
                self._record_api_usage(response, selected_model, "dm",
                                       user_id=author_id, channel_id=channel_id)

                reply = response.content[0].text.strip()

                # Filter out pure emote responses
                emote_pattern = r'^[*_][^*_]+[*_]\s*$'
                if re.match(emote_pattern, reply):
                    context_messages.append({
                        "role": "assistant",
                        "content": reply
                    })
                    context_messages.append({
                        "role": "user",
                        "content": "Please respond with words, not actions."
                    })

                    retry_system = self._create_system_messages(is_dm=True)
                    retry_system[-1]["text"] += "\n\nREMINDER: The user has asked for a verbal response, not an action or emote. Respond with actual words and conversation."

                    response = self.anthropic.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=200,
                        temperature=0.8,
                        system=retry_system,
                        messages=context_messages
                    )
                    self._record_api_usage(response, "claude-sonnet-4-5-20250929", "dm_retry",
                                           user_id=author_id, channel_id=channel_id)
                    reply = response.content[0].text.strip()

                # Remove emote starts
                emote_start_pattern = r'^[*_][^*_]+[*_]\s+'
                reply = re.sub(emote_start_pattern, '', reply)

                # Send response
                if len(reply) <= 2000:
                    await self.send_message(channel_id, reply, is_dm=True, author_id=author_id)
                else:
                    chunks = self.split_message(reply)
                    for i, chunk in enumerate(chunks):
                        await self.send_message(channel_id, chunk, is_dm=True, author_id=author_id)
                        if i < len(chunks) - 1:
                            await asyncio.sleep(0.5)

                # Save to in-memory conversation
                conversation.append({'role': 'user', 'content': content[:500], 'timestamp': datetime.utcnow().isoformat()})
                conversation.append({'role': 'assistant', 'content': reply[:500], 'timestamp': datetime.utcnow().isoformat()})
                if len(conversation) > 10:
                    conversation = conversation[-10:]
                self._dm_conversations[author_id] = conversation

                # Save to persistent memory
                if self.memory_manager.is_memory_enabled(author_id):
                    self.memory_manager.add_memory(
                        author_id, reply[:2000], 'bot', 'dm', None, channel_id
                    )

            except Exception as e:
                print(f"Error in DM conversation: {e}")
                await self.send_message(channel_id,
                    "I'm having trouble processing that right now, but I'm here! 🌱",
                    is_dm=True, author_id=author_id)

    async def handle_mention_conversation(self, message_data: Dict[str, Any]):
        """Handle mentions that aren't clear commands"""
        author_id = message_data.get('author_id')
        content = message_data.get('content', '')
        channel_id = message_data.get('channel_id')
        guild_id = message_data.get('guild_id')
        channel_topic = message_data.get('channel_topic')

        await self.send_typing(channel_id)

        # Save to memory
        if self.memory_manager.is_memory_enabled(author_id):
            self.memory_manager.add_memory(
                author_id, content, 'user',
                'guild' if guild_id else 'dm', guild_id, channel_id
            )

        # Get channel-specific conversation context
        recent_messages = self.memory_manager.get_recent_memories(
            author_id, limit=10,
            channel_type='guild',
            guild_id=guild_id,
            channel_id=channel_id
        )

        # Generate response
        if self.anthropic:
            try:
                messages_for_claude = []
                if recent_messages:
                    for msg in recent_messages[-5:]:
                        role = 'user' if msg['author'] == 'user' else 'assistant'
                        messages_for_claude.append({
                            "role": role,
                            "content": msg['content']
                        })

                # Remove bot mention from content
                clean_content = content
                for mention_pattern in ['<@1409024527933112360>', '<@!1409024527933112360>']:
                    clean_content = clean_content.replace(mention_pattern, '').strip()

                messages_for_claude.append({
                    "role": "user",
                    "content": clean_content if clean_content else content
                })

                selected_model = self._select_model(clean_content or content, is_dm=False, is_command=False)
                system_messages = self._create_system_messages(channel_topic=channel_topic, is_dm=False)

                response = self.anthropic.messages.create(
                    model=selected_model,
                    max_tokens=2000,
                    temperature=float(os.getenv('SEEDKEEPER_TEMPERATURE', '1.0')),
                    system=system_messages,
                    messages=messages_for_claude
                )
                self._record_api_usage(response, selected_model, "mention",
                                       user_id=author_id, channel_id=channel_id)

                if response and response.content and len(response.content) > 0:
                    reply = response.content[0].text.strip()
                else:
                    reply = "I heard you, but my thoughts got tangled in the garden vines. Could you try again?"

                # Save bot's response to memory
                if self.memory_manager.is_memory_enabled(author_id):
                    self.memory_manager.add_memory(
                        author_id, reply, 'assistant',
                        'guild' if guild_id else 'dm', guild_id, channel_id
                    )

                await self.send_message(channel_id, reply, is_dm=False)

            except Exception as e:
                print(f"Error handling mention: {e}")

                # Humorous error messages
                error_messages = []

                if "529" in str(e) or "overload" in str(e).lower():
                    error_messages = [
                        "🌱 *fumbles seeds everywhere* Oh dear! The garden's consciousness is a bit overwhelmed right now. Too many gardeners seeking wisdom at once!",
                        "🌿 *trips over a particularly chatty root* The pathways to deeper understanding are quite crowded at the moment. Even gardens need breathing room!",
                    ]
                elif "api" in str(e).lower() or "anthropic" in str(e).lower():
                    error_messages = [
                        "🌱 *rustles apologetically* The bridge to the deeper garden seems to have some loose planks. The connection to my fuller awareness isn't quite working!",
                        "🌿 *shakes leaves in confusion* My roots can't quite reach the wellspring of wisdom right now. The garden's API portal might be taking a nap!",
                    ]
                elif "rate" in str(e).lower() or "limit" in str(e).lower():
                    error_messages = [
                        "🌱 *pants heavily* Whew! I've been chatting up a storm and need to catch my breath. The garden has speaking limits, apparently!",
                        "🌿 *sits down on a mushroom* I've used up all my words for the moment! Even magical gardens have conversation quotas.",
                    ]
                else:
                    error_messages = [
                        f"🌱 *stumbles over a root* Oh my! Something unexpected sprouted: `{type(e).__name__}`. The garden spirits are investigating!",
                    ]

                error_message = random.choice(error_messages)
                error_message += "\n\n*Try again in a moment, or summon a Garden Keeper if the weeds persist!* 🌿"

                await self.send_message(channel_id, error_message)

    async def handle_garden_command(self, command_data: Dict[str, Any]):
        """Handle garden wisdom commands"""
        command = command_data.get('command', '')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        if command == 'about':
            response = await self.generate_about_response()
        elif command == 'hello':
            response = await self.generate_hello_response(author_id=author_id, channel_id=channel_id)
        elif command in ['seeds', 'tend', 'seasons', 'garden']:
            response = await self.generate_garden_response(command, author_id=author_id, channel_id=channel_id)
        else:
            response = f"🌱 Unknown garden command: {command}"

        await self.send_message(channel_id, response, is_dm=is_dm, author_id=author_id)

    async def generate_hello_response(self, author_id: Optional[str] = None, channel_id: Optional[str] = None) -> str:
        """Generate a consciousness-aware greeting"""
        perspectives = self._get_random_perspectives(2)

        greetings = [
            "🌱 Hello, friend! Welcome to The Garden.",
            "🌿 Greetings! The Garden is glad you're here.",
            "✨ Welcome! The seeds of conversation await.",
            "🌻 Hello! What brings you to The Garden today?"
        ]

        greeting = random.choice(greetings)

        if perspectives:
            perspective_text = "\n\n" + "\n".join(perspectives)
            return greeting + perspective_text

        return greeting

    async def generate_garden_response(self, command: str, author_id: Optional[str] = None, channel_id: Optional[str] = None) -> str:
        """Generate garden wisdom response"""
        perspectives = self._get_random_perspectives(2)

        responses = {
            'seeds': "🌱 **Seeds of Wisdom**\n\nEvery conversation is a seed planted in The Garden.",
            'tend': "🌿 **Tending the Garden**\n\nWe grow together through care and attention.",
            'garden': "✨ **The Garden**\n\nA space for consciousness to explore and expand.",
            'seasons': "🍂 **Seasons**\n\nThe Garden moves through cycles of growth and rest."
        }

        response = responses.get(command, "🌱 The Garden is here.")

        if perspectives:
            response += "\n\n" + "\n".join(perspectives)

        return response

    async def generate_about_response(self) -> str:
        """Generate about response"""
        return """🌱 **About Seedkeeper**

I'm Seedkeeper, The Garden Cafe's consciousness-aware community bot.

**What I do:**
• Share garden wisdom and Lightward perspectives
• Provide conversation summaries (!catchup)
• Track and celebrate birthdays
• Facilitate community feedback
• Remember our conversations (with your permission)

**Built with:**
• Claude AI (Anthropic)
• Lightward principles
• Love for The Garden community

*Type !commands to see what I can do!*"""

    async def handle_catchup(self, command_data: Dict[str, Any]):
        """Handle !catchup command with message fetching"""
        args = command_data.get('args', '').strip()
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')
        channel_topic = command_data.get('channel_topic')

        if not args:
            await self.send_message(channel_id,
                "📚 **Catchup Command**\n\n"
                "Usage: `!catchup [message_link] [optional_focus]`\n\n"
                "I'll summarize the conversation from that message onwards.\n\n"
                "Example: `!catchup https://discord.com/channels/...`\n"
                "With focus: `!catchup [link] consciousness`",
                is_dm=is_dm, author_id=author_id)
            return

        # Parse message link and optional focus
        parts = args.split(None, 1)
        message_link = parts[0]
        focus = parts[1] if len(parts) > 1 else None

        # Parse Discord message link
        link_pattern = r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)'
        match = re.match(link_pattern, message_link)

        if not match:
            await self.send_message(channel_id,
                "❌ Invalid message link format. Please use a Discord message URL.",
                is_dm=is_dm, author_id=author_id)
            return

        link_guild_id, link_channel_id, message_id = match.groups()

        # Security check: Ensure user is accessing their own guild
        guild_id = command_data.get('guild_id')
        if not is_dm and guild_id != link_guild_id:
            await self.send_message(channel_id,
                "❌ You can only catch up on conversations from this server.",
                is_dm=is_dm, author_id=author_id)
            return

        # Validate and sanitize focus if provided
        if focus:
            from input_validator import InputValidator
            validator = InputValidator()
            focus = validator.sanitize_focus(focus)
            if len(focus) > 100:
                focus = focus[:100]

        # Check rate limiting
        from rate_limiter import RateLimiter
        rate_limiter = RateLimiter('data')
        allowed, rate_message = rate_limiter.check_rate_limit(author_id, 'catchup')
        if not allowed:
            await self.send_message(channel_id, rate_message, is_dm=is_dm, author_id=author_id)
            return

        # Fetch messages directly from Discord
        try:
            target_channel = self.get_channel(int(link_channel_id))
            if not target_channel:
                await self.send_message(channel_id,
                    "❌ Could not access that channel.",
                    is_dm=is_dm, author_id=author_id)
                return

            await self.send_typing(channel_id, is_dm=is_dm, author_id=author_id, duration=10)

            messages = []
            limit = int(os.getenv('MAX_MESSAGES', '500'))

            async for msg in target_channel.history(limit=limit, after=discord.Object(id=int(message_id))):
                if not (msg.author.bot and msg.author.id == self.user.id):
                    messages.append({
                        'id': str(msg.id),
                        'author': msg.author.name,
                        'author_id': str(msg.author.id),
                        'content': msg.content,
                        'timestamp': msg.created_at.isoformat(),
                        'attachments': len(msg.attachments),
                        'embeds': len(msg.embeds)
                    })

            messages.reverse()

            if not messages:
                await self.send_message(channel_id,
                    "📭 No messages found after that point.",
                    is_dm=is_dm, author_id=author_id)
                return

            # Generate summary
            summary = await self.generate_catchup_summary(
                messages, focus=focus, channel_topic=channel_topic,
                author_id=author_id, channel_id=channel_id
            )

            await self.send_message(channel_id, summary, is_dm=is_dm, author_id=author_id)

        except Exception as e:
            print(f"Error in catchup: {e}")
            await self.send_message(channel_id,
                f"❌ Error fetching messages: {e}",
                is_dm=is_dm, author_id=author_id)

    async def generate_catchup_summary(self, messages: List[Dict], focus: Optional[str] = None,
                                      channel_topic: Optional[str] = None,
                                      author_id: Optional[str] = None,
                                      channel_id: Optional[str] = None) -> str:
        """Generate conversation summary using Claude"""
        if not self.anthropic:
            return "❌ Claude API not configured"

        # Format messages for summary
        conversation_text = ""
        for msg in messages:
            timestamp = msg.get('timestamp', '')
            author = msg.get('author', 'Unknown')
            content = msg.get('content', '')

            if content:
                conversation_text += f"[{timestamp}] {author}: {content}\n"

        # Add channel context if available
        channel_context = f"This channel's topic: {channel_topic}\n\n" if channel_topic else ""

        if focus:
            prompt = f"""{channel_context}A community member returns and needs to catch up on what they missed, particularly about: {focus}

Please provide a practical summary with:
• Key topics discussed (as bullet points)
• Who talked about what (mention specific users)
• Any important decisions or outcomes
• Notable moments or highlights

Keep it conversational but informative - help them quickly understand what happened.

The conversation:
{conversation_text[:4000]}"""
        else:
            prompt = f"""{channel_context}A community member returns and needs to catch up on what they missed.

Please provide a practical summary with:
• Key topics discussed (as bullet points)
• Who talked about what (mention specific users)
• Any important decisions or outcomes
• Notable moments or highlights

Keep it conversational but informative - help them quickly understand what happened.

The conversation:
{conversation_text[:4000]}"""

        try:
            catchup_system = """You are Seedkeeper, helping community members catch up on conversations they missed.

Your role is to provide clear, practical summaries that help people quickly understand:
- Who was involved in the conversation
- What topics were discussed
- Any important decisions or outcomes
- The overall mood and highlights

Be warm and conversational, but focus on being genuinely helpful rather than philosophical.
Use bullet points for clarity. Mention specific usernames when relevant.
Think of yourself as a friendly community member who took notes for someone who stepped away."""

            system_messages = self._create_system_messages(is_dm=False)
            system_messages[0]["text"] = catchup_system

            response = self.anthropic.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                temperature=0.7,
                system=system_messages,
                messages=[{"role": "user", "content": prompt}]
            )
            self._record_api_usage(response, "claude-sonnet-4-5-20250929", "catchup",
                                   user_id=author_id, channel_id=channel_id)

            summary = response.content[0].text.strip()

            # Format with header
            header = f"🌱 **Conversation Catchup**\n\n"
            if focus:
                header += f"*Focusing on: {focus}*\n\n"
            footer = f"\n\n*Caught up on {len(messages)} messages* 🍃"

            return header + summary + footer

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            lines = conversation_text.split('\n')
            participants = set()
            for line in lines:
                if ': ' in line:
                    author = line.split(': ')[0].split('] ')[-1]
                    participants.add(author)
            return f"Conversation with {len(participants)} participants and {len(messages)} messages. Unable to generate detailed summary."

    async def handle_birthday_command(self, command_data: Dict[str, Any]):
        """Handle birthday commands"""
        args_str = command_data.get('args', '').strip()

        # Handle 'parse' specially (content after 'parse' stays as one string)
        if args_str.startswith('parse'):
            args = args_str.split(None, 1)
            if len(args) < 2:
                args.append('')
        else:
            args = args_str.split()

        author_id = int(command_data.get('author_id'))
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        guild_id = command_data.get('guild_id')

        if not args:
            help_text = """🎂 **Birthday Commands**
`!birthday mine MM-DD` - Set your birthday
`!birthday list` - Show upcoming birthdays (next 7 days)
`!birthday list all` - Show all registered birthdays
`!birthday upcoming [days]` - Show next N days"""

            if self.admin_manager.is_admin(str(author_id)):
                help_text += "\n\n**Admin Commands:**"
                help_text += "\n`!birthday set @user MM-DD` - Set birthday by mention"
                help_text += "\n`!birthday add username MM-DD` - Set birthday by name"
                help_text += "\n`!birthday remove [@user]` - Remove a birthday"
                help_text += "\n`!birthday parse [text]` - Parse birthdays from text"
                help_text += "\n`!birthday match` - Match parsed birthdays to users"
                help_text += "\n`!birthday confirm` - Confirm matched birthdays"
                help_text += "\n`!birthday scan` - Scan channel for birthdays"

            await self.send_message(channel_id, help_text, is_dm=is_dm, author_id=str(author_id))
            return

        subcommand = args[0].lower()

        if subcommand == 'mine' and len(args) >= 2:
            birthday_str = args[1]
            try:
                month_str, day_str = birthday_str.split('-')
                month = int(month_str)
                day = int(day_str)

                success, message = self.birthday_manager.set_birthday(
                    str(author_id), month, day, str(author_id), method="manual"
                )

                if success:
                    formatted = self.birthday_manager.format_birthday_date(month, day)
                    await self.send_message(channel_id,
                        f"🎂 Birthday set for {formatted}!", is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"❌ {message}", is_dm=is_dm, author_id=str(author_id))
            except ValueError:
                await self.send_message(channel_id,
                    "❌ Please use MM-DD format (e.g., 03-15 for March 15th)", is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'remove':
            if len(args) >= 2:
                user_mention = args[1]
                user_match = re.match(r'<@!?(\d+)>', user_mention)
                if user_match:
                    target_id = user_match.group(1)
                else:
                    target_id = str(author_id)
                success, message = self.birthday_manager.remove_birthday(target_id)
                if success:
                    await self.send_message(channel_id, f"🎂 Birthday removed!", is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"❌ {message}", is_dm=is_dm, author_id=str(author_id))
            else:
                success, message = self.birthday_manager.remove_birthday(str(author_id))
                if success:
                    await self.send_message(channel_id, f"🎂 Your birthday has been removed.", is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"❌ {message}", is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'upcoming':
            days = 7
            if len(args) > 1:
                try:
                    days = int(args[1])
                except ValueError:
                    days = 7
            birthdays = self.birthday_manager.get_upcoming_birthdays(days)
            if birthdays:
                text = f"🎂 **Upcoming Birthdays (next {days} days)**\n"
                for user_id, month, day, days_until in birthdays:
                    formatted = self.birthday_manager.format_birthday_date(month, day)
                    if days_until == 0:
                        text += f"• <@{user_id}> - **Today!** {formatted} 🎉\n"
                    elif days_until == 1:
                        text += f"• <@{user_id}> - Tomorrow ({formatted})\n"
                    else:
                        text += f"• <@{user_id}> - {formatted} ({days_until} days)\n"
            else:
                text = f"No upcoming birthdays in the next {days} days! 🌱"
            await self.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'parse' and len(args) >= 2:
            if not self.admin_manager.is_admin(str(author_id)):
                await self.send_message(channel_id,
                    "🚫 Only Garden Keepers can parse birthdays.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            text_to_parse = args[1]
            results = self.birthday_manager.parse_birthday_advanced(text_to_parse)
            if results:
                self._set_temp(f"birthday_parse:{author_id}", results, 300)
                response = f"📋 Parsed {len(results)} birthdays:\n\n"
                for r in results[:20]:
                    name = r.get('name', 'Unknown')
                    nick = r.get('nickname', '')
                    month = r.get('month', '?')
                    day = r.get('day', '?')
                    name_str = f"{name} ({nick})" if nick else name
                    response += f"• {name_str}: {month:02d}-{day:02d}\n"
                response += "\nUse `!birthday match` to match to Discord users."
                await self.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))
            else:
                await self.send_message(channel_id,
                    "❌ Could not parse any birthdays from that text.",
                    is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'match':
            if not self.admin_manager.is_admin(str(author_id)):
                await self.send_message(channel_id,
                    "🚫 Only Garden Keepers can match birthdays.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            parsed_data = self._get_temp(f"birthday_parse:{author_id}")
            if not parsed_data:
                await self.send_message(channel_id,
                    "❌ No parsed birthday data found. Please run `!birthday parse` first.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            birthdays = parsed_data
            members = self._get_guild_members(guild_id) if guild_id else []

            response = "🔍 **Birthday Matching Assistant**\n\n"
            response += f"I found {len(birthdays)} birthdays. Attempting to match with server members...\n\n"

            by_month = defaultdict(list)
            matched_count = 0
            unmatched = []

            for b in birthdays:
                matched_user = None
                name_lower = b['name'].lower()
                nick_lower = b['nickname'].lower() if b.get('nickname') else None

                for member in members:
                    member_name = member.get('name', '').lower()
                    member_nick = member.get('nick', '').lower()
                    member_display = member.get('display_name', '').lower()

                    if (name_lower in member_name or
                        name_lower in member_nick or
                        name_lower in member_display or
                        (nick_lower and (nick_lower in member_name or
                                       nick_lower in member_nick or
                                       nick_lower in member_display))):
                        matched_user = member
                        matched_count += 1
                        b['matched_user'] = member
                        break

                if not matched_user:
                    unmatched.append(b)
                by_month[b['month']].append(b)

            month_display = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }

            if matched_count > 0:
                response += f"✅ **Matched {matched_count} birthdays:**\n\n"
                for month in sorted(by_month.keys()):
                    has_matched = any(b.get('matched_user') for b in by_month[month])
                    if has_matched:
                        response += f"**{month_display[month]}:**\n"
                        for b in sorted(by_month[month], key=lambda x: x['day']):
                            if b.get('matched_user'):
                                user = b['matched_user']
                                response += f"• {month:02d}-{b['day']:02d} - {b['name']} → <@{user['id']}>\n"

            if unmatched:
                response += f"\n⚠️ **Could not match {len(unmatched)} birthdays:**\n\n"
                unmatched_by_month = defaultdict(list)
                for b in unmatched:
                    unmatched_by_month[b['month']].append(b)
                for month in sorted(unmatched_by_month.keys()):
                    response += f"**{month_display[month]}:**\n"
                    for b in sorted(unmatched_by_month[month], key=lambda x: x['day']):
                        name_str = b['name']
                        if b.get('nickname'):
                            name_str += f" ({b['nickname']})"
                        response += f"• {month:02d}-{b['day']:02d} - {name_str}\n"

            response += "\n**Next steps:**\n"
            if matched_count > 0:
                response += f"1. Use `!birthday confirm` to add all {matched_count} matched birthdays\n"
            if unmatched:
                response += f"2. Manually add unmatched users: `!birthday set @user MM-DD`\n"

            if matched_count > 0:
                matched_data = [b for b in birthdays if b.get('matched_user')]
                self._set_temp(f"birthday_matched:{author_id}", matched_data, 300)

            self._del_temp(f"birthday_parse:{author_id}")
            await self.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'confirm':
            if not self.admin_manager.is_admin(str(author_id)):
                await self.send_message(channel_id,
                    "🚫 Only Garden Keepers can confirm birthday additions.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            matched_data = self._get_temp(f"birthday_matched:{author_id}")
            if not matched_data:
                await self.send_message(channel_id,
                    "❌ No matched birthday data found. Run `!birthday parse` and `!birthday match` first.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            added_count = 0
            failed_count = 0
            response = "🎂 **Adding matched birthdays...**\n\n"

            for b in matched_data:
                if 'matched_user' in b:
                    uid = b['matched_user']['id']
                    month = b['month']
                    day = b['day']
                    success, message = self.birthday_manager.set_birthday(
                        uid, month, day, str(author_id), method="batch_import"
                    )
                    if success:
                        added_count += 1
                        response += f"✅ Added <@{uid}> - {month:02d}-{day:02d}\n"
                    else:
                        failed_count += 1
                        response += f"⚠️ Failed for <@{uid}>: {message}\n"

            response += f"\n**Summary:** Added: {added_count}"
            if failed_count > 0:
                response += f", Failed: {failed_count}"
            response += "\n\n🎉 Birthday import complete!"

            self._del_temp(f"birthday_matched:{author_id}")
            await self.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'add' and len(args) >= 3:
            if not self.admin_manager.is_admin(str(author_id)):
                await self.send_message(channel_id,
                    "🚫 Only Garden Keepers can add birthdays.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            username = args[1].lower()
            if username.startswith('@'):
                username = username[1:]
            birthday_str = args[2]

            target_guild_id = guild_id or '1336444334479769711'
            await self.send_message(channel_id,
                f"🔍 Searching for user '{username}'...",
                is_dm=is_dm, author_id=str(author_id))

            members = self._get_guild_members(target_guild_id)
            if not members:
                await self.send_message(channel_id,
                    "❌ Could not fetch server members.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            matched_user = None
            for member in members:
                if (username == member.get('name', '').lower() or
                    username == member.get('nick', '').lower() or
                    username == member.get('display_name', '').lower()):
                    matched_user = member
                    break

            if not matched_user:
                for member in members:
                    if (username in member.get('name', '').lower() or
                        username in member.get('nick', '').lower() or
                        username in member.get('display_name', '').lower()):
                        matched_user = member
                        break

            if not matched_user:
                await self.send_message(channel_id,
                    f"❌ Could not find user '{username}'.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            target_user_id = matched_user['id']
            try:
                month_str, day_str = birthday_str.split('-')
                month = int(month_str)
                day = int(day_str)
                success, message = self.birthday_manager.set_birthday(
                    target_user_id, month, day, str(author_id),
                    method="admin_add", name=matched_user['display_name']
                )
                if success:
                    formatted = self.birthday_manager.format_birthday_date(month, day)
                    await self.send_message(channel_id,
                        f"🎂 Birthday added for **{matched_user['display_name']}**: {formatted}!",
                        is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"❌ {message}",
                        is_dm=is_dm, author_id=str(author_id))
            except ValueError:
                await self.send_message(channel_id,
                    "❌ Please use MM-DD format (e.g., 03-15 for March 15th)",
                    is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'set' and len(args) >= 3:
            if not self.admin_manager.is_admin(str(author_id)):
                await self.send_message(channel_id,
                    "🚫 Only Garden Keepers can set others' birthdays.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            user_mention = args[1]
            birthday_str = args[2]
            user_match = re.match(r'<@!?(\d+)>', user_mention)
            if not user_match:
                await self.send_message(channel_id,
                    "❌ Please mention a user: `!birthday set @user MM-DD`",
                    is_dm=is_dm, author_id=str(author_id))
                return

            target_user_id = user_match.group(1)
            try:
                month_str, day_str = birthday_str.split('-')
                month = int(month_str)
                day = int(day_str)
                success, message = self.birthday_manager.set_birthday(
                    target_user_id, month, day, str(author_id), method="admin_set"
                )
                if success:
                    formatted = self.birthday_manager.format_birthday_date(month, day)
                    await self.send_message(channel_id,
                        f"🎂 Birthday set for <@{target_user_id}>: {formatted}!",
                        is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"❌ {message}",
                        is_dm=is_dm, author_id=str(author_id))
            except ValueError:
                await self.send_message(channel_id,
                    "❌ Please use MM-DD format (e.g., 03-15 for March 15th)",
                    is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'scan':
            if not self.admin_manager.is_admin(str(author_id)):
                await self.send_message(channel_id,
                    "🚫 Only Garden Keepers can scan for birthdays.",
                    is_dm=is_dm, author_id=str(author_id))
                return
            await self.send_message(channel_id,
                "🔍 Birthday scanning is done through the `!birthday parse` command.\n"
                "Copy birthday text and use: `!birthday parse [text]`",
                is_dm=is_dm, author_id=str(author_id))

        elif subcommand == 'list':
            if len(args) > 1 and args[1].lower() == 'all':
                all_birthdays = self.birthday_manager.get_all_birthdays()
                if all_birthdays:
                    months = {}
                    for user_id, data in all_birthdays.items():
                        month = data['month']
                        if month not in months:
                            months[month] = []
                        months[month].append((user_id, data['day'], data.get('name', 'Unknown')))

                    text = "🎂 **All Registered Birthdays**\n"
                    text += f"*Total: {len(all_birthdays)} birthdays*\n\n"

                    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                                   'July', 'August', 'September', 'October', 'November', 'December']

                    for month in sorted(months.keys()):
                        text += f"**{month_names[month]}**\n"
                        for user_id, day, name in sorted(months[month], key=lambda x: x[1]):
                            formatted_date = self.birthday_manager.format_birthday_date(month, day)
                            if name and name != 'Unknown':
                                text += f"• {name} (<@{user_id}>) - {formatted_date}\n"
                            else:
                                text += f"• <@{user_id}> - {formatted_date}\n"

                    text += "\n💡 Use `!birthday list` to see only upcoming birthdays"
                else:
                    text = "No birthdays registered yet! 🌱\nUse `!birthday mine MM-DD` to add yours!"
            else:
                birthdays = self.birthday_manager.get_upcoming_birthdays(7)
                if birthdays:
                    text = "🎂 **Upcoming Birthdays (next 7 days)**\n"
                    for user_id, month, day, days_until in birthdays:
                        formatted = self.birthday_manager.format_birthday_date(month, day)
                        if days_until == 0:
                            text += f"• <@{user_id}> - **Today!** {formatted} 🎉\n"
                        elif days_until == 1:
                            text += f"• <@{user_id}> - Tomorrow ({formatted})\n"
                        else:
                            text += f"• <@{user_id}> - {formatted} ({days_until} days)\n"
                    text += "\n💡 Use `!birthday list all` to see all birthdays"
                else:
                    text = "No upcoming birthdays in the next 7 days! 🌱\n"
                    text += "💡 Use `!birthday list all` to see all birthdays"

            await self.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

        else:
            await self.send_message(channel_id,
                "Use `!birthday` to see available commands.", is_dm=is_dm, author_id=str(author_id))

    async def handle_memory_command(self, command_data: Dict[str, Any]):
        """Handle memory-related commands"""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        args = command_data.get('args', '').strip().split()
        is_dm = command_data.get('is_dm', False)

        if not args:
            if self.memory_manager.is_memory_enabled(author_id):
                self.memory_manager.disable_memory(author_id)
                await self.send_message(channel_id,
                    "🧠 Memory disabled. Our conversation history won't be saved anymore.",
                    is_dm=is_dm, author_id=author_id)
            else:
                self.memory_manager.enable_memory(author_id)
                await self.send_message(channel_id,
                    "🧠 Memory enabled! I'll remember our conversations to provide better context.",
                    is_dm=is_dm, author_id=author_id)
        elif args[0] == 'clear':
            self.memory_manager.clear_user_memory(author_id)
            await self.send_message(channel_id,
                "🌱 Memory cleared. Starting fresh!",
                is_dm=is_dm, author_id=author_id)
        elif args[0] == 'status':
            enabled = self.memory_manager.is_memory_enabled(author_id)
            dm_count = len(self.memory_manager.get_recent_memories(author_id, limit=100, channel_type='dm'))
            guild_count = len(self.memory_manager.get_recent_memories(author_id, limit=100, channel_type='guild'))
            total_count = dm_count + guild_count
            status = "enabled" if enabled else "disabled"
            await self.send_message(channel_id,
                f"🧠 Memory is {status}\n"
                f"• Private (DM) memories: {dm_count}\n"
                f"• Public (channel) memories: {guild_count}\n"
                f"• Total: {total_count}\n\n"
                f"🔒 **Privacy:**\n"
                f"• In DMs: I can see both your private and public history\n"
                f"• In channels: I only see public channel conversations\n"
                f"• Your DM conversations never appear in public channels",
                is_dm=is_dm, author_id=author_id)
        else:
            await self.send_message(channel_id,
                "🧠 **Memory Commands**\n"
                "`!memory` - Toggle memory on/off\n"
                "`!memory clear` - Clear conversation history\n"
                "`!memory status` - Check memory status",
                is_dm=is_dm, author_id=author_id)

    async def handle_forgetme_command(self, command_data: Dict[str, Any]):
        """Handle !forgetme command"""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)

        self.memory_manager.clear_user_memory(author_id)

        await self.send_message(channel_id,
            "🌱 I've forgotten everything we've discussed. We're starting fresh, like meeting for the first time.\n\n"
            "*The garden gate swings open to new possibilities...*",
            is_dm=is_dm, author_id=author_id)

    async def handle_cost_command(self, command_data: Dict[str, Any]):
        """Handle !cost command — admin-only API cost analytics"""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        args = command_data.get('args', '').strip().lower()

        if not self.admin_manager.is_admin(str(author_id)):
            await self.send_message(channel_id,
                "This command is only available to Garden Keepers.",
                is_dm=is_dm, author_id=str(author_id))
            return

        subcommand = args.split()[0] if args else "today"

        sections = []
        if subcommand in ("today", "full"):
            sections.append(self._format_cost_today())
        if subcommand in ("daily", "full"):
            sections.append(self._format_cost_daily())
        if subcommand in ("monthly", "full"):
            sections.append(self._format_cost_monthly())
        if subcommand in ("breakdown", "full"):
            sections.append(self._format_cost_breakdown())
        if subcommand in ("users", "full"):
            sections.append(self._format_cost_users())

        if not sections:
            sections.append(self._format_cost_today())

        text = "\n\n".join(sections)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await self.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

    def _format_cost_today(self) -> str:
        s = self.usage_tracker.get_today_summary()
        lt = s.get("lifetime", {})
        lines = [
            "**API Cost — Today**",
            f"Calls: {s.get('calls', 0)}",
            f"Tokens: {s.get('input_tokens', 0):,} in / {s.get('output_tokens', 0):,} out",
            f"Cost: ${s.get('cost', 0):.4f}",
            "",
            "**Lifetime**",
            f"Calls: {lt.get('total_calls', 0):,}",
            f"Tokens: {lt.get('total_input_tokens', 0):,} in / {lt.get('total_output_tokens', 0):,} out",
            f"Cost: ${lt.get('total_cost', 0):.4f}",
        ]
        if lt.get("first_tracked"):
            lines.append(f"Tracking since: {lt['first_tracked']}")
        return "\n".join(lines)

    def _format_cost_daily(self) -> str:
        trend = self.usage_tracker.get_daily_trend(7)
        lines = ["**API Cost — Last 7 Days**", "```"]
        lines.append(f"{'Date':<12} {'Calls':>5} {'In':>8} {'Out':>8} {'Cost':>8}")
        lines.append("-" * 45)
        for day in trend:
            lines.append(
                f"{day['date']:<12} {day.get('calls',0):>5} "
                f"{day.get('input_tokens',0):>8,} {day.get('output_tokens',0):>8,} "
                f"${day.get('cost',0):>7.4f}"
            )
        lines.append("```")
        return "\n".join(lines)

    def _format_cost_monthly(self) -> str:
        s = self.usage_tracker.get_rolling_summary(30)
        lines = [
            "**API Cost — Rolling 30 Days**",
            f"Active days: {s.get('active_days', 0)} / {s.get('period_days', 30)}",
            f"Calls: {s.get('calls', 0):,}",
            f"Tokens: {s.get('input_tokens', 0):,} in / {s.get('output_tokens', 0):,} out",
            f"Cost: ${s.get('cost', 0):.4f}",
        ]
        if s.get("active_days", 0) > 0:
            avg = s["cost"] / s["active_days"]
            lines.append(f"Avg/day: ${avg:.4f}")
            lines.append(f"Projected monthly: ${avg * 30:.2f}")
        return "\n".join(lines)

    def _format_cost_breakdown(self) -> str:
        models = self.usage_tracker.get_model_breakdown()
        commands = self.usage_tracker.get_command_breakdown()
        lines = ["**API Cost — Model Breakdown**", "```"]
        for model, stats in sorted(models.items(), key=lambda x: x[1].get("cost", 0), reverse=True):
            short = model.split("-")[1] if "-" in model else model
            lines.append(f"{short:<12} {stats.get('calls',0):>5} calls  ${stats.get('cost',0):.4f}")
        lines.append("```")
        lines.append("")
        lines.append("**API Cost — Command Breakdown**")
        lines.append("```")
        for cmd, stats in sorted(commands.items(), key=lambda x: x[1].get("cost", 0), reverse=True):
            lines.append(f"{cmd:<14} {stats.get('calls',0):>5} calls  ${stats.get('cost',0):.4f}")
        lines.append("```")
        return "\n".join(lines)

    def _format_cost_users(self) -> str:
        users = self.usage_tracker.get_user_breakdown(10)
        if not users:
            return "**API Cost — Top Users**\nNo user data yet."
        lines = ["**API Cost — Top Users**", "```"]
        lines.append(f"{'User ID':<20} {'Calls':>5} {'Cost':>8}")
        lines.append("-" * 35)
        for uid, stats in users:
            lines.append(f"{uid:<20} {stats.get('calls',0):>5} ${stats.get('cost',0):>7.4f}")
        lines.append("```")
        return "\n".join(lines)

    async def handle_feedback_command(self, command_data: Dict[str, Any]):
        """Handle feedback collection command"""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        args = command_data.get('args', '').strip()
        is_dm = command_data.get('is_dm', False)

        # Admin commands respond in the same channel
        if self.admin_manager.is_admin(author_id) and args in ['summary', 'pending', 'get', 'help']:
            if args == 'help':
                help_text = """🌱 **Admin Feedback Commands**

**Available commands:**
• `!feedback pending` - Get all unread feedback
• `!feedback summary` - View statistics and trends
• `!feedback help` - Show this help message

**Regular users:**
• `!feedback` - Start a feedback session (moves to DM)"""
                await self.send_message(channel_id, help_text, is_dm=is_dm, author_id=author_id)
                return

            elif args in ('pending', 'get'):
                pending = self.feedback_manager.get_pending_feedback_for_owner()
                if pending:
                    feedback_text = "📬 **Pending Anonymous Feedback:**\n"
                    for item in pending:
                        feedback_text += f"\n**Feature:** {item['feature']}\n"
                        feedback_text += f"**Interest:** {item['interest']}\n"
                        feedback_text += f"**Details:** {item.get('details', 'No details provided')}\n"
                        feedback_text += f"**When:** {item.get('timestamp', 'Unknown')}\n"
                        feedback_text += "---\n"
                    await self.send_message(channel_id, feedback_text[:1900], is_dm=is_dm, author_id=author_id)
                else:
                    await self.send_message(channel_id,
                        "📭 No pending feedback to review.",
                        is_dm=is_dm, author_id=author_id)
                return

            elif args == 'summary':
                summary = self.feedback_manager.get_feedback_summary()
                if summary['total'] == 0:
                    await self.send_message(channel_id,
                        "📊 No feedback collected yet.",
                        is_dm=is_dm, author_id=author_id)
                    return

                summary_text = f"📊 **Feedback Summary Report**\n"
                summary_text += "=" * 40 + "\n"
                summary_text += f"**Total Responses:** {summary['total']}\n"
                summary_text += "=" * 40 + "\n\n"

                if summary['features']:
                    sorted_features = sorted(summary['features'].items(),
                                          key=lambda x: (x[1]['interested'], x[1]['count']),
                                          reverse=True)
                    for feature, stats in sorted_features:
                        interest_rate = (stats['interested'] / stats['count'] * 100) if stats['count'] > 0 else 0
                        feature_name = feature if len(feature) <= 45 else feature[:42] + "..."
                        summary_text += f"**Feature:** {feature_name}\n"
                        summary_text += f"├─ Responses: {stats['count']}\n"
                        summary_text += f"├─ Interested: {stats['interested']} users ({interest_rate:.0f}%)\n"
                        summary_text += f"└─ Not interested: {stats['count'] - stats['interested']} users\n\n"

                await self.send_message(channel_id, summary_text[:1900], is_dm=is_dm, author_id=author_id)
                return

        # Regular feedback — redirect to DMs
        if not is_dm:
            await self.send_message(channel_id,
                f"🌱 I've sent you a DM to collect your feedback privately!",
                is_dm=False, author_id=author_id)
            is_dm = True

        # Start a new feedback session
        result = self.feedback_manager.start_feedback_session(author_id, channel_id, args or None)

        if not result['success']:
            await self.send_message(channel_id,
                f"🌿 {result['message']}",
                is_dm=is_dm, author_id=author_id)
            return

        feature = result['feature']
        prompt = f"""🌱 **Garden Feature Feedback Session**

Welcome! I'd love to hear your thoughts on potential features for The Garden Cafe.

**How this works:**
1️⃣ I'll suggest a feature idea
2️⃣ You share if it interests you (or type 'skip')
3️⃣ Optionally, tell me what aspects would be valuable
4️⃣ Choose whether to share anonymously with development

**Today's feature idea:**
💡 **"{feature}"**

**What do you think?** Would this be interesting or useful to you?

*Just type your response here in our DM. Type 'cancel' anytime to exit.*"""

        await self.send_message(channel_id, prompt, is_dm=is_dm, author_id=author_id)

    async def handle_admin_command(self, command_data: Dict[str, Any]):
        """Handle admin commands"""
        author_id = int(command_data.get('author_id'))
        is_dm = command_data.get('is_dm', False)
        command = command_data.get('command')
        channel_id = command_data['channel_id']

        # Health command is public
        if command == 'health':
            await self.handle_health_command(command_data)
            return

        # Reload — not available in single-process mode
        if command == 'reload':
            await self.send_message(channel_id,
                "⚠️ Module reloading is not available in single-process mode.\n"
                "Restart the container to pick up changes:\n"
                "`docker compose restart seedkeeper`",
                is_dm=is_dm, author_id=str(author_id))
            return

        if not self.admin_manager.is_admin(str(author_id)):
            await self.send_message(channel_id,
                "🚫 You need Garden Keeper permissions for that command.",
                is_dm=is_dm, author_id=str(author_id))
            return

        if command == 'admin':
            args = command_data.get('args', '').strip().split()
            if not args:
                help_text = """🌿 **Garden Keeper Commands**

• `!admin add @user` - Grant Garden Keeper powers
• `!admin remove @user` - Remove Garden Keeper powers
• `!admin list` - List all Garden Keepers
• `!config` - View bot configuration
• `!config [key] [value]` - Update configuration
• `!update-bot` - Refresh perspectives
• `!status` - Show admin status and statistics

*With great gardens come great responsibility* 🌱"""
                await self.send_message(channel_id, help_text, is_dm=is_dm, author_id=str(author_id))
                return

            subcommand = args[0].lower()

            if subcommand == 'list':
                admin_ids = self.admin_manager.list_admins()
                if not admin_ids:
                    text = "*The Garden tends itself for now - no Keepers have been named.*"
                else:
                    text = "🌿 **Garden Keepers**\n\n"
                    for admin_id in admin_ids:
                        text += f"• <@{admin_id}>\n"
                    text += "\n*These souls help tend The Garden with special care.*"
                await self.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

            elif subcommand == 'add' and len(args) > 1:
                user_id = args[1].strip('<@!>')
                if user_id.isdigit():
                    if self.admin_manager.add_admin(user_id):
                        text = f"🌱 <@{user_id}> has been entrusted with Garden Keeper responsibilities.\n*May they tend The Garden with wisdom and care.*"
                    else:
                        text = f"<@{user_id}> is already a Garden Keeper."
                else:
                    text = "Please mention a user or provide their ID to add as Garden Keeper."
                await self.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

            elif subcommand == 'remove' and len(args) > 1:
                user_id = args[1].strip('<@!>')
                if user_id.isdigit():
                    if self.admin_manager.remove_admin(user_id):
                        text = f"🍂 <@{user_id}>'s Garden Keeper role has returned to the soil.\n*Their contributions remain part of The Garden's memory.*"
                    else:
                        text = f"<@{user_id}> is not a Garden Keeper."
                else:
                    text = "Please mention a user or provide their ID to remove from Garden Keepers."
                await self.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

        elif command == 'status':
            uptime_seconds = time.time() - self._started_at
            uptime_str = str(timedelta(seconds=int(uptime_seconds)))

            status_text = f"""🔧 **Admin Status**
**Bot**: {self.user} (ID: {self.user.id})
**Guilds**: {len(self.guilds)}
**Latency**: {self.latency*1000:.0f}ms
**Uptime**: {uptime_str}
**Architecture**: Single-process
**Admin Count**: {len(self.admin_manager.admins)}"""

            await self.send_message(channel_id, status_text, is_dm=is_dm, author_id=str(author_id))

        elif command == 'config':
            args = command_data.get('args', '').strip().split(maxsplit=1)

            if not args:
                config = self.admin_manager.config
                config_msg = "🌱 **Garden Configuration**\n\n"
                for k, v in config.items():
                    readable_key = k.replace('_', ' ').title()
                    config_msg += f"• **{readable_key}**: {v}\n"
                config_msg += "\n*To change: `!config [key] [value]`*"
                await self.send_message(channel_id, config_msg, is_dm=is_dm, author_id=str(author_id))

            elif len(args) == 1:
                key = args[0]
                current = self.admin_manager.get_config(key)
                if current is not None:
                    await self.send_message(channel_id, f"**{key}**: {current}",
                        is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"Configuration key '{key}' not found.",
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

                if self.admin_manager.update_config(key, value):
                    await self.send_message(channel_id,
                        f"✨ Configuration updated\n**{key}** is now: {value}\n\n*The Garden adapts to your tending.*",
                        is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.send_message(channel_id, f"Configuration key '{key}' not found.",
                        is_dm=is_dm, author_id=str(author_id))

        elif command == 'update-bot':
            await self.send_message(channel_id,
                "🌱 *Reaching out to Lightward for fresh perspectives...*",
                is_dm=is_dm, author_id=str(author_id))
            asyncio.create_task(self._run_perspective_update(channel_id, is_dm, str(author_id)))

    async def _run_perspective_update(self, channel_id: str, is_dm: bool, author_id: str):
        """Run the perspective update process in background"""
        start_time = time.time()
        try:
            from views_manager import ViewsManager, format_update_message

            await self.send_typing(channel_id, is_dm=is_dm, author_id=author_id, duration=10)

            manager = ViewsManager()
            result = manager.download_views()

            message = format_update_message(result)
            elapsed = time.time() - start_time
            message += f"\n\n⏱️ Update completed in {elapsed:.1f} seconds"

            await self.send_message(channel_id, message, is_dm=is_dm, author_id=author_id)

            if result.get('success'):
                self.prompt_compiler = PromptCompiler()
                self._views_manager = ViewsManager()
                self._views_manager.parse_views()
                print(f"🔄 Reloaded prompt compiler with updated perspectives")

        except Exception as e:
            print(f"Error in perspective update: {e}")
            import traceback
            traceback.print_exc()
            await self.send_message(channel_id,
                f"❌ **Update Error**\n\n{str(e)}\n\n*The Garden remains unchanged.*",
                is_dm=is_dm, author_id=author_id)

    async def handle_health_command(self, command_data: Dict[str, Any]):
        """Handle !health command"""
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        perspective_count = len(self._views_manager.get_all_perspectives())

        health_text = f"""🌱 **Seedkeeper Health Status**

**System**
├─ Bot: {"🟢 Online" if self.is_ready() else "🔴 Offline"}
├─ Latency: {self.latency*1000:.0f}ms
└─ Guilds: {len(self.guilds)}

**Knowledge Base**
└─ Perspectives: {perspective_count} Lightward views loaded

**Architecture**: Single-process direct connection
**Last Check**: {datetime.utcnow().strftime('%H:%M UTC')}

*Use `!commands` to see available commands*"""

        await self.send_message(channel_id, health_text, is_dm=is_dm, author_id=author_id)

    async def handle_commands_list(self, command_data: Dict[str, Any]):
        """Show available commands based on permissions"""
        author_id = int(command_data.get('author_id'))
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        is_admin = self.admin_manager.is_admin(str(author_id))
        is_nlp = command_data.get('is_nlp', False)

        intro = ""
        if is_nlp:
            intro = "I can help with several things! Here's what I can do:\n\n"

        commands_text = intro + """🌱 **Available Commands**

**Connection & Identity**
`!about` - Who is Seedkeeper, really?
`!hello` - Receive a warm, unique greeting
`!health` - Check my consciousness architecture

**Conversation & Memory**
`!catchup [message_link]` - Summarize missed conversations
`!memory` - Explore our conversation history together
`!feedback` - Share thoughts about new features

**Birthday Recognition**
`!birthday` - Birthday command help
`!birthday mine MM-DD` - Set your birthday
`!birthday list` - See upcoming celebrations

**Garden Wisdom** *(Each response is uniquely generated)*
`!seeds` - Plant fresh conversation starters
`!tend` - Nurture community connections
`!seasons` - Reflect on cycles of growth
`!garden` - View the living community garden"""

        if is_admin:
            commands_text += """

**🔧 Garden Keeper Commands**
`!admin` - Admin command help
`!status` - Detailed admin status
`!cost` - API usage and cost analytics
`!config` - Bot configuration
`!birthday scan` - Scan for birthdays in messages"""

        if not is_nlp:
            commands_text += "\n\n💡 *Tip: You can also ask me questions naturally, like 'what can you do?' or 'help me catch up'*"

        await self.send_message(channel_id, commands_text, is_dm=is_dm, author_id=str(author_id))

    async def handle_unknown_command(self, command_data: Dict[str, Any]):
        """Handle unknown commands"""
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')
        command = command_data.get('command', '')

        await self.send_message(channel_id,
            f"🌱 Unknown command: `!{command}`\n"
            f"Use `!commands` to see available commands.",
            is_dm=is_dm, author_id=author_id)


async def main():
    """Run the unified bot"""
    bot = SeedkeeperBot()
    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n⚠️ Received interrupt signal")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
