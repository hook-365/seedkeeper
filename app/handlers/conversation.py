"""DM and mention conversation handlers."""

import asyncio
import os
import re
import random
from datetime import datetime
from typing import Dict, Any

from input_validator import InputValidator
from config import (
    CONVERSATION_HISTORY_LIMIT,
    CONVERSATION_STORAGE_LIMIT,
    PERSISTENT_MEMORY_LIMIT,
)


class ConversationHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_dm_conversation(self, message_data: Dict[str, Any]):
        """Handle natural DM conversations."""
        author_id = message_data.get('author_id')
        raw_content = message_data.get('content', '')
        channel_id = message_data.get('channel_id')

        # Sanitize user input
        content = InputValidator.sanitize_string(raw_content, max_length=2000)

        # Check if there's an active feedback session (auto-expire after 30 min)
        if author_id in self.bot.feedback_manager.sessions:
            session = self.bot.feedback_manager.sessions[author_id]
            session_ts = session.get('timestamp', '')
            try:
                session_age = (datetime.utcnow() - datetime.fromisoformat(session_ts)).total_seconds()
                if session_age > 1800:  # 30 minutes
                    self.bot.feedback_manager.cancel_session(author_id)
            except (ValueError, TypeError):
                pass

        if author_id in self.bot.feedback_manager.sessions:
            if content.lower() in ['cancel', 'stop', 'exit', 'quit']:
                self.bot.feedback_manager.cancel_session(author_id)
                await self.bot.send_message(channel_id,
                    "Feedback session cancelled. Feel free to start a new one anytime with `!feedback`",
                    is_dm=True, author_id=author_id)
                return

            result = self.bot.feedback_manager.process_feedback_response(author_id, content)

            if result.get('complete'):
                await self.bot.send_message(channel_id, result['message'], is_dm=True, author_id=author_id)

                if result.get('success') and os.getenv('BOT_OWNER_ID') == author_id:
                    pending = self.bot.feedback_manager.get_pending_feedback_for_owner()
                    if pending:
                        feedback_text = "**New Anonymous Feedback:**\n"
                        for item in pending:
                            feedback_text += f"\n**Feature:** {item['feature']}\n"
                            feedback_text += f"**Interest:** {item['interest']}\n"
                            feedback_text += f"**Details:** {item['details']}\n"
                            feedback_text += "---\n"
                        await self.bot.send_message(channel_id, feedback_text[:1900], is_dm=True, author_id=author_id)
                        self.bot.feedback_manager.acknowledge_pending_feedback()
            else:
                await self.bot.send_message(channel_id, result.get('next_prompt', result.get('message')),
                                            is_dm=True, author_id=author_id)
            return

        # Get conversation history from in-memory store
        conversation = self.bot._dm_conversations.get(author_id, [])

        # Get personality for token limits
        personality = self.bot.personality_manager.get_user_personality(str(author_id))

        # Add persistent memories if enabled
        persistent_memories = []
        if self.bot.memory_manager.is_memory_enabled(author_id):
            memories = self.bot.memory_manager.get_recent_memories(author_id, limit=PERSISTENT_MEMORY_LIMIT)
            for mem in memories:
                role = 'user' if mem['author'] == 'user' else 'assistant'
                persistent_memories.append({'role': role, 'content': mem['content']})

        # Check if this looks like birthday info
        birthday_keywords = ['birthday', 'born', 'birth', 'bday', 'born on', 'celebrate']
        if any(keyword in content.lower() for keyword in birthday_keywords):
            parsed_results = self.bot.birthday_manager.parse_birthday_advanced(content)
            if parsed_results:
                for result in parsed_results:
                    if result.get('month') and result.get('day'):
                        success, message = self.bot.birthday_manager.set_birthday(
                            str(author_id), result['month'], result['day'], str(author_id), method="auto"
                        )
                        if success:
                            formatted = self.bot.birthday_manager.format_birthday_date(result['month'], result['day'])
                            await self.bot.send_message(channel_id,
                                f"I've noted your birthday as {formatted}! I'll remember to celebrate with you.",
                                is_dm=True, author_id=author_id)
                        else:
                            await self.bot.send_message(channel_id, message,
                                is_dm=True, author_id=author_id)
                        return

        # Generate natural response using LLM
        try:
            context_messages = []
            if persistent_memories:
                context_messages.extend(persistent_memories[-PERSISTENT_MEMORY_LIMIT:])
            for msg in conversation[-CONVERSATION_HISTORY_LIMIT:]:
                context_messages.append({"role": msg['role'], "content": msg['content']})
            context_messages.append({"role": "user", "content": content})

            system = self.bot._get_system_for_personality(personality, is_dm=True)
            max_tokens = personality.get('max_tokens', 800)

            # Get DM channel for typing indicator
            user = self.bot.get_user(int(author_id)) or await self.bot.fetch_user(int(author_id))
            dm_channel = user.dm_channel or await user.create_dm()

            # Show typing while LLM generates
            async with dm_channel.typing():
                result = await self.bot.model_client.complete(
                    personality=personality,
                    system=system,
                    messages=context_messages,
                    max_tokens=max_tokens,
                    temperature=float(os.getenv('SEEDKEEPER_TEMPERATURE', '1.0')),
                )
            self.bot._record_api_usage_from_result(result, "dm",
                                                   user_id=author_id, channel_id=channel_id)
            reply = result.text

            # Send response
            if len(reply) <= 2000:
                await self.bot.send_message(channel_id, reply, is_dm=True, author_id=author_id)
            else:
                chunks = self.bot.split_message(reply)
                for i, chunk in enumerate(chunks):
                    await self.bot.send_message(channel_id, chunk, is_dm=True, author_id=author_id)
                    if i < len(chunks) - 1:
                        await asyncio.sleep(0.5)

            # Save to in-memory conversation
            conversation.append({'role': 'user', 'content': content[:500], 'timestamp': datetime.utcnow().isoformat()})
            conversation.append({'role': 'assistant', 'content': reply[:500], 'timestamp': datetime.utcnow().isoformat()})
            if len(conversation) > CONVERSATION_STORAGE_LIMIT:
                conversation = conversation[-CONVERSATION_STORAGE_LIMIT:]
            self.bot._dm_conversations[author_id] = conversation

            # Save to persistent memory
            if self.bot.memory_manager.is_memory_enabled(author_id):
                self.bot.memory_manager.add_memory(
                    author_id, reply[:2000], 'bot', 'dm', None, channel_id
                )

        except Exception as e:
            print(f"Error in DM conversation: {e}")
            await self.bot.send_message(channel_id,
                "I'm having trouble processing that right now, but I'm here!",
                is_dm=True, author_id=author_id)

    async def handle_mention_conversation(self, message_data: Dict[str, Any]):
        """Handle mentions that aren't clear commands."""
        author_id = message_data.get('author_id')
        raw_content = message_data.get('content', '')
        channel_id = message_data.get('channel_id')
        guild_id = message_data.get('guild_id')
        channel_topic = message_data.get('channel_topic')

        # Sanitize user input
        content = InputValidator.sanitize_string(raw_content, max_length=2000)

        # Save to memory
        if self.bot.memory_manager.is_memory_enabled(author_id):
            self.bot.memory_manager.add_memory(
                author_id, content, 'user',
                'guild' if guild_id else 'dm', guild_id, channel_id
            )

        # Get personality for token limits
        personality = self.bot.personality_manager.get_user_personality(str(author_id))

        # Get channel-specific conversation context
        recent_messages = self.bot.memory_manager.get_recent_memories(
            author_id, limit=CONVERSATION_HISTORY_LIMIT,
            channel_type='guild',
            guild_id=guild_id,
            channel_id=channel_id
        )

        try:
            messages = []
            if recent_messages:
                for msg in recent_messages[-CONVERSATION_HISTORY_LIMIT:]:
                    role = 'user' if msg['author'] == 'user' else 'assistant'
                    messages.append({"role": role, "content": msg['content']})

            # Remove bot mention from content
            clean_content = content
            for mention_pattern in [f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>']:
                clean_content = clean_content.replace(mention_pattern, '').strip()

            messages.append({
                "role": "user",
                "content": clean_content if clean_content else content
            })

            system = self.bot._get_system_for_personality(personality, channel_topic=channel_topic, is_dm=False)
            max_tokens = max(personality.get('max_tokens', 800), 1200)

            # Get channel for typing indicator
            channel = self.bot.get_channel(int(channel_id))

            # Show typing while LLM generates
            async with channel.typing():
                result = await self.bot.model_client.complete(
                    personality=personality,
                    system=system,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=float(os.getenv('SEEDKEEPER_TEMPERATURE', '1.0')),
                )
            self.bot._record_api_usage_from_result(result, "mention",
                                                   user_id=author_id, channel_id=channel_id)
            reply = result.text
            if not reply:
                reply = "I heard you, but my thoughts got tangled. Could you try again?"

            # Save bot's response to memory
            if self.bot.memory_manager.is_memory_enabled(author_id):
                self.bot.memory_manager.add_memory(
                    author_id, reply, 'assistant',
                    'guild' if guild_id else 'dm', guild_id, channel_id
                )

            await self.bot.send_message(channel_id, reply, is_dm=False)

        except Exception as e:
            print(f"Error handling mention: {e}")
            await self.bot.send_message(channel_id,
                f"Something went wrong: {type(e).__name__}. Try again in a moment?")
