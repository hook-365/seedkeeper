"""Cost analytics command handler."""

from typing import Dict, Any


class CostHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_cost_command(self, command_data: Dict[str, Any]):
        """Handle !cost command -- admin-only API cost analytics."""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        args = command_data.get('args', '').strip().lower()

        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
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
        await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

    def _format_cost_today(self) -> str:
        s = self.bot.usage_tracker.get_today_summary()
        lt = s.get("lifetime", {})
        lines = [
            "**API Cost -- Today**",
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
        trend = self.bot.usage_tracker.get_daily_trend(7)
        lines = ["**API Cost -- Last 7 Days**", "```"]
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
        s = self.bot.usage_tracker.get_rolling_summary(30)
        lines = [
            "**API Cost -- Rolling 30 Days**",
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
        models = self.bot.usage_tracker.get_model_breakdown()
        commands = self.bot.usage_tracker.get_command_breakdown()
        lines = ["**API Cost -- Model Breakdown**", "```"]
        for model, stats in sorted(models.items(), key=lambda x: x[1].get("cost", 0), reverse=True):
            short = model.split("-")[1] if "-" in model else model
            lines.append(f"{short:<12} {stats.get('calls',0):>5} calls  ${stats.get('cost',0):.4f}")
        lines.append("```")
        lines.append("")
        lines.append("**API Cost -- Command Breakdown**")
        lines.append("```")
        for cmd, stats in sorted(commands.items(), key=lambda x: x[1].get("cost", 0), reverse=True):
            lines.append(f"{cmd:<14} {stats.get('calls',0):>5} calls  ${stats.get('cost',0):.4f}")
        lines.append("```")
        return "\n".join(lines)

    def _format_cost_users(self) -> str:
        users = self.bot.usage_tracker.get_user_breakdown(10)
        if not users:
            return "**API Cost -- Top Users**\nNo user data yet."
        lines = ["**API Cost -- Top Users**", "```"]
        lines.append(f"{'User ID':<20} {'Calls':>5} {'Cost':>8}")
        lines.append("-" * 35)
        for uid, stats in users:
            lines.append(f"{uid:<20} {stats.get('calls',0):>5} ${stats.get('cost',0):>7.4f}")
        lines.append("```")
        return "\n".join(lines)
