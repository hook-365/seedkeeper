#!/usr/bin/env python3
"""
Birthday Manager for Seedkeeper
Tracks and celebrates community birthdays in The Garden Café
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import asyncio
import re
from persistence import atomic_json_write

class BirthdayManager:
    """Manages birthday tracking and celebrations"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.birthdays_file = self.data_dir / "birthdays.json"
        self.pending_file = self.data_dir / "pending_birthdays.json"
        self.birthdays = self.load_birthdays()
        self.pending_confirmations = self.load_pending()
    
    def load_birthdays(self) -> Dict:
        """Load birthdays from JSON file"""
        if self.birthdays_file.exists():
            try:
                with open(self.birthdays_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def load_pending(self) -> Dict:
        """Load pending birthday confirmations"""
        if self.pending_file.exists():
            try:
                with open(self.pending_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_birthdays(self):
        """Save birthdays to JSON file"""
        atomic_json_write(self.birthdays_file, self.birthdays, indent=2)

    def save_pending(self):
        """Save pending confirmations"""
        atomic_json_write(self.pending_file, self.pending_confirmations, indent=2)
    
    def set_birthday(self, user_id: str, month: int, day: int,
                    added_by: str, method: str = "manual", name: str = None,
                    year: int = None) -> Tuple[bool, str]:
        """
        Set a user's birthday
        Returns (success, message)
        """
        # Validate date
        try:
            # Use a leap year for validation (allows Feb 29)
            datetime(2024, month, day)
        except ValueError:
            return False, "That doesn't seem to be a valid date. Try formats like `03-15`, `March 15`, or `1990-03-15`."
        
        # Check if birthday already exists
        if user_id in self.birthdays:
            existing = self.birthdays[user_id]
            if existing['month'] == month and existing['day'] == day:
                return False, "That birthday is already registered!"
            else:
                # Update existing
                birthday_data = {
                    'month': month,
                    'day': day,
                    'added_by': added_by,
                    'method': method,
                    'updated_at': datetime.now().isoformat(),
                    'confirmed': method != "learned"
                }
                if name:
                    birthday_data['name'] = name
                if year:
                    birthday_data['year'] = year
                # Preserve existing year if not being updated
                elif 'year' in existing:
                    birthday_data['year'] = existing['year']
                self.birthdays[user_id] = birthday_data
                self.save_birthdays()
                return True, "Birthday updated successfully! 🎂"
        
        # Add new birthday
        birthday_data = {
            'month': month,
            'day': day,
            'added_by': added_by,
            'method': method,
            'added_at': datetime.now().isoformat(),
            'confirmed': method != "learned"
        }
        if name:
            birthday_data['name'] = name
        if year:
            birthday_data['year'] = year
        self.birthdays[user_id] = birthday_data
        self.save_birthdays()
        return True, "Birthday registered successfully! 🎂"
    
    def remove_birthday(self, user_id: str) -> Tuple[bool, str]:
        """Remove a user's birthday"""
        if user_id in self.birthdays:
            del self.birthdays[user_id]
            self.save_birthdays()
            return True, "Birthday removed."
        return False, "No birthday found to remove."

    def set_year(self, user_id: str, year: int) -> Tuple[bool, str]:
        """Set/update just the birth year for an existing birthday."""
        if user_id not in self.birthdays:
            return False, "No birthday on file. Use `!birthday mine <date>` first (e.g., `03-15` or `March 15`)."
        if year < 1900 or year > datetime.now().year:
            return False, "Please enter a valid birth year (1900-present)."
        self.birthdays[user_id]['year'] = year
        self.birthdays[user_id]['updated_at'] = datetime.now().isoformat()
        self.save_birthdays()
        return True, "Birth year added! 🎂"

    def get_birthday(self, user_id: str) -> Optional[Dict]:
        """Get a user's birthday info"""
        return self.birthdays.get(user_id)
    
    def get_todays_birthdays(self) -> List[str]:
        """Get list of user IDs with birthdays today"""
        today = datetime.now()
        todays_birthdays = []
        
        for user_id, info in self.birthdays.items():
            if info['month'] == today.month and info['day'] == today.day:
                if info.get('confirmed', True):  # Skip unconfirmed learned birthdays
                    todays_birthdays.append(user_id)
        
        return todays_birthdays
    
    def get_upcoming_birthdays(self, days: int = 7) -> List[Tuple[str, int, int, int]]:
        """
        Get upcoming birthdays in the next N days
        Returns list of (user_id, month, day, days_until)
        """
        today = datetime.now()
        upcoming = []
        
        for user_id, info in self.birthdays.items():
            if not info.get('confirmed', True):
                continue
                
            # Calculate days until birthday
            this_year = datetime(today.year, info['month'], info['day'])
            if this_year < today:
                # Birthday passed this year, check next year
                next_birthday = datetime(today.year + 1, info['month'], info['day'])
            else:
                next_birthday = this_year
            
            days_until = (next_birthday - today).days
            
            if 0 <= days_until <= days:
                upcoming.append((user_id, info['month'], info['day'], days_until))
        
        # Sort by days until
        upcoming.sort(key=lambda x: x[3])
        return upcoming
    
    def get_all_birthdays(self) -> Dict:
        """
        Get all registered birthdays
        Returns dictionary of user_id -> birthday info
        """
        # Return only confirmed birthdays
        return {
            user_id: info 
            for user_id, info in self.birthdays.items() 
            if info.get('confirmed', True)
        }
    
    def add_pending_confirmation(self, user_id: str, month: int, day: int, 
                                message_id: str, channel_id: str, detected_by: str):
        """Add a birthday pending confirmation"""
        self.pending_confirmations[message_id] = {
            'user_id': user_id,
            'month': month,
            'day': day,
            'channel_id': channel_id,
            'detected_by': detected_by,
            'detected_at': datetime.now().isoformat()
        }
        self.save_pending()
    
    def confirm_pending(self, message_id: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Confirm a pending birthday
        Returns (success, user_id, birthday_info)
        """
        if message_id not in self.pending_confirmations:
            return False, None, None
        
        pending = self.pending_confirmations[message_id]
        success, msg = self.set_birthday(
            pending['user_id'],
            pending['month'],
            pending['day'],
            pending['detected_by'],
            method="learned"
        )
        
        # Mark as confirmed
        if success and pending['user_id'] in self.birthdays:
            self.birthdays[pending['user_id']]['confirmed'] = True
            self.save_birthdays()
        
        # Remove from pending
        del self.pending_confirmations[message_id]
        self.save_pending()
        
        return success, pending['user_id'], self.birthdays.get(pending['user_id'])
    
    def parse_birthday_from_message(self, content: str) -> Optional[Tuple[List[str], int, int]]:
        """
        Try to detect birthday wishes in a message
        Returns (mentioned_user_ids, month, day) or None
        """
        content_lower = content.lower()
        
        # Check for birthday indicators
        birthday_indicators = [
            'happy birthday', 'hbd', 'bday', '🎂', '🎉', '🎈', '🎊',
            'birthday wishes', 'many happy returns'
        ]
        
        has_birthday_indicator = any(indicator in content_lower for indicator in birthday_indicators)
        if not has_birthday_indicator:
            return None
        
        # Extract mentioned user IDs
        user_mentions = re.findall(r'<@!?(\d+)>', content)
        if not user_mentions:
            return None
        
        # For learning, we'll use today's date
        today = datetime.now()
        return user_mentions, today.month, today.day
    
    def parse_birthday_advanced(self, content: str, mentioned_users: List[str] = None) -> List[Dict]:
        """
        Advanced birthday parsing that can extract dates from various formats
        Returns list of potential birthday matches with confidence scores
        """
        results = []
        content_lower = content.lower()
        
        # Extract all user mentions from the message
        if mentioned_users is None:
            mentioned_users = re.findall(r'<@!?(\d+)>', content)
        
        # Month names and numbers
        months = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sept': 9, 'sep': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
        
        # Patterns to try (with confidence scores)
        patterns = [
            # MM-DD or MM/DD formats
            (r'(\d{1,2})[-/](\d{1,2})', 0.9, 'numeric'),
            # Month DD formats
            (r'(' + '|'.join(months.keys()) + r')\s+(\d{1,2})(?:st|nd|rd|th)?', 0.95, 'month_day'),
            # DD Month formats
            (r'(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(months.keys()) + ')', 0.95, 'day_month'),
            # "birthday is/on [date]" patterns
            (r'birthday\s+(?:is|on|:)\s*(' + '|'.join(months.keys()) + r')\s+(\d{1,2})', 0.98, 'birthday_month_day'),
            (r'birthday\s+(?:is|on|:)\s*(\d{1,2})[-/](\d{1,2})', 0.98, 'birthday_numeric'),
            # "born on/in [date]" patterns  
            (r'born\s+(?:on|in)\s*(' + '|'.join(months.keys()) + r')\s+(\d{1,2})', 0.95, 'born_month_day'),
            (r'born\s+(?:on|in)\s*(\d{1,2})[-/](\d{1,2})', 0.95, 'born_numeric'),
            # "[user]'s birthday" patterns
            (r"(?:his|her|their|my)\s+birthday\s+(?:is|on)?\s*(' + '|'.join(months.keys()) + r')\s+(\d{1,2})", 0.9, 'possessive_month_day'),
            (r"(?:his|her|their|my)\s+birthday\s+(?:is|on)?\s*(\d{1,2})[-/](\d{1,2})", 0.9, 'possessive_numeric')
        ]
        
        for pattern, confidence, pattern_type in patterns:
            matches = re.finditer(pattern, content_lower)
            for match in matches:
                month = None
                day = None
                
                if pattern_type in ['numeric', 'birthday_numeric', 'born_numeric', 'possessive_numeric']:
                    # MM-DD format
                    month = int(match.group(1))
                    day = int(match.group(2))
                elif pattern_type in ['month_day', 'birthday_month_day', 'born_month_day', 'possessive_month_day']:
                    # Month DD format
                    month = months.get(match.group(1))
                    day = int(match.group(2))
                elif pattern_type == 'day_month':
                    # DD Month format
                    day = int(match.group(1))
                    month = months.get(match.group(2))
                
                # Validate the date
                if month and day:
                    try:
                        # Use 2024 as it's a leap year for validation
                        datetime(2024, month, day)
                        
                        # Find context around the match to help identify whose birthday it is
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end]
                        
                        result = {
                            'month': month,
                            'day': day,
                            'confidence': confidence,
                            'pattern': pattern_type,
                            'matched_text': match.group(0),
                            'context': context,
                            'mentioned_users': mentioned_users
                        }
                        
                        # Check if "my" is in the context (author's birthday)
                        if 'my birthday' in content_lower[max(0, match.start() - 20):match.end() + 20]:
                            result['is_author'] = True
                            result['confidence'] += 0.05
                        
                        results.append(result)
                    except ValueError:
                        # Invalid date, skip
                        pass
        
        # Sort by confidence
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results
    
    def parse_birthday_list(self, content: str) -> List[Dict]:
        """
        Parse a structured birthday list format like:
        January
        -------
        7th - Kristi (krae.7)
        
        Returns list of parsed birthdays with names
        """
        results = []
        lines = content.split('\n')
        current_month = None
        
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        for line in lines:
            line_clean = line.strip()
            line_lower = line_clean.lower()
            
            # Check if this is a month header
            for month_name, month_num in months.items():
                if month_name in line_lower and len(line_clean) < 20:  # Month headers are short
                    current_month = month_num
                    break
            
            # Check if this is a birthday entry (contains a day number)
            if current_month and ('-' in line or '–' in line):  # em-dash or regular dash
                # Try to extract day and name
                # Patterns: "7th - Name" or "7 - Name" or "07 - Name"
                patterns = [
                    r'(\d{1,2})(?:st|nd|rd|th)?\s*[-–]\s*(.+)',  # Day with optional suffix
                ]
                
                for pattern in patterns:
                    match = re.match(pattern, line_clean)
                    if match:
                        day_str = match.group(1)
                        name_part = match.group(2).strip()
                        
                        try:
                            day = int(day_str)
                            # Validate the date
                            datetime(2024, current_month, day)
                            
                            # Extract main name and nickname/username if present
                            name_match = re.match(r'([^(]+)(?:\(([^)]+)\))?', name_part)
                            if name_match:
                                main_name = name_match.group(1).strip()
                                nickname = name_match.group(2).strip() if name_match.group(2) else None
                                
                                results.append({
                                    'month': current_month,
                                    'day': day,
                                    'name': main_name,
                                    'nickname': nickname,
                                    'full_text': line_clean,
                                    'confidence': 0.95  # High confidence for structured format
                                })
                        except (ValueError, TypeError):
                            # Invalid date or parsing error
                            pass
        
        return results
    
    def format_birthday_date(self, month: int, day: int) -> str:
        """Format birthday date nicely"""
        date = datetime(2024, month, day)  # Use 2024 as it's a leap year
        return date.strftime("%B %d")
    
    def get_next_birthday_check_time(self) -> datetime:
        """Calculate when to run the next birthday check (daily at 9 AM local time)"""
        now = datetime.now()
        next_check = now.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # If it's already past 9 AM today, schedule for tomorrow
        if now >= next_check:
            next_check += timedelta(days=1)
        
        return next_check