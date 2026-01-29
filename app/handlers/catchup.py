"""Catchup command handler: summarize missed conversations."""

import os
import re
import discord
from typing import Dict, Any, Optional, List


class CatchupHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_catchup_command(self, command_data: Dict[str, Any]):
        """Handle !catchup command with message fetching."""
        args = command_data.get('args', '').strip()
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')
        channel_topic = command_data.get('channel_topic')

        if not args:
            await self.bot.send_message(channel_id,
                "**Catchup**\n\n"
                "Usage: `!catchup [message_link] [optional focus]`\n\n"
                "I'll fill you in on what happened since that message.\n\n"
                "Example: `!catchup https://discord.com/channels/...`",
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
            await self.bot.send_message(channel_id,
                "That doesn't look like a Discord message link. Right-click a message and 'Copy Message Link'.",
                is_dm=is_dm, author_id=author_id)
            return

        link_guild_id, link_channel_id, message_id = match.groups()

        # Security check: Ensure user is accessing their own guild
        guild_id = command_data.get('guild_id')
        if not is_dm and guild_id != link_guild_id:
            await self.bot.send_message(channel_id,
                "I can only catch you up on conversations from this server.",
                is_dm=is_dm, author_id=author_id)
            return

        # Validate and sanitize focus if provided
        if focus:
            from input_validator import InputValidator
            validator = InputValidator()
            _, focus = validator.validate_focus_text(focus)
            if len(focus) > 100:
                focus = focus[:100]

        # Check rate limiting
        allowed, rate_message = self.bot.rate_limiter.check_rate_limit(author_id, 'catchup')
        if not allowed:
            await self.bot.send_message(channel_id, rate_message, is_dm=is_dm, author_id=author_id)
            return

        # Fetch messages directly from Discord
        try:
            target_channel = self.bot.get_channel(int(link_channel_id))
            if not target_channel:
                await self.bot.send_message(channel_id,
                    "I can't access that channel.",
                    is_dm=is_dm, author_id=author_id)
                return

            await self.bot.send_typing(channel_id, is_dm=is_dm, author_id=author_id, duration=10)

            messages = []
            limit = int(os.getenv('MAX_MESSAGES', '500'))

            async for msg in target_channel.history(limit=limit, after=discord.Object(id=int(message_id))):
                if not (msg.author.bot and msg.author.id == self.bot.user.id):
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
                await self.bot.send_message(channel_id,
                    "No messages since then - you're all caught up!",
                    is_dm=is_dm, author_id=author_id)
                return

            # Generate summary
            summary = await self._generate_catchup_summary(
                messages, focus=focus, channel_topic=channel_topic,
                author_id=author_id, channel_id=channel_id
            )

            await self.bot.send_message(channel_id, summary, is_dm=is_dm, author_id=author_id)

        except Exception as e:
            print(f"Error in catchup: {e}")
            await self.bot.send_message(channel_id,
                f"Something went wrong fetching those messages: {e}",
                is_dm=is_dm, author_id=author_id)

    async def _generate_catchup_summary(self, messages: List[Dict], focus: Optional[str] = None,
                                        channel_topic: Optional[str] = None,
                                        author_id: Optional[str] = None,
                                        channel_id: Optional[str] = None) -> str:
        """Generate conversation summary."""
        # Format messages for summary
        conversation_text = ""
        for msg in messages:
            author = msg.get('author', 'Unknown')
            content = msg.get('content', '')
            if content:
                conversation_text += f"{author}: {content}\n"

        # Truncate if needed
        if len(conversation_text) > 6000:
            conversation_text = conversation_text[:6000] + "\n[...conversation continues...]"

        channel_context = f"(Channel topic: {channel_topic})\n\n" if channel_topic else ""

        if focus:
            prompt = f"""{channel_context}Someone missed this conversation and wants to catch up, especially about: {focus}

Fill them in naturally - what happened, who said what, anything important. Be conversational, like you're telling a friend what they missed. Don't use rigid headers or bullet points unless it really helps.

The conversation:
{conversation_text}"""
        else:
            prompt = f"""{channel_context}Someone missed this conversation and wants to catch up.

Fill them in naturally - what happened, who said what, anything notable or important. Be conversational, like you're telling a friend what they missed. Keep it digestible.

The conversation:
{conversation_text}"""

        try:
            personality = self.bot.personality_manager.get_user_personality(str(author_id))
            system = self.bot._get_system_for_personality(personality, is_dm=False)

            result = await self.bot.model_client.complete(
                personality=personality,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.7,
            )
            self.bot._record_api_usage_from_result(result, "catchup",
                                                   user_id=author_id, channel_id=channel_id)

            footer = f"\n\n*{len(messages)} messages*"
            return result.text + footer

        except Exception as e:
            print(f"Error generating summary: {e}")
            participants = set(msg.get('author', 'Unknown') for msg in messages if msg.get('content'))
            return f"Couldn't generate a summary, but there were {len(messages)} messages from {', '.join(list(participants)[:5])}."
