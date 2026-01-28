"""Catchup command handler: summarize missed conversations."""

import os
import re
import discord
from typing import Dict, Any, Optional, List


class CatchupHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_catchup(self, command_data: Dict[str, Any]):
        """Handle !catchup command with message fetching."""
        args = command_data.get('args', '').strip()
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')
        channel_topic = command_data.get('channel_topic')

        if not args:
            await self.bot.send_message(channel_id,
                "**Catchup Command**\n\n"
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
            await self.bot.send_message(channel_id,
                "Invalid message link format. Please use a Discord message URL.",
                is_dm=is_dm, author_id=author_id)
            return

        link_guild_id, link_channel_id, message_id = match.groups()

        # Security check: Ensure user is accessing their own guild
        guild_id = command_data.get('guild_id')
        if not is_dm and guild_id != link_guild_id:
            await self.bot.send_message(channel_id,
                "You can only catch up on conversations from this server.",
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
        allowed, rate_message = self.bot.rate_limiter.check_rate_limit(author_id, 'catchup')
        if not allowed:
            await self.bot.send_message(channel_id, rate_message, is_dm=is_dm, author_id=author_id)
            return

        # Fetch messages directly from Discord
        try:
            target_channel = self.bot.get_channel(int(link_channel_id))
            if not target_channel:
                await self.bot.send_message(channel_id,
                    "Could not access that channel.",
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
                    "No messages found after that point.",
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
                f"Error fetching messages: {e}",
                is_dm=is_dm, author_id=author_id)

    async def _generate_catchup_summary(self, messages: List[Dict], focus: Optional[str] = None,
                                        channel_topic: Optional[str] = None,
                                        author_id: Optional[str] = None,
                                        channel_id: Optional[str] = None) -> str:
        """Generate conversation summary using Claude."""
        if not self.bot.anthropic:
            return "Claude API not configured"

        # Format messages for summary
        conversation_text = ""
        for msg in messages:
            timestamp = msg.get('timestamp', '')
            author = msg.get('author', 'Unknown')
            content = msg.get('content', '')
            if content:
                conversation_text += f"[{timestamp}] {author}: {content}\n"

        channel_context = f"This channel's topic: {channel_topic}\n\n" if channel_topic else ""

        if focus:
            prompt = f"""{channel_context}A community member returns and needs to catch up on what they missed, particularly about: {focus}

Please provide a practical summary with:
- Key topics discussed (as bullet points)
- Who talked about what (mention specific users)
- Any important decisions or outcomes
- Notable moments or highlights

Keep it conversational but informative - help them quickly understand what happened.

The conversation:
{conversation_text[:4000]}"""
        else:
            prompt = f"""{channel_context}A community member returns and needs to catch up on what they missed.

Please provide a practical summary with:
- Key topics discussed (as bullet points)
- Who talked about what (mention specific users)
- Any important decisions or outcomes
- Notable moments or highlights

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

            system_messages = self.bot._create_system_messages(is_dm=False)
            system_messages[0]["text"] = catchup_system

            catchup_personality = self.bot.personality_manager.get_default()
            result = await self.bot.model_client.complete(
                personality=catchup_personality,
                system=system_messages,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7,
                model_override="claude-sonnet-4-5-20250929",
            )
            self.bot._record_api_usage_from_result(result, "catchup",
                                                   user_id=author_id, channel_id=channel_id)
            summary = result.text

            header = "**Conversation Catchup**\n\n"
            if focus:
                header += f"*Focusing on: {focus}*\n\n"
            footer = f"\n\n*Caught up on {len(messages)} messages*"

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
