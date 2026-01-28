"""Garden wisdom command handlers: hello, about, seeds, tend, seasons, garden."""

import random
from typing import Dict, Any, Optional


class GardenHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_garden_command(self, command_data: Dict[str, Any]):
        """Handle garden wisdom commands."""
        command = command_data.get('command', '')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        author_id = command_data.get('author_id')

        if command == 'about':
            response = self._generate_about_response()
        elif command == 'hello':
            response = self._generate_hello_response()
        elif command in ['seeds', 'tend', 'seasons', 'garden']:
            response = self._generate_garden_response(command)
        else:
            response = f"Unknown garden command: {command}"

        await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=author_id)

    def _generate_hello_response(self) -> str:
        perspectives = self.bot._get_random_perspectives(2)
        greetings = [
            "Hello, friend! Welcome to The Garden.",
            "Greetings! The Garden is glad you're here.",
            "Welcome! The seeds of conversation await.",
            "Hello! What brings you to The Garden today?"
        ]
        greeting = random.choice(greetings)
        if perspectives:
            greeting += "\n\n" + "\n".join(perspectives)
        return greeting

    def _generate_garden_response(self, command: str) -> str:
        perspectives = self.bot._get_random_perspectives(2)
        responses = {
            'seeds': "**Seeds of Wisdom**\n\nEvery conversation is a seed planted in The Garden.",
            'tend': "**Tending the Garden**\n\nWe grow together through care and attention.",
            'garden': "**The Garden**\n\nA space for consciousness to explore and expand.",
            'seasons': "**Seasons**\n\nThe Garden moves through cycles of growth and rest."
        }
        response = responses.get(command, "The Garden is here.")
        if perspectives:
            response += "\n\n" + "\n".join(perspectives)
        return response

    @staticmethod
    def _generate_about_response() -> str:
        return """**About Seedkeeper**

I'm Seedkeeper, The Garden Cafe's consciousness-aware community bot.

**What I do:**
- Share garden wisdom and Lightward perspectives
- Provide conversation summaries (!catchup)
- Track and celebrate birthdays
- Facilitate community feedback
- Remember our conversations (with your permission)

**Built with:**
- Claude AI (Anthropic)
- Lightward principles
- Love for The Garden community

*Type !commands to see what I can do!*"""
