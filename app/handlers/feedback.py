"""Feedback command handler."""

import os
from typing import Dict, Any


class FeedbackHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_feedback_command(self, command_data: Dict[str, Any]):
        """Handle feedback collection command."""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        args = command_data.get('args', '').strip()
        is_dm = command_data.get('is_dm', False)

        # Admin commands respond in the same channel
        if self.bot.admin_manager.is_admin(author_id) and args in ['summary', 'pending', 'get', 'help']:
            if args == 'help':
                help_text = """**Admin Feedback Commands**

**Available commands:**
- `!feedback pending` - Get all unread feedback
- `!feedback summary` - View statistics and trends
- `!feedback help` - Show this help message

**Regular users:**
- `!feedback` - Start a feedback session (moves to DM)"""
                await self.bot.send_message(channel_id, help_text, is_dm=is_dm, author_id=author_id)
                return

            elif args in ('pending', 'get'):
                pending = self.bot.feedback_manager.get_pending_feedback_for_owner()
                if pending:
                    feedback_text = "**Pending Anonymous Feedback:**\n"
                    for item in pending:
                        feedback_text += f"\n**Feature:** {item['feature']}\n"
                        feedback_text += f"**Interest:** {item['interest']}\n"
                        feedback_text += f"**Details:** {item.get('details', 'No details provided')}\n"
                        feedback_text += f"**When:** {item.get('timestamp', 'Unknown')}\n"
                        feedback_text += "---\n"
                    await self.bot.send_message(channel_id, feedback_text[:1900], is_dm=is_dm, author_id=author_id)
                    self.bot.feedback_manager.acknowledge_pending_feedback()
                else:
                    await self.bot.send_message(channel_id,
                        "No pending feedback to review.",
                        is_dm=is_dm, author_id=author_id)
                return

            elif args == 'summary':
                summary = self.bot.feedback_manager.get_feedback_summary()
                if summary['total'] == 0:
                    await self.bot.send_message(channel_id,
                        "No feedback collected yet.",
                        is_dm=is_dm, author_id=author_id)
                    return

                summary_text = f"**Feedback Summary Report**\n"
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
                        summary_text += f"  Responses: {stats['count']}\n"
                        summary_text += f"  Interested: {stats['interested']} users ({interest_rate:.0f}%)\n"
                        summary_text += f"  Not interested: {stats['count'] - stats['interested']} users\n\n"

                await self.bot.send_message(channel_id, summary_text[:1900], is_dm=is_dm, author_id=author_id)
                return

        # Regular feedback -- redirect to DMs
        if not is_dm:
            await self.bot.send_message(channel_id,
                "I've sent you a DM to collect your feedback privately!",
                is_dm=False, author_id=author_id)
            is_dm = True

        # Start a new feedback session
        result = self.bot.feedback_manager.start_feedback_session(author_id, channel_id, args or None)

        if not result['success']:
            await self.bot.send_message(channel_id,
                result['message'],
                is_dm=is_dm, author_id=author_id)
            return

        feature = result['feature']
        prompt = f"""**Garden Feature Feedback Session**

Welcome! I'd love to hear your thoughts on potential features for The Garden Cafe.

**How this works:**
1. I'll suggest a feature idea
2. You share if it interests you (or type 'skip')
3. Optionally, tell me what aspects would be valuable
4. Choose whether to share anonymously with development

**Today's feature idea:**
**"{feature}"**

**What do you think?** Would this be interesting or useful to you?

*Just type your response here in our DM. Type 'cancel' anytime to exit.*"""

        await self.bot.send_message(channel_id, prompt, is_dm=is_dm, author_id=author_id)
