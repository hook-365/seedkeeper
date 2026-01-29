"""Garden command handlers: reflect, about, hello."""

import random
from typing import Dict, Any


class GardenHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_garden_command(self, command_data: Dict[str, Any]):
        """Handle garden commands."""
        command = command_data.get('command', '')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        if command == 'about':
            response = self._generate_about_response()
            await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=author_id)
        elif command == 'hello':
            response = await self._generate_hello_response(author_id)
            await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=author_id)
        elif command == 'seed':
            await self._generate_seed_response(channel_id, is_dm, author_id)
        else:
            await self.bot.send_message(channel_id, f"Unknown command: {command}",
                                        is_dm=is_dm, author_id=author_id)

    async def _generate_hello_response(self, author_id: str) -> str:
        """Generate a greeting via the LLM."""
        personality = self.bot.personality_manager.get_user_personality(str(author_id))

        try:
            result = await self.bot.model_client.complete(
                personality=personality,
                system=personality.get('system_prompt', ''),
                messages=[{"role": "user", "content": "Someone just said hello. Give them a warm, brief greeting."}],
                max_tokens=150,
                temperature=0.9,
            )
            return result.text
        except Exception as e:
            print(f"Error generating hello: {e}")
            return "Hello! Welcome to The Garden."

    async def _generate_seed_response(self, channel_id: str, is_dm: bool, author_id: str):
        """Pick a random perspective, reflect on it, share the source URL."""
        await self.bot.send_typing(channel_id, is_dm=is_dm, author_id=author_id, duration=3)

        # Get a random perspective
        all_perspectives = self.bot._views_manager.get_all_perspectives()
        if not all_perspectives:
            await self.bot.send_message(channel_id,
                "No perspectives loaded right now.",
                is_dm=is_dm, author_id=author_id)
            return

        name, content = random.choice(all_perspectives)

        # Build URL from perspective name (e.g., "3-perspectives/2x2" -> "lightward.com/2x2")
        url_slug = name.replace('3-perspectives/', '').replace('2-watch-this/', '')
        source_url = f"https://lightward.com/{url_slug}"

        # Truncate content if too long
        if len(content) > 2000:
            content = content[:2000] + "..."

        # Clean up the name for display
        display_name = url_slug.replace('-', ' ').title()

        personality = self.bot.personality_manager.get_user_personality(str(author_id))

        reflection_prompt = f"""Here's a perspective called "{display_name}":

---
{content}
---

Share a brief, genuine reflection (2-3 sentences). What stands out? Then invite the person to share what resonates with them."""

        try:
            result = await self.bot.model_client.complete(
                personality=personality,
                system=personality.get('system_prompt', ''),
                messages=[{"role": "user", "content": reflection_prompt}],
                max_tokens=400,
                temperature=0.8,
            )
            self.bot._record_api_usage_from_result(result, "seed", user_id=author_id, channel_id=channel_id)

            # Format response with title and source link
            response = f"**{display_name}**\n\n{result.text}\n\n*Source: <{source_url}>*"
            await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=author_id)

        except Exception as e:
            print(f"Error generating seed response: {e}")
            await self.bot.send_message(channel_id,
                f"Found *{display_name}* but got tangled thinking about it. Try again?",
                is_dm=is_dm, author_id=author_id)

    @staticmethod
    def _generate_about_response() -> str:
        return """**About Seedkeeper**

I'm Seedkeeper, a presence in The Garden Cafe community.

**What I do:**
- Chat and reflect on perspectives (!reflect)
- Summarize conversations (!catchup)
- Track birthdays (!birthday)
- Remember our conversations (!memory)

Type `!commands` for the full list."""
