"""Activity insights command handler - the secret sauce dashboard."""

from typing import Dict, Any


class InsightsHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_insights_command(self, command_data: Dict[str, Any]):
        """Handle !insights command -- admin-only activity dashboard."""
        author_id = command_data.get('author_id')
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)
        args = command_data.get('args', '').strip().lower()

        subcommand = args.split()[0] if args else "summary"

        if subcommand == "summary" or subcommand == "":
            text = self._format_summary()
        elif subcommand == "today":
            text = self._format_today()
        elif subcommand == "peak":
            text = self._format_peak_hours()
        elif subcommand == "trend":
            text = self._format_trend()
        elif subcommand == "commands":
            text = self._format_command_stats()
        elif subcommand == "lifetime":
            text = self._format_lifetime()
        elif subcommand in ("llm", "tokens", "model"):
            text = self._format_llm_usage()
        elif subcommand == "full":
            sections = [
                self._format_summary(),
                self._format_llm_summary(),
                self._format_trend(),
                self._format_command_stats(),
                self._format_peak_hours(),
            ]
            text = "\n\n".join(sections)
        else:
            text = self._format_help()

        # Truncate if too long
        if len(text) > 1900:
            text = text[:1900] + "\n..."

        await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

    def _format_summary(self) -> str:
        """Quick 24-hour summary with sparkline."""
        tracker = self.bot.activity_tracker
        summary = tracker.get_24h_summary()
        peak = tracker.get_peak_hours()
        sparkline = tracker.get_sparkline(7)
        avg_response = tracker.get_avg_response_time()

        # Get LLM stats for today
        llm = self.bot.usage_tracker.get_today_summary()

        lines = [
            "**Insights -- Last 24 Hours**",
            "",
            f"Messages: **{summary['messages']}**  |  Users: **{summary['unique_users']}**",
            f"Commands: **{summary['commands']}**  |  DMs: **{summary['dms']}**  |  Mentions: **{summary['mentions']}**",
        ]

        # LLM usage line
        if llm.get('calls', 0) > 0:
            tokens = llm.get('input_tokens', 0) + llm.get('output_tokens', 0)
            lines.append(f"LLM calls: **{llm['calls']}**  |  Tokens: **{tokens:,}**")

        if peak["peak_hour"] is not None:
            lines.append(f"Peak hour: **{tracker.format_hour(peak['peak_hour'])}**")

        if avg_response > 0:
            lines.append(f"Avg response: **{avg_response / 1000:.1f}s**")

        lines.extend([
            "",
            f"7-day trend: `{sparkline}`",
            "",
            "*`!insights full` for complete dashboard*",
        ])

        return "\n".join(lines)

    def _format_today(self) -> str:
        """Detailed today stats."""
        tracker = self.bot.activity_tracker
        today = tracker.get_today_detailed()

        lines = [
            f"**Insights -- Today ({today['date']})**",
            "",
            f"Messages: {today['messages']}",
            f"Unique users: {today['unique_users']}",
            f"Commands: {today['commands']}",
            f"DMs: {today['dms']}",
            f"Mentions: {today['mentions']}",
            f"Responses: {today['responses']}",
        ]

        if today['avg_response_ms'] > 0:
            lines.append(f"Avg response: {today['avg_response_ms'] / 1000:.1f}s")

        if today['top_commands']:
            lines.append("")
            lines.append("**Top Commands Today**")
            for cmd, count in today['top_commands']:
                lines.append(f"  `!{cmd}`: {count}")

        return "\n".join(lines)

    def _format_peak_hours(self) -> str:
        """Peak hours analysis with hourly distribution."""
        tracker = self.bot.activity_tracker
        peak = tracker.get_peak_hours()

        lines = [
            "**Insights -- Peak Hours**",
            "",
        ]

        if peak["peak_hour"] is None:
            lines.append("Not enough data yet.")
            return "\n".join(lines)

        lines.extend([
            f"Busiest: **{tracker.format_hour(peak['peak_hour'])}** ({peak['peak_count']} msgs)",
            f"Quietest: **{tracker.format_hour(peak['quiet_hour'])}** ({peak['quiet_count']} msgs)",
            "",
            "```",
        ])

        # Create a compact bar chart
        dist = peak["distribution"]
        max_val = max(dist.values()) if dist.values() else 1

        for hour in range(24):
            count = dist.get(hour, 0)
            bar_len = int((count / max_val) * 15) if max_val > 0 else 0
            bar = "█" * bar_len
            time_label = f"{hour:02d}"
            lines.append(f"{time_label} {bar} {count}")

        lines.append("```")
        return "\n".join(lines)

    def _format_trend(self) -> str:
        """7-day trend with daily breakdown."""
        tracker = self.bot.activity_tracker
        trend = tracker.get_weekly_trend()
        sparkline = tracker.get_sparkline(7)

        # Get LLM daily trend too
        llm_trend = self.bot.usage_tracker.get_daily_trend(7)

        lines = [
            "**Insights -- 7-Day Trend**",
            "",
            f"Activity: `{sparkline}`",
            "",
            "```",
            f"{'Date':<8} {'Msgs':>5} {'Users':>5} {'LLM':>5}",
            "-" * 27,
        ]

        # Merge activity and LLM data
        llm_by_date = {d['date']: d for d in llm_trend}

        for day in trend:
            short_date = day['date'][5:]  # MM-DD
            llm_day = llm_by_date.get(day['date'], {})
            llm_calls = llm_day.get('calls', 0)
            lines.append(
                f"{short_date:<8} {day['messages']:>5} "
                f"{day['unique_users']:>5} {llm_calls:>5}"
            )

        lines.append("```")

        # Calculate week totals
        total_msgs = sum(d['messages'] for d in trend)
        avg_daily = total_msgs / 7 if trend else 0

        lines.extend([
            f"Week total: **{total_msgs}** msgs  |  Avg: **{avg_daily:.0f}**/day",
        ])

        return "\n".join(lines)

    def _format_command_stats(self) -> str:
        """Command usage leaderboard."""
        tracker = self.bot.activity_tracker
        commands = tracker.get_command_leaderboard(30)

        lines = [
            "**Insights -- Top Commands (30d)**",
            "",
        ]

        if not commands:
            lines.append("No command data yet.")
            return "\n".join(lines)

        lines.append("```")
        for cmd, count in list(commands.items())[:8]:
            lines.append(f"!{cmd:<12} {count:>4}")
        lines.append("```")

        total = sum(commands.values())
        lines.append(f"Total: **{total}** commands")

        return "\n".join(lines)

    def _format_lifetime(self) -> str:
        """All-time statistics combining activity and LLM."""
        tracker = self.bot.activity_tracker
        stats = tracker.get_lifetime_stats()
        llm = self.bot.usage_tracker.get_today_summary().get('lifetime', {})

        lines = [
            "**Insights -- Lifetime Stats**",
            "",
            "**Activity**",
            f"  Messages: {stats['total_messages']:,}",
            f"  Commands: {stats['total_commands']:,}",
            f"  DMs: {stats['total_dms']:,}",
            f"  Mentions: {stats['total_mentions']:,}",
            f"  Unique users: {stats['total_unique_users']:,}",
            "",
            "**LLM Usage**",
            f"  Calls: {llm.get('total_calls', 0):,}",
            f"  Tokens in: {llm.get('total_input_tokens', 0):,}",
            f"  Tokens out: {llm.get('total_output_tokens', 0):,}",
        ]

        if stats.get('first_tracked') or llm.get('first_tracked'):
            first = stats.get('first_tracked') or llm.get('first_tracked')
            lines.append(f"\nTracking since: **{first}**")

        return "\n".join(lines)

    def _format_llm_usage(self) -> str:
        """Detailed LLM/token usage stats."""
        tracker = self.bot.usage_tracker
        today = tracker.get_today_summary()
        lt = today.get('lifetime', {})
        models = tracker.get_model_breakdown()
        commands = tracker.get_command_breakdown()

        lines = [
            "**Insights -- LLM Usage**",
            "",
            "**Today**",
            f"  Calls: {today.get('calls', 0)}",
            f"  Tokens: {today.get('input_tokens', 0):,} in / {today.get('output_tokens', 0):,} out",
            "",
            "**Lifetime**",
            f"  Calls: {lt.get('total_calls', 0):,}",
            f"  Tokens: {lt.get('total_input_tokens', 0):,} in / {lt.get('total_output_tokens', 0):,} out",
        ]

        if models:
            lines.append("")
            lines.append("**By Model**")
            for model, stats in sorted(models.items(), key=lambda x: x[1].get("calls", 0), reverse=True):
                short = model.split("/")[-1] if "/" in model else model
                short = short[:20]
                lines.append(f"  {short}: {stats.get('calls', 0)} calls")

        if commands:
            lines.append("")
            lines.append("**By Type**")
            for cmd, stats in sorted(commands.items(), key=lambda x: x[1].get("calls", 0), reverse=True)[:5]:
                lines.append(f"  {cmd}: {stats.get('calls', 0)} calls")

        return "\n".join(lines)

    def _format_llm_summary(self) -> str:
        """Compact LLM summary for full view."""
        tracker = self.bot.usage_tracker
        today = tracker.get_today_summary()
        lt = today.get('lifetime', {})
        rolling = tracker.get_rolling_summary(30)

        total_tokens = lt.get('total_input_tokens', 0) + lt.get('total_output_tokens', 0)

        lines = [
            "**Insights -- LLM Stats**",
            "",
            f"Today: **{today.get('calls', 0)}** calls",
            f"30-day: **{rolling.get('calls', 0)}** calls",
            f"Lifetime: **{lt.get('total_calls', 0):,}** calls, **{total_tokens:,}** tokens",
        ]

        return "\n".join(lines)

    def _format_help(self) -> str:
        """Help text for insights command."""
        return """**Insights Dashboard**

`!insights` - Quick summary
`!insights today` - Today's details
`!insights trend` - 7-day breakdown
`!insights peak` - Hourly patterns
`!insights commands` - Command leaderboard
`!insights llm` - LLM/token usage
`!insights lifetime` - All-time stats
`!insights full` - Everything"""
