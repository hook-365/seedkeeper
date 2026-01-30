"""Birthday command handler: all birthday subcommands."""

import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Tuple

from zodiac import format_sign_display, get_western_zodiac, get_chinese_zodiac


# Month name lookup for flexible date parsing
MONTH_NAMES = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
    'july': 7, 'jul': 7, 'august': 8, 'aug': 8,
    'september': 9, 'sept': 9, 'sep': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
}


def _normalize_year(y: int) -> int:
    """Convert 2-digit year to 4-digit: 0-29 → 2000s, 30-99 → 1900s."""
    if 0 <= y <= 29:
        return 2000 + y
    if 30 <= y <= 99:
        return 1900 + y
    return y


def parse_date_input(date_str: str) -> Tuple[int, int, Optional[int]]:
    """
    Parse a flexible date string into (month, day, year|None).

    Accepted formats:
      - ISO: 1990-03-15
      - Month name: March 15, Mar 15 1990, 15 March, 15th Mar 1990
      - Numeric 3-part: 03/15/1990, 03-15-90, 15/03/1990
      - Numeric 2-part: 03-15, 03/15, 3/5

    For ambiguous numeric dates, if the first number > 12 it is treated as
    DD/MM; otherwise MM/DD (US default).

    Raises ValueError with a descriptive message on failure.
    """
    text = date_str.strip()
    if not text:
        raise ValueError("No date provided.")

    # Strip ordinal suffixes (1st, 2nd, 3rd, 4th, ...)
    cleaned = re.sub(r'(\d+)(?:st|nd|rd|th)\b', r'\1', text, flags=re.IGNORECASE)

    month = day = year = None

    # --- Pattern 1: ISO YYYY-MM-DD ---
    m = re.fullmatch(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', cleaned)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        return _validate_date(month, day, year)

    # --- Pattern 2: Month name + day (± year) ---
    # "March 15", "Mar 15 1990", "March 15, 1990"
    m = re.fullmatch(
        r'([a-zA-Z]+)\s+(\d{1,2})(?:\s*,?\s*(\d{2,4}))?', cleaned
    )
    if m and m.group(1).lower() in MONTH_NAMES:
        month = MONTH_NAMES[m.group(1).lower()]
        day = int(m.group(2))
        if m.group(3):
            year = _normalize_year(int(m.group(3)))
        return _validate_date(month, day, year)

    # "15 March", "15 Mar 1990"
    m = re.fullmatch(
        r'(\d{1,2})\s+([a-zA-Z]+)(?:\s+(\d{2,4}))?', cleaned
    )
    if m and m.group(2).lower() in MONTH_NAMES:
        day = int(m.group(1))
        month = MONTH_NAMES[m.group(2).lower()]
        if m.group(3):
            year = _normalize_year(int(m.group(3)))
        return _validate_date(month, day, year)

    # --- Pattern 3: 3-part numeric (slashes or dashes) ---
    m = re.fullmatch(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', cleaned)
    if m:
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = _normalize_year(c)
        if a > 12:
            # DD/MM/YYYY
            day, month = a, b
        else:
            # MM/DD/YYYY (US default)
            month, day = a, b
        return _validate_date(month, day, year)

    # --- Pattern 4: 2-part numeric ---
    m = re.fullmatch(r'(\d{1,2})[-/](\d{1,2})', cleaned)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            day, month = a, b
        else:
            month, day = a, b
        return _validate_date(month, day, None)

    raise ValueError(
        "Could not parse date. Try formats like: `03-15`, `03/15`, `March 15`, "
        "`Mar 15 1990`, `1990-03-15`, or `03-15-1990`."
    )


def _validate_date(month: int, day: int, year: Optional[int]) -> Tuple[int, int, Optional[int]]:
    """Validate month/day/year and return the tuple or raise ValueError."""
    if not (1 <= month <= 12):
        raise ValueError(f"Invalid month: {month}. Must be 1-12.")
    if not (1 <= day <= 31):
        raise ValueError(f"Invalid day: {day}. Must be 1-31.")
    try:
        if year is not None:
            datetime(year, month, day)
        else:
            datetime(2024, month, day)  # leap year for validation
    except ValueError:
        if year is not None:
            raise ValueError(f"Invalid date: {month}/{day}/{year}.")
        else:
            raise ValueError(f"Invalid date: {month}/{day}.")
    if year is not None and (year < 1900 or year > datetime.now().year):
        raise ValueError(f"Year {year} is out of range (1900-{datetime.now().year}).")
    return month, day, year


def fuzzy_match_user(name: str, nickname: Optional[str], members: List[Dict]) -> Tuple[Optional[Dict], float]:
    """
    Fuzzy match a name/nickname against server members.
    Returns (best_match, confidence) where confidence is 0-1.
    """
    best_match = None
    best_score = 0.0

    search_terms = [name.lower()]
    if nickname:
        search_terms.append(nickname.lower())

    for member in members:
        member_names = [
            member.get('name', '').lower(),
            member.get('nick', '').lower() if member.get('nick') else '',
            member.get('display_name', '').lower(),
        ]
        # Also check without special chars
        member_names.extend([re.sub(r'[^a-z0-9]', '', n) for n in member_names])

        for search in search_terms:
            search_clean = re.sub(r'[^a-z0-9]', '', search)
            for mname in member_names:
                if not mname:
                    continue

                # Exact match
                if search == mname or search_clean == mname:
                    return member, 1.0

                # Substring match
                if search in mname or mname in search:
                    score = 0.85
                    if score > best_score:
                        best_score = score
                        best_match = member
                    continue

                # Fuzzy match
                ratio = SequenceMatcher(None, search, mname).ratio()
                if ratio > best_score and ratio > 0.6:
                    best_score = ratio
                    best_match = member

                # Also try clean versions
                mname_clean = re.sub(r'[^a-z0-9]', '', mname)
                ratio_clean = SequenceMatcher(None, search_clean, mname_clean).ratio()
                if ratio_clean > best_score and ratio_clean > 0.6:
                    best_score = ratio_clean
                    best_match = member

    return best_match, best_score


class BirthdayHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_sign_command(self, command_data: Dict[str, Any]):
        """Handle !sign command - show zodiac signs."""
        args = command_data.get('args', '').strip()
        author_id = str(command_data.get('author_id'))
        channel_id = command_data.get('channel_id')
        is_dm = command_data.get('is_dm', False)

        # Determine target user
        target_id = author_id
        target_name = None

        if args:
            # Check for @mention
            mention_match = re.match(r'<@!?(\d+)>', args)
            if mention_match:
                target_id = mention_match.group(1)

        # Look up birthday
        birthday_data = self.bot.birthday_manager.birthdays.get(target_id)

        if not birthday_data:
            if target_id == author_id:
                await self.bot.send_message(channel_id,
                    "I don't have your birthday on file. Use `!birthday mine <date>` to set it (e.g., `03-15` or `March 15`).",
                    is_dm=is_dm, author_id=author_id)
            else:
                await self.bot.send_message(channel_id,
                    "I don't have that person's birthday on file.",
                    is_dm=is_dm, author_id=author_id)
            return

        month = birthday_data['month']
        day = birthday_data['day']
        year = birthday_data.get('year')  # Optional
        name = birthday_data.get('name')

        # Try to get display name if not stored
        if not name and target_id != author_id:
            try:
                user = await self.bot.fetch_user(int(target_id))
                name = user.display_name if user else None
            except:
                pass

        display = format_sign_display(month, day, year, name)
        # Add tip if viewing own signs and year not set
        if target_id == author_id and not year:
            display += "\n\n💡 *Add your birth year with `!birthday year YYYY` to see your Chinese zodiac!*"
        await self.bot.send_message(channel_id, display, is_dm=is_dm, author_id=author_id)

    async def handle_birthday_command(self, command_data: Dict[str, Any]):
        """Handle birthday commands."""
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
`!birthday mine <date>` - Set your birthday
`!birthday year YYYY` - Add birth year to your existing birthday
`!birthday list` - Show upcoming birthdays (next 7 days)
`!birthday list all` - Show all registered birthdays
`!birthday upcoming [days]` - Show next N days
`!sign` - Show your zodiac signs
*Date formats:* `03-15`, `03/15`, `March 15`, `Mar 15 1990`, `1990-03-15`"""

            if self.bot.admin_manager.is_admin(str(author_id)):
                help_text += "\n\n**Admin Commands:**"
                help_text += "\n`!birthday set @user <date>` - Set birthday by mention"
                help_text += "\n`!birthday set <user_id> <date>` - Set birthday by ID"
                help_text += "\n`!birthday add username <date>` - Set birthday by name"
                help_text += "\n`!birthday remove [@user]` - Remove a birthday"
                help_text += "\n`!birthday parse [text]` - Parse birthdays from text"
                help_text += "\n`!birthday match` - Match parsed birthdays to users"
                help_text += "\n`!birthday confirm` - Confirm matched birthdays"
                help_text += "\n`!birthday scan` - Scan channel for birthdays"
                help_text += "\n`!birthday ask-years` - Post announcement asking for birth years"
                help_text += "\n`!birthday announce @user` - Manually trigger birthday announcement"

            await self.bot.send_message(channel_id, help_text, is_dm=is_dm, author_id=str(author_id))
            return

        subcommand = args[0].lower()

        if subcommand == 'mine' and len(args) >= 2:
            await self._handle_mine(args, author_id, channel_id, is_dm)
        elif subcommand == 'year' and len(args) >= 2:
            await self._handle_year(args, author_id, channel_id, is_dm)
        elif subcommand == 'ask-years':
            await self._handle_ask_years(author_id, channel_id, is_dm)
        elif subcommand == 'announce' and len(args) >= 2:
            await self._handle_announce(args, author_id, channel_id, is_dm)
        elif subcommand == 'remove':
            await self._handle_remove(args, author_id, channel_id, is_dm)
        elif subcommand == 'upcoming':
            await self._handle_upcoming(args, author_id, channel_id, is_dm)
        elif subcommand == 'parse' and len(args) >= 2:
            await self._handle_parse(args, author_id, channel_id, is_dm)
        elif subcommand == 'match':
            await self._handle_match(author_id, channel_id, is_dm, guild_id)
        elif subcommand == 'confirm':
            await self._handle_confirm(author_id, channel_id, is_dm)
        elif subcommand == 'add' and len(args) >= 3:
            await self._handle_add(args, author_id, channel_id, is_dm, guild_id)
        elif subcommand == 'set' and len(args) >= 3:
            await self._handle_set(args, author_id, channel_id, is_dm)
        elif subcommand == 'scan':
            await self._handle_scan(author_id, channel_id, is_dm, args=args, guild_id=guild_id)
        elif subcommand == 'list':
            await self._handle_list(args, author_id, channel_id, is_dm)
        else:
            await self.bot.send_message(channel_id,
                "Use `!birthday` to see available commands.", is_dm=is_dm, author_id=str(author_id))

    async def _handle_mine(self, args, author_id, channel_id, is_dm):
        birthday_str = ' '.join(args[1:])
        try:
            month, day, year = parse_date_input(birthday_str)
            success, message = self.bot.birthday_manager.set_birthday(
                str(author_id), month, day, str(author_id), method="manual", year=year
            )
            if success:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                if year:
                    await self.bot.send_message(channel_id,
                        f"🎂 Birthday set for {formatted}, {year}!", is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.bot.send_message(channel_id,
                        f"🎂 Birthday set for {formatted}!", is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"❌ {message}", is_dm=is_dm, author_id=str(author_id))
        except ValueError as e:
            await self.bot.send_message(channel_id,
                f"❌ {e}", is_dm=is_dm, author_id=str(author_id))

    async def _handle_year(self, args, author_id, channel_id, is_dm):
        """Handle !birthday year YYYY - add birth year to existing birthday."""
        try:
            year = int(args[1])
            success, message = self.bot.birthday_manager.set_year(str(author_id), year)
            if success:
                from zodiac import get_chinese_zodiac
                chinese = get_chinese_zodiac(year)
                await self.bot.send_message(channel_id,
                    f"🎂 Birth year set to {year}! You're a {chinese['emoji']} {chinese['animal']}!",
                    is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"❌ {message}", is_dm=is_dm, author_id=str(author_id))
        except ValueError:
            await self.bot.send_message(channel_id,
                "❌ Please provide a valid year (e.g., `!birthday year 1990`)",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_ask_years(self, author_id, channel_id, is_dm):
        """Handle !birthday ask-years - post announcement asking users to share birthday info."""
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "🚫 Only Garden Keepers can use this command.", is_dm=is_dm, author_id=str(author_id))
            return

        # Build current birthday status
        all_birthdays = self.bot.birthday_manager.get_all_birthdays()

        has_year = []
        no_year = []

        for user_id, data in all_birthdays.items():
            month, day = data['month'], data['day']
            western = get_western_zodiac(month, day)
            formatted_date = self.bot.birthday_manager.format_birthday_date(month, day)

            if data.get('year'):
                chinese = get_chinese_zodiac(data['year'])
                has_year.append(f"<@{user_id}> - {formatted_date} {western['symbol']}{chinese['emoji']}")
            else:
                no_year.append(f"<@{user_id}> - {formatted_date} {western['symbol']}")

        # Build the announcement
        announcement = "@everyone\n\n"
        announcement += "🎂 **Birthday & Zodiac Update!** 🎂\n\n"

        announcement += "We're tracking birthdays so we can celebrate together! "
        announcement += "Here's what we know so far:\n\n"

        if has_year or no_year:
            if has_year:
                announcement += "**✨ Complete profiles (with Chinese zodiac):**\n"
                for entry in has_year:
                    announcement += f"• {entry}\n"
                announcement += "\n"

            if no_year:
                announcement += "**📅 Birthdays tracked (no birth year yet):**\n"
                for entry in no_year:
                    announcement += f"• {entry}\n"
                announcement += "\n"
        else:
            announcement += "*No birthdays registered yet!*\n\n"

        announcement += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        announcement += "**📝 How to participate:**\n\n"

        announcement += "**Don't see your name?** Add your birthday:\n"
        announcement += "`!birthday mine <date>` (e.g., `!birthday mine June 15` or `!birthday mine 06-15`)\n"
        announcement += "Include your birth year too: `!birthday mine June 15 1990`\n\n"

        announcement += "**Already listed but want to add your year?**\n"
        announcement += "`!birthday year YYYY` (e.g., `!birthday year 1990`)\n\n"

        announcement += "**Check your zodiac signs anytime:** `!sign`\n\n"

        announcement += "*Birth year is optional and only used for Chinese zodiac display!* 🐉"

        await self.bot.send_message(channel_id, announcement, is_dm=is_dm, author_id=str(author_id))

    async def _handle_announce(self, args, author_id, channel_id, is_dm):
        """Handle !birthday announce @user - manually trigger a birthday announcement (admin only)."""
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "🚫 Only Garden Keepers can use this command.", is_dm=is_dm, author_id=str(author_id))
            return

        # Parse user mention or ID
        user_arg = args[1]
        user_match = re.match(r'<@!?(\d+)>', user_arg)
        if user_match:
            target_user_id = user_match.group(1)
        elif re.match(r'^\d{17,20}$', user_arg):
            target_user_id = user_arg
        else:
            await self.bot.send_message(channel_id,
                "❌ Please mention a user: `!birthday announce @user`",
                is_dm=is_dm, author_id=str(author_id))
            return

        # Check if user has a birthday registered
        birthday_data = self.bot.birthday_manager.birthdays.get(target_user_id)
        if not birthday_data:
            await self.bot.send_message(channel_id,
                "❌ That user doesn't have a birthday registered.",
                is_dm=is_dm, author_id=str(author_id))
            return

        # Get birthday channel
        birthday_channel_id = os.getenv('BIRTHDAY_CHANNEL_ID')
        if not birthday_channel_id:
            await self.bot.send_message(channel_id,
                "❌ BIRTHDAY_CHANNEL_ID not configured in environment.",
                is_dm=is_dm, author_id=str(author_id))
            return

        birthday_channel = self.bot.get_channel(int(birthday_channel_id))
        if not birthday_channel:
            await self.bot.send_message(channel_id,
                f"❌ Could not find birthday channel (ID: {birthday_channel_id}).",
                is_dm=is_dm, author_id=str(author_id))
            return

        await self.bot.send_message(channel_id,
            "🎂 Generating birthday announcement...", is_dm=is_dm, author_id=str(author_id))

        # Trigger the announcement
        try:
            await self.bot._announce_birthday(birthday_channel, target_user_id)
            await self.bot.send_message(channel_id,
                f"✅ Birthday announcement posted to <#{birthday_channel_id}>!",
                is_dm=is_dm, author_id=str(author_id))
        except Exception as e:
            await self.bot.send_message(channel_id,
                f"❌ Error posting announcement: {e}",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_remove(self, args, author_id, channel_id, is_dm):
        if len(args) >= 2:
            user_mention = args[1]
            user_match = re.match(r'<@!?(\d+)>', user_mention)
            target_id = user_match.group(1) if user_match else str(author_id)
            success, message = self.bot.birthday_manager.remove_birthday(target_id)
            msg = "🎂 Birthday removed!" if success else f"❌ {message}"
        else:
            success, message = self.bot.birthday_manager.remove_birthday(str(author_id))
            msg = "🎂 Your birthday has been removed." if success else f"❌ {message}"
        await self.bot.send_message(channel_id, msg, is_dm=is_dm, author_id=str(author_id))

    async def _handle_upcoming(self, args, author_id, channel_id, is_dm):
        days = 7
        if len(args) > 1:
            try:
                days = int(args[1])
            except ValueError:
                days = 7
        birthdays = self.bot.birthday_manager.get_upcoming_birthdays(days)
        if birthdays:
            text = f"🎂 **Upcoming Birthdays (next {days} days)**\n"
            for user_id, month, day, days_until in birthdays:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                if days_until == 0:
                    text += f"• <@{user_id}> - **Today!** {formatted} 🎉\n"
                elif days_until == 1:
                    text += f"• <@{user_id}> - Tomorrow ({formatted})\n"
                else:
                    text += f"• <@{user_id}> - {formatted} ({days_until} days)\n"
        else:
            text = f"No upcoming birthdays in the next {days} days! 🌱"
        await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

    async def _handle_parse(self, args, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "🚫 Only Garden Keepers can parse birthdays.", is_dm=is_dm, author_id=str(author_id))
            return

        text_to_parse = args[1].strip()
        if not text_to_parse:
            await self.bot.send_message(channel_id,
                "Please provide text to parse: `!birthday parse [text with names and dates]`",
                is_dm=is_dm, author_id=str(author_id))
            return
        results = self.bot.birthday_manager.parse_birthday_advanced(text_to_parse)
        if results:
            self.bot._set_temp(f"birthday_parse:{author_id}", results, 300)
            response = f"📋 Parsed {len(results)} birthdays:\n\n"
            for r in results[:20]:
                name = r.get('name', 'Unknown')
                nick = r.get('nickname', '')
                month = r.get('month', '?')
                day = r.get('day', '?')
                name_str = f"{name} ({nick})" if nick else name
                response += f"- {name_str}: {month:02d}-{day:02d}\n"
            response += "\nUse `!birthday match` to match to Discord users."
            await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))
        else:
            await self.bot.send_message(channel_id,
                "❌ Could not parse any birthdays from that text.",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_match(self, author_id, channel_id, is_dm, guild_id):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can match birthdays.", is_dm=is_dm, author_id=str(author_id))
            return

        # Check for parsed data from parse command or scan command
        parsed_data = self.bot._get_temp(f"birthday_parse:{author_id}")
        scan_data = self.bot._temp_state.get(f"birthday_scan_{author_id}", {}).get('birthdays')

        birthdays = parsed_data or scan_data
        if not birthdays:
            await self.bot.send_message(channel_id,
                "No parsed birthday data found. Use `!birthday parse [text]` or `!birthday scan [link]` first.",
                is_dm=is_dm, author_id=str(author_id))
            return

        members = await self.bot._get_guild_members(guild_id) if guild_id else []
        if not members:
            error_msg = (
                "**Could not fetch server members.**\n\n"
                "To fix this:\n"
                "1. Go to Discord Developer Portal > Your App > Bot\n"
                "2. Enable **Server Members Intent** under Privileged Gateway Intents\n"
                "3. Restart the bot\n\n"
                "**Workaround:** Use `!birthday set <user_id> MM-DD` to add birthdays by ID.\n"
                "Example: `!birthday set 764630517197963274 01-07`"
            )
            await self.bot.send_message(channel_id, error_msg, is_dm=is_dm, author_id=str(author_id))
            return

        response = "**Birthday Matching**\n\n"
        matched = []
        unmatched = []

        for b in birthdays:
            name = b.get('name', '')
            nickname = b.get('nickname')

            match, confidence = fuzzy_match_user(name, nickname, members)

            if match and confidence >= 0.6:
                b['matched_user'] = match
                b['confidence'] = confidence
                matched.append(b)
            else:
                unmatched.append(b)

        # Store for confirmation
        self.bot._temp_state[f"birthday_matched_{author_id}"] = {
            'matched': matched,
            'unmatched': unmatched,
            'expires': (datetime.now() + timedelta(minutes=10)).isoformat()
        }

        if matched:
            response += f"**Matched ({len(matched)}):**\n"
            for b in sorted(matched, key=lambda x: (x['month'], x['day'])):
                user = b['matched_user']
                conf = b['confidence']
                conf_str = "exact" if conf >= 0.95 else f"{conf:.0%}"
                name_str = b.get('name', '?')
                if b.get('nickname'):
                    name_str += f" ({b['nickname']})"
                response += f"- {b['month']}/{b['day']} {name_str} -> <@{user['id']}> [{conf_str}]\n"

        if unmatched:
            response += f"\n**No match found ({len(unmatched)}):**\n"
            for b in unmatched:
                name_str = b.get('name', '?')
                if b.get('nickname'):
                    name_str += f" ({b['nickname']})"
                response += f"- {b['month']}/{b['day']} {name_str}\n"

        response += "\n`!birthday confirm` to save matched birthdays."
        await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))

    async def _handle_confirm(self, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can confirm birthday additions.",
                is_dm=is_dm, author_id=str(author_id))
            return

        # Check both old and new storage locations
        matched_data = self.bot._get_temp(f"birthday_matched:{author_id}")
        if not matched_data:
            new_data = self.bot._temp_state.get(f"birthday_matched_{author_id}", {})
            matched_data = new_data.get('matched', [])

        if not matched_data:
            await self.bot.send_message(channel_id,
                "No matched birthday data found. Run `!birthday parse` or `!birthday scan`, then `!birthday match` first.",
                is_dm=is_dm, author_id=str(author_id))
            return

        added_count = 0
        failed_count = 0
        response = "**Adding matched birthdays...**\n\n"

        for b in matched_data:
            if 'matched_user' in b:
                uid = b['matched_user']['id']
                month = b['month']
                day = b['day']
                name = b.get('name')
                success, message = self.bot.birthday_manager.set_birthday(
                    uid, month, day, str(author_id), method="batch_import", name=name
                )
                if success:
                    added_count += 1
                    response += f"Added <@{uid}> - {month}/{day}\n"
                else:
                    failed_count += 1
                    response += f"Failed <@{uid}>: {message}\n"

        response += f"\n**Done:** {added_count} added"
        if failed_count > 0:
            response += f", {failed_count} failed"

        # Clean up temp data
        self.bot._del_temp(f"birthday_matched:{author_id}")
        if f"birthday_matched_{author_id}" in self.bot._temp_state:
            del self.bot._temp_state[f"birthday_matched_{author_id}"]
        if f"birthday_scan_{author_id}" in self.bot._temp_state:
            del self.bot._temp_state[f"birthday_scan_{author_id}"]

        await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))

    async def _handle_add(self, args, author_id, channel_id, is_dm, guild_id):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "🚫 Only Garden Keepers can add birthdays.", is_dm=is_dm, author_id=str(author_id))
            return

        username = args[1].lower()
        if username.startswith('@'):
            username = username[1:]
        birthday_str = ' '.join(args[2:])

        target_guild_id = guild_id or os.getenv('DEFAULT_GUILD_ID', '1336444334479769711')
        await self.bot.send_message(channel_id,
            f"🔍 Searching for user '{username}'...", is_dm=is_dm, author_id=str(author_id))

        members = await self.bot._get_guild_members(target_guild_id)
        if not members:
            error_msg = (
                "❌ **Could not fetch server members.**\n\n"
                "Try using `!birthday set <user_id> <date>` instead.\n"
                "Example: `!birthday set 764630517197963274 01-07`"
            )
            await self.bot.send_message(channel_id, error_msg, is_dm=is_dm, author_id=str(author_id))
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
            await self.bot.send_message(channel_id,
                f"❌ Could not find user '{username}'.", is_dm=is_dm, author_id=str(author_id))
            return

        target_user_id = matched_user['id']
        try:
            month, day, year = parse_date_input(birthday_str)
            success, message = self.bot.birthday_manager.set_birthday(
                target_user_id, month, day, str(author_id),
                method="admin_add", name=matched_user['display_name'], year=year
            )
            if success:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                if year:
                    await self.bot.send_message(channel_id,
                        f"🎂 Birthday added for **{matched_user['display_name']}**: {formatted}, {year}!",
                        is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.bot.send_message(channel_id,
                        f"🎂 Birthday added for **{matched_user['display_name']}**: {formatted}!",
                        is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"❌ {message}",
                    is_dm=is_dm, author_id=str(author_id))
        except ValueError as e:
            await self.bot.send_message(channel_id,
                f"❌ {e}",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_set(self, args, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "🚫 Only Garden Keepers can set others' birthdays.",
                is_dm=is_dm, author_id=str(author_id))
            return

        user_arg = args[1]
        birthday_str = ' '.join(args[2:])

        # Support both @mention and raw user ID (17-20 digit Discord snowflake)
        user_match = re.match(r'<@!?(\d+)>', user_arg)
        if user_match:
            target_user_id = user_match.group(1)
        elif re.match(r'^\d{17,20}$', user_arg):
            # Raw Discord user ID (snowflake format)
            target_user_id = user_arg
        else:
            await self.bot.send_message(channel_id,
                "❌ Please mention a user or provide their ID:\n"
                "`!birthday set @user <date>`\n"
                "`!birthday set 764630517197963274 03-15`",
                is_dm=is_dm, author_id=str(author_id))
            return
        try:
            month, day, year = parse_date_input(birthday_str)
            success, message = self.bot.birthday_manager.set_birthday(
                target_user_id, month, day, str(author_id), method="admin_set", year=year
            )
            if success:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                if year:
                    await self.bot.send_message(channel_id,
                        f"🎂 Birthday set for <@{target_user_id}>: {formatted}, {year}!",
                        is_dm=is_dm, author_id=str(author_id))
                else:
                    await self.bot.send_message(channel_id,
                        f"🎂 Birthday set for <@{target_user_id}>: {formatted}!",
                        is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"❌ {message}",
                    is_dm=is_dm, author_id=str(author_id))
        except ValueError as e:
            await self.bot.send_message(channel_id,
                f"❌ {e}",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_scan(self, author_id, channel_id, is_dm, args=None, guild_id=None):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can scan for birthdays.",
                is_dm=is_dm, author_id=str(author_id))
            return

        # If no message link provided, show usage
        if not args or len(args) < 2:
            await self.bot.send_message(channel_id,
                "**Birthday Scan**\n\n"
                "Scan channel history for birthday mentions.\n\n"
                "Usage: `!birthday scan [message_link]`\n\n"
                "I'll scan from that message forward and find any birthdays mentioned.",
                is_dm=is_dm, author_id=str(author_id))
            return

        message_link = args[1]

        # Parse Discord message link
        link_pattern = r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)'
        match = re.match(link_pattern, message_link)

        if not match:
            await self.bot.send_message(channel_id,
                "That doesn't look like a Discord message link. Right-click a message and 'Copy Message Link'.",
                is_dm=is_dm, author_id=str(author_id))
            return

        link_guild_id, link_channel_id, message_id = match.groups()

        # Security check
        if guild_id and guild_id != link_guild_id:
            await self.bot.send_message(channel_id,
                "I can only scan channels from this server.",
                is_dm=is_dm, author_id=str(author_id))
            return

        await self.bot.send_message(channel_id,
            "🔍 *Scanning channel for birthday mentions...*",
            is_dm=is_dm, author_id=str(author_id))

        try:
            import discord
            target_channel = self.bot.get_channel(int(link_channel_id))
            if not target_channel:
                await self.bot.send_message(channel_id,
                    "I can't access that channel.",
                    is_dm=is_dm, author_id=str(author_id))
                return

            found_birthdays = []
            scanned = 0

            async for msg in target_channel.history(limit=500, after=discord.Object(id=int(message_id))):
                scanned += 1
                content = msg.content

                # Try structured list parsing first
                list_results = self.bot.birthday_manager.parse_birthday_list(content)
                if list_results:
                    for r in list_results:
                        found_birthdays.append({
                            'name': r.get('name', 'Unknown'),
                            'month': r['month'],
                            'day': r['day'],
                            'source': f"List format in message by {msg.author.name}",
                            'username': r.get('username')
                        })

                # Try advanced parsing
                advanced_results = self.bot.birthday_manager.parse_birthday_advanced(content)
                for r in advanced_results:
                    if r.get('month') and r.get('day'):
                        found_birthdays.append({
                            'name': r.get('name', msg.author.name),
                            'month': r['month'],
                            'day': r['day'],
                            'source': f"Mentioned by {msg.author.name}",
                            'confidence': r.get('confidence', 0.5)
                        })

            if not found_birthdays:
                await self.bot.send_message(channel_id,
                    f"Scanned {scanned} messages but didn't find any birthday mentions.\n\n"
                    "Tip: You can also paste birthday text directly with `!birthday parse [text]`",
                    is_dm=is_dm, author_id=str(author_id))
                return

            # Deduplicate by name
            seen = set()
            unique = []
            for b in found_birthdays:
                key = (b.get('name', '').lower(), b['month'], b['day'])
                if key not in seen:
                    seen.add(key)
                    unique.append(b)

            # Store for confirmation
            self.bot._temp_state[f'birthday_scan_{author_id}'] = {
                'birthdays': unique,
                'expires': (datetime.now() + timedelta(minutes=10)).isoformat()
            }

            # Format results
            month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            result_text = f"**Found {len(unique)} potential birthdays** (scanned {scanned} messages)\n\n"
            for i, b in enumerate(unique[:20], 1):  # Limit display to 20
                date_str = f"{month_names[b['month']]} {b['day']}"
                result_text += f"{i}. **{b.get('name', 'Unknown')}** - {date_str}\n"

            if len(unique) > 20:
                result_text += f"\n*...and {len(unique) - 20} more*\n"

            result_text += "\n\nUse `!birthday match` to match these to Discord users, then `!birthday confirm` to save."

            await self.bot.send_message(channel_id, result_text, is_dm=is_dm, author_id=str(author_id))

        except Exception as e:
            print(f"Error scanning for birthdays: {e}")
            await self.bot.send_message(channel_id,
                f"Error scanning channel: {e}",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_list(self, args, author_id, channel_id, is_dm):
        if len(args) > 1 and args[1].lower() == 'all':
            all_birthdays = self.bot.birthday_manager.get_all_birthdays()
            if all_birthdays:
                months = {}
                for user_id, data in all_birthdays.items():
                    month = data['month']
                    if month not in months:
                        months[month] = []
                    months[month].append((user_id, data['day'], data.get('name', 'Unknown'), data.get('year')))

                text = "🎂 **All Registered Birthdays**\n"
                text += f"*Total: {len(all_birthdays)} birthdays*\n\n"

                month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                               'July', 'August', 'September', 'October', 'November', 'December']

                for month in sorted(months.keys()):
                    text += f"**{month_names[month]}**\n"
                    for user_id, day, name, year in sorted(months[month], key=lambda x: x[1]):
                        formatted_date = self.bot.birthday_manager.format_birthday_date(month, day)
                        # Get zodiac symbols
                        western = get_western_zodiac(month, day)
                        zodiac_str = western['symbol']
                        if year:
                            chinese = get_chinese_zodiac(year)
                            zodiac_str += chinese['emoji']
                        if name and name != 'Unknown':
                            text += f"- {name} (<@{user_id}>) - {formatted_date} {zodiac_str}\n"
                        else:
                            text += f"- <@{user_id}> - {formatted_date} {zodiac_str}\n"

                text += "\n💡 Use `!birthday list` to see only upcoming birthdays"
            else:
                text = "No birthdays registered yet! 🌱\nUse `!birthday mine <date>` to add yours!"
        else:
            birthdays = self.bot.birthday_manager.get_upcoming_birthdays(7)
            if birthdays:
                text = "🎂 **Upcoming Birthdays (next 7 days)**\n"
                for user_id, month, day, days_until in birthdays:
                    formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                    # Get zodiac symbols
                    western = get_western_zodiac(month, day)
                    zodiac_str = western['symbol']
                    birthday_data = self.bot.birthday_manager.birthdays.get(user_id)
                    if birthday_data and birthday_data.get('year'):
                        chinese = get_chinese_zodiac(birthday_data['year'])
                        zodiac_str += chinese['emoji']
                    if days_until == 0:
                        text += f"• <@{user_id}> - **Today!** {formatted} {zodiac_str} 🎉\n"
                    elif days_until == 1:
                        text += f"• <@{user_id}> - Tomorrow ({formatted}) {zodiac_str}\n"
                    else:
                        text += f"• <@{user_id}> - {formatted} {zodiac_str} ({days_until} days)\n"
                text += "\n💡 Use `!birthday list all` to see all birthdays"
            else:
                text = "No upcoming birthdays in the next 7 days! 🌱\n"
                text += "💡 Use `!birthday list all` to see all birthdays"

        await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))
