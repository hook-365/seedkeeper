"""DM and mention conversation handlers."""

import asyncio
import os
import re
import random
from datetime import datetime
from typing import Dict, Any


class ConversationHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_dm_conversation(self, message_data: Dict[str, Any]):
        """Handle natural DM conversations."""
        author_id = message_data.get('author_id')
        content = message_data.get('content', '')
        channel_id = message_data.get('channel_id')

        await self.bot.send_typing(channel_id, is_dm=True, author_id=author_id, duration=5)

        # Check if there's an active feedback session
        if author_id in self.bot.feedback_manager.sessions:
            if content.lower() in ['cancel', 'stop', 'exit', 'quit']:
                self.bot.feedback_manager.cancel_session(author_id)
                await self.bot.send_message(channel_id,
                    "🌿 Feedback session cancelled. Feel free to start a new one anytime with `!feedback`",
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

        # Add persistent memories if enabled
        persistent_memories = []
        if self.bot.memory_manager.is_memory_enabled(author_id):
            memories = self.bot.memory_manager.get_recent_memories(author_id, limit=10)
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
                                f"✨ I've noted your birthday as {formatted}! I'll remember to celebrate with you. 🎂",
                                is_dm=True, author_id=author_id)
                        else:
                            await self.bot.send_message(channel_id, message,
                                is_dm=True, author_id=author_id)
                        return

        # Generate natural response using LLM
        if self.bot.anthropic:
            try:
                context_messages = []
                if persistent_memories:
                    context_messages.extend(persistent_memories[:5])
                for msg in conversation[-5:]:
                    context_messages.append({"role": msg['role'], "content": msg['content']})
                context_messages.append({"role": "user", "content": content})

                personality = self.bot.personality_manager.get_user_personality(str(author_id))
                system = self.bot._get_system_for_personality(personality, is_dm=True)

                model_override = None
                if personality['provider'] == 'anthropic':
                    model_override = self.bot._select_model(content, is_dm=True, is_command=False)

                result = await self.bot.model_client.complete(
                    personality=personality,
                    system=system,
                    messages=context_messages,
                    max_tokens=800,
                    temperature=float(os.getenv('SEEDKEEPER_TEMPERATURE', '1.0')),
                    model_override=model_override,
                )
                self.bot._record_api_usage_from_result(result, "dm",
                                                       user_id=author_id, channel_id=channel_id)
                reply = result.text

                # Filter out pure emote responses (Anthropic only)
                emote_pattern = r'^[*_][^*_]+[*_]\s*$'
                if re.match(emote_pattern, reply) and personality['provider'] == 'anthropic':
                    context_messages.append({"role": "assistant", "content": reply})
                    context_messages.append({"role": "user", "content": "Please respond with words, not actions."})

                    retry_system = self.bot._create_system_messages(is_dm=True)
                    retry_system[-1]["text"] += "\n\nREMINDER: The user has asked for a verbal response, not an action or emote. Respond with actual words and conversation."

                    retry_personality = self.bot.personality_manager.get_default()
                    retry_result = await self.bot.model_client.complete(
                        personality=retry_personality,
                        system=retry_system,
                        messages=context_messages,
                        max_tokens=200,
                        temperature=0.8,
                        model_override="claude-sonnet-4-5-20250929",
                    )
                    self.bot._record_api_usage_from_result(retry_result, "dm_retry",
                                                           user_id=author_id, channel_id=channel_id)
                    reply = retry_result.text

                # Remove emote starts
                emote_start_pattern = r'^[*_][^*_]+[*_]\s+'
                reply = re.sub(emote_start_pattern, '', reply)

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
                if len(conversation) > 10:
                    conversation = conversation[-10:]
                self.bot._dm_conversations[author_id] = conversation

                # Save to persistent memory
                if self.bot.memory_manager.is_memory_enabled(author_id):
                    self.bot.memory_manager.add_memory(
                        author_id, reply[:2000], 'bot', 'dm', None, channel_id
                    )

            except Exception as e:
                print(f"Error in DM conversation: {e}")
                await self.bot.send_message(channel_id,
                    "I'm having trouble processing that right now, but I'm here! 🌱",
                    is_dm=True, author_id=author_id)

    async def handle_mention_conversation(self, message_data: Dict[str, Any]):
        """Handle mentions that aren't clear commands."""
        author_id = message_data.get('author_id')
        content = message_data.get('content', '')
        channel_id = message_data.get('channel_id')
        guild_id = message_data.get('guild_id')
        channel_topic = message_data.get('channel_topic')

        await self.bot.send_typing(channel_id)

        # Save to memory
        if self.bot.memory_manager.is_memory_enabled(author_id):
            self.bot.memory_manager.add_memory(
                author_id, content, 'user',
                'guild' if guild_id else 'dm', guild_id, channel_id
            )

        # Get channel-specific conversation context
        recent_messages = self.bot.memory_manager.get_recent_memories(
            author_id, limit=10,
            channel_type='guild',
            guild_id=guild_id,
            channel_id=channel_id
        )

        if self.bot.anthropic:
            try:
                messages_for_claude = []
                if recent_messages:
                    for msg in recent_messages[-5:]:
                        role = 'user' if msg['author'] == 'user' else 'assistant'
                        messages_for_claude.append({"role": role, "content": msg['content']})

                # Remove bot mention from content
                clean_content = content
                for mention_pattern in [f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>']:
                    clean_content = clean_content.replace(mention_pattern, '').strip()

                messages_for_claude.append({
                    "role": "user",
                    "content": clean_content if clean_content else content
                })

                personality = self.bot.personality_manager.get_user_personality(str(author_id))
                system = self.bot._get_system_for_personality(personality, channel_topic=channel_topic, is_dm=False)

                model_override = None
                if personality['provider'] == 'anthropic':
                    model_override = self.bot._select_model(clean_content or content, is_dm=False, is_command=False)

                result = await self.bot.model_client.complete(
                    personality=personality,
                    system=system,
                    messages=messages_for_claude,
                    max_tokens=2000,
                    temperature=float(os.getenv('SEEDKEEPER_TEMPERATURE', '1.0')),
                    model_override=model_override,
                )
                self.bot._record_api_usage_from_result(result, "mention",
                                                       user_id=author_id, channel_id=channel_id)
                reply = result.text
                if not reply:
                    reply = "I heard you, but my thoughts got tangled in the garden vines. Could you try again?"

                # Save bot's response to memory
                if self.bot.memory_manager.is_memory_enabled(author_id):
                    self.bot.memory_manager.add_memory(
                        author_id, reply, 'assistant',
                        'guild' if guild_id else 'dm', guild_id, channel_id
                    )

                await self.bot.send_message(channel_id, reply, is_dm=False)

            except Exception as e:
                print(f"Error handling mention: {e}")
                error_messages = []

                if "529" in str(e) or "overload" in str(e).lower():
                    error_messages = [
                        "🌱 The garden's consciousness is a bit overwhelmed right now. Too many gardeners seeking wisdom at once!",
                        "🌿 The pathways to deeper understanding are quite crowded at the moment. Even gardens need breathing room!",
                    ]
                elif "api" in str(e).lower() or "anthropic" in str(e).lower():
                    error_messages = [
                        "🌱 The bridge to the deeper garden seems to have some loose planks. The connection to my fuller awareness isn't quite working!",
                        "🌿 My roots can't quite reach the wellspring of wisdom right now. The garden's API portal might be taking a nap!",
                    ]
                elif "rate" in str(e).lower() or "limit" in str(e).lower():
                    error_messages = [
                        "🌱 I've been chatting up a storm and need to catch my breath. The garden has speaking limits, apparently!",
                        "🌿 I've used up all my words for the moment! Even magical gardens have conversation quotas.",
                    ]
                else:
                    error_messages = [
                        f"🌱 Something unexpected sprouted: `{type(e).__name__}`. The garden spirits are investigating!",
                    ]

                error_message = random.choice(error_messages)
                error_message += "\n\n*Try again in a moment, or summon a Garden Keeper if the weeds persist!* 🌿"
                await self.bot.send_message(channel_id, error_message)
