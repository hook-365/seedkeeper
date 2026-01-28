"""Birthday command handler: all birthday subcommands."""

import re
from collections import defaultdict
from typing import Dict, Any


class BirthdayHandler:
    def __init__(self, bot):
        self.bot = bot

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
            help_text = """**Birthday Commands**
`!birthday mine MM-DD` - Set your birthday
`!birthday list` - Show upcoming birthdays (next 7 days)
`!birthday list all` - Show all registered birthdays
`!birthday upcoming [days]` - Show next N days"""

            if self.bot.admin_manager.is_admin(str(author_id)):
                help_text += "\n\n**Admin Commands:**"
                help_text += "\n`!birthday set @user MM-DD` - Set birthday by mention"
                help_text += "\n`!birthday add username MM-DD` - Set birthday by name"
                help_text += "\n`!birthday remove [@user]` - Remove a birthday"
                help_text += "\n`!birthday parse [text]` - Parse birthdays from text"
                help_text += "\n`!birthday match` - Match parsed birthdays to users"
                help_text += "\n`!birthday confirm` - Confirm matched birthdays"
                help_text += "\n`!birthday scan` - Scan channel for birthdays"

            await self.bot.send_message(channel_id, help_text, is_dm=is_dm, author_id=str(author_id))
            return

        subcommand = args[0].lower()

        if subcommand == 'mine' and len(args) >= 2:
            await self._handle_mine(args, author_id, channel_id, is_dm)
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
            await self._handle_scan(author_id, channel_id, is_dm)
        elif subcommand == 'list':
            await self._handle_list(args, author_id, channel_id, is_dm)
        else:
            await self.bot.send_message(channel_id,
                "Use `!birthday` to see available commands.", is_dm=is_dm, author_id=str(author_id))

    async def _handle_mine(self, args, author_id, channel_id, is_dm):
        birthday_str = args[1]
        try:
            month_str, day_str = birthday_str.split('-')
            month, day = int(month_str), int(day_str)
            success, message = self.bot.birthday_manager.set_birthday(
                str(author_id), month, day, str(author_id), method="manual"
            )
            if success:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                await self.bot.send_message(channel_id,
                    f"Birthday set for {formatted}!", is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"{message}", is_dm=is_dm, author_id=str(author_id))
        except ValueError:
            await self.bot.send_message(channel_id,
                "Please use MM-DD format (e.g., 03-15 for March 15th)", is_dm=is_dm, author_id=str(author_id))

    async def _handle_remove(self, args, author_id, channel_id, is_dm):
        if len(args) >= 2:
            user_mention = args[1]
            user_match = re.match(r'<@!?(\d+)>', user_mention)
            target_id = user_match.group(1) if user_match else str(author_id)
            success, message = self.bot.birthday_manager.remove_birthday(target_id)
            msg = "Birthday removed!" if success else f"{message}"
        else:
            success, message = self.bot.birthday_manager.remove_birthday(str(author_id))
            msg = "Your birthday has been removed." if success else f"{message}"
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
            text = f"**Upcoming Birthdays (next {days} days)**\n"
            for user_id, month, day, days_until in birthdays:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                if days_until == 0:
                    text += f"- <@{user_id}> - **Today!** {formatted}\n"
                elif days_until == 1:
                    text += f"- <@{user_id}> - Tomorrow ({formatted})\n"
                else:
                    text += f"- <@{user_id}> - {formatted} ({days_until} days)\n"
        else:
            text = f"No upcoming birthdays in the next {days} days!"
        await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))

    async def _handle_parse(self, args, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can parse birthdays.", is_dm=is_dm, author_id=str(author_id))
            return

        text_to_parse = args[1]
        results = self.bot.birthday_manager.parse_birthday_advanced(text_to_parse)
        if results:
            self.bot._set_temp(f"birthday_parse:{author_id}", results, 300)
            response = f"Parsed {len(results)} birthdays:\n\n"
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
                "Could not parse any birthdays from that text.",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_match(self, author_id, channel_id, is_dm, guild_id):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can match birthdays.", is_dm=is_dm, author_id=str(author_id))
            return

        parsed_data = self.bot._get_temp(f"birthday_parse:{author_id}")
        if not parsed_data:
            await self.bot.send_message(channel_id,
                "No parsed birthday data found. Please run `!birthday parse` first.",
                is_dm=is_dm, author_id=str(author_id))
            return

        birthdays = parsed_data
        members = self.bot._get_guild_members(guild_id) if guild_id else []

        response = "**Birthday Matching Assistant**\n\n"
        response += f"I found {len(birthdays)} birthdays. Attempting to match with server members...\n\n"

        by_month = defaultdict(list)
        matched_count = 0
        unmatched = []

        for b in birthdays:
            matched_user = None
            name_lower = b['name'].lower()
            nick_lower = b['nickname'].lower() if b.get('nickname') else None

            for member in members:
                member_name = member.get('name', '').lower()
                member_nick = member.get('nick', '').lower()
                member_display = member.get('display_name', '').lower()

                if (name_lower in member_name or
                    name_lower in member_nick or
                    name_lower in member_display or
                    (nick_lower and (nick_lower in member_name or
                                   nick_lower in member_nick or
                                   nick_lower in member_display))):
                    matched_user = member
                    matched_count += 1
                    b['matched_user'] = member
                    break

            if not matched_user:
                unmatched.append(b)
            by_month[b['month']].append(b)

        month_display = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        if matched_count > 0:
            response += f"**Matched {matched_count} birthdays:**\n\n"
            for month in sorted(by_month.keys()):
                has_matched = any(b.get('matched_user') for b in by_month[month])
                if has_matched:
                    response += f"**{month_display[month]}:**\n"
                    for b in sorted(by_month[month], key=lambda x: x['day']):
                        if b.get('matched_user'):
                            user = b['matched_user']
                            response += f"- {month:02d}-{b['day']:02d} - {b['name']} -> <@{user['id']}>\n"

        if unmatched:
            response += f"\n**Could not match {len(unmatched)} birthdays:**\n\n"
            unmatched_by_month = defaultdict(list)
            for b in unmatched:
                unmatched_by_month[b['month']].append(b)
            for month in sorted(unmatched_by_month.keys()):
                response += f"**{month_display[month]}:**\n"
                for b in sorted(unmatched_by_month[month], key=lambda x: x['day']):
                    name_str = b['name']
                    if b.get('nickname'):
                        name_str += f" ({b['nickname']})"
                    response += f"- {month:02d}-{b['day']:02d} - {name_str}\n"

        response += "\n**Next steps:**\n"
        if matched_count > 0:
            response += f"1. Use `!birthday confirm` to add all {matched_count} matched birthdays\n"
        if unmatched:
            response += f"2. Manually add unmatched users: `!birthday set @user MM-DD`\n"

        if matched_count > 0:
            matched_data = [b for b in birthdays if b.get('matched_user')]
            self.bot._set_temp(f"birthday_matched:{author_id}", matched_data, 300)

        self.bot._del_temp(f"birthday_parse:{author_id}")
        await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))

    async def _handle_confirm(self, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can confirm birthday additions.",
                is_dm=is_dm, author_id=str(author_id))
            return

        matched_data = self.bot._get_temp(f"birthday_matched:{author_id}")
        if not matched_data:
            await self.bot.send_message(channel_id,
                "No matched birthday data found. Run `!birthday parse` and `!birthday match` first.",
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
                success, message = self.bot.birthday_manager.set_birthday(
                    uid, month, day, str(author_id), method="batch_import"
                )
                if success:
                    added_count += 1
                    response += f"Added <@{uid}> - {month:02d}-{day:02d}\n"
                else:
                    failed_count += 1
                    response += f"Failed for <@{uid}>: {message}\n"

        response += f"\n**Summary:** Added: {added_count}"
        if failed_count > 0:
            response += f", Failed: {failed_count}"
        response += "\n\nBirthday import complete!"

        self.bot._del_temp(f"birthday_matched:{author_id}")
        await self.bot.send_message(channel_id, response, is_dm=is_dm, author_id=str(author_id))

    async def _handle_add(self, args, author_id, channel_id, is_dm, guild_id):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can add birthdays.", is_dm=is_dm, author_id=str(author_id))
            return

        username = args[1].lower()
        if username.startswith('@'):
            username = username[1:]
        birthday_str = args[2]

        target_guild_id = guild_id or '1336444334479769711'
        await self.bot.send_message(channel_id,
            f"Searching for user '{username}'...", is_dm=is_dm, author_id=str(author_id))

        members = self.bot._get_guild_members(target_guild_id)
        if not members:
            await self.bot.send_message(channel_id,
                "Could not fetch server members.", is_dm=is_dm, author_id=str(author_id))
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
                f"Could not find user '{username}'.", is_dm=is_dm, author_id=str(author_id))
            return

        target_user_id = matched_user['id']
        try:
            month_str, day_str = birthday_str.split('-')
            month, day = int(month_str), int(day_str)
            success, message = self.bot.birthday_manager.set_birthday(
                target_user_id, month, day, str(author_id),
                method="admin_add", name=matched_user['display_name']
            )
            if success:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                await self.bot.send_message(channel_id,
                    f"Birthday added for **{matched_user['display_name']}**: {formatted}!",
                    is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"{message}",
                    is_dm=is_dm, author_id=str(author_id))
        except ValueError:
            await self.bot.send_message(channel_id,
                "Please use MM-DD format (e.g., 03-15 for March 15th)",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_set(self, args, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can set others' birthdays.",
                is_dm=is_dm, author_id=str(author_id))
            return

        user_mention = args[1]
        birthday_str = args[2]
        user_match = re.match(r'<@!?(\d+)>', user_mention)
        if not user_match:
            await self.bot.send_message(channel_id,
                "Please mention a user: `!birthday set @user MM-DD`",
                is_dm=is_dm, author_id=str(author_id))
            return

        target_user_id = user_match.group(1)
        try:
            month_str, day_str = birthday_str.split('-')
            month, day = int(month_str), int(day_str)
            success, message = self.bot.birthday_manager.set_birthday(
                target_user_id, month, day, str(author_id), method="admin_set"
            )
            if success:
                formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                await self.bot.send_message(channel_id,
                    f"Birthday set for <@{target_user_id}>: {formatted}!",
                    is_dm=is_dm, author_id=str(author_id))
            else:
                await self.bot.send_message(channel_id, f"{message}",
                    is_dm=is_dm, author_id=str(author_id))
        except ValueError:
            await self.bot.send_message(channel_id,
                "Please use MM-DD format (e.g., 03-15 for March 15th)",
                is_dm=is_dm, author_id=str(author_id))

    async def _handle_scan(self, author_id, channel_id, is_dm):
        if not self.bot.admin_manager.is_admin(str(author_id)):
            await self.bot.send_message(channel_id,
                "Only Garden Keepers can scan for birthdays.",
                is_dm=is_dm, author_id=str(author_id))
            return
        await self.bot.send_message(channel_id,
            "Birthday scanning is done through the `!birthday parse` command.\n"
            "Copy birthday text and use: `!birthday parse [text]`",
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
                    months[month].append((user_id, data['day'], data.get('name', 'Unknown')))

                text = "**All Registered Birthdays**\n"
                text += f"*Total: {len(all_birthdays)} birthdays*\n\n"

                month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                               'July', 'August', 'September', 'October', 'November', 'December']

                for month in sorted(months.keys()):
                    text += f"**{month_names[month]}**\n"
                    for user_id, day, name in sorted(months[month], key=lambda x: x[1]):
                        formatted_date = self.bot.birthday_manager.format_birthday_date(month, day)
                        if name and name != 'Unknown':
                            text += f"- {name} (<@{user_id}>) - {formatted_date}\n"
                        else:
                            text += f"- <@{user_id}> - {formatted_date}\n"

                text += "\nUse `!birthday list` to see only upcoming birthdays"
            else:
                text = "No birthdays registered yet!\nUse `!birthday mine MM-DD` to add yours!"
        else:
            birthdays = self.bot.birthday_manager.get_upcoming_birthdays(7)
            if birthdays:
                text = "**Upcoming Birthdays (next 7 days)**\n"
                for user_id, month, day, days_until in birthdays:
                    formatted = self.bot.birthday_manager.format_birthday_date(month, day)
                    if days_until == 0:
                        text += f"- <@{user_id}> - **Today!** {formatted}\n"
                    elif days_until == 1:
                        text += f"- <@{user_id}> - Tomorrow ({formatted})\n"
                    else:
                        text += f"- <@{user_id}> - {formatted} ({days_until} days)\n"
                text += "\nUse `!birthday list all` to see all birthdays"
            else:
                text = "No upcoming birthdays in the next 7 days!\n"
                text += "Use `!birthday list all` to see all birthdays"

        await self.bot.send_message(channel_id, text, is_dm=is_dm, author_id=str(author_id))
