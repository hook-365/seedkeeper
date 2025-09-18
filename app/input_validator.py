#!/usr/bin/env python3
"""
Input validation and sanitization for Seedkeeper
Prevents injection attacks and ensures data integrity
"""

import re
import html
from typing import Optional, Union, List, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """Validates and sanitizes user input to prevent security issues"""
    
    # Patterns for validation
    DISCORD_ID_PATTERN = re.compile(r'^\d{17,19}$')
    DISCORD_MENTION_PATTERN = re.compile(r'<@!?(\d{17,19})>')
    DATE_PATTERN = re.compile(r'^(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])$')
    MESSAGE_LINK_PATTERN = re.compile(
        r'https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d{17,19})/(\d{17,19})/(\d{17,19})'
    )
    
    # Maximum lengths for various inputs
    MAX_COMMAND_LENGTH = 100
    MAX_MESSAGE_LENGTH = 2000
    MAX_FOCUS_LENGTH = 200
    MAX_USERNAME_LENGTH = 32
    
    # Dangerous characters that could be used for injection
    DANGEROUS_CHARS = re.compile(r'[;&|`$(){}\\]')
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 2000, 
                       allow_mentions: bool = True,
                       allow_urls: bool = True) -> str:
        """
        Sanitize a string for safe use
        
        Args:
            text: The text to sanitize
            max_length: Maximum allowed length
            allow_mentions: Whether to allow Discord mentions
            allow_urls: Whether to allow URLs
            
        Returns:
            Sanitized string
        """
        if not text:
            return ""
        
        # Truncate to max length
        text = text[:max_length]
        
        # HTML escape to prevent XSS
        text = html.escape(text)
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text 
                      if char == '\n' or char == '\t' or not ord(char) < 32)
        
        # Remove dangerous shell characters
        text = InputValidator.DANGEROUS_CHARS.sub('', text)
        
        # Handle mentions
        if not allow_mentions:
            text = text.replace('@', '\\@')
        
        # Handle URLs
        if not allow_urls:
            text = re.sub(r'https?://[^\s]+', '[URL REMOVED]', text)
        
        return text.strip()
    
    @staticmethod
    def validate_discord_id(user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a Discord user ID
        
        Returns:
            (is_valid, cleaned_id)
        """
        if not user_id:
            return False, None
        
        # Check if it's a mention
        mention_match = InputValidator.DISCORD_MENTION_PATTERN.match(user_id)
        if mention_match:
            user_id = mention_match.group(1)
        
        # Validate ID format
        if InputValidator.DISCORD_ID_PATTERN.match(user_id):
            return True, user_id
        
        return False, None
    
    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Validate and parse a date in MM-DD format
        
        Returns:
            (is_valid, month, day)
        """
        if not date_str:
            return False, None, None
        
        # Remove any dangerous characters first
        date_str = InputValidator.sanitize_string(date_str, max_length=10, 
                                                 allow_mentions=False, 
                                                 allow_urls=False)
        
        match = InputValidator.DATE_PATTERN.match(date_str)
        if not match:
            return False, None, None
        
        month = int(match.group(1))
        day = int(match.group(2))
        
        # Validate the date is real (using a non-leap year)
        try:
            datetime(2023, month, day)
            return True, month, day
        except ValueError:
            return False, None, None
    
    @staticmethod
    def validate_message_link(link: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Validate and parse a Discord message link
        
        Returns:
            (is_valid, guild_id, channel_id, message_id)
        """
        if not link:
            return False, None, None, None
        
        # Sanitize first
        link = InputValidator.sanitize_string(link, max_length=200, 
                                             allow_mentions=False)
        
        match = InputValidator.MESSAGE_LINK_PATTERN.match(link)
        if not match:
            return False, None, None, None
        
        return True, match.group(1), match.group(2), match.group(3)
    
    @staticmethod
    def validate_command(command: str) -> Tuple[bool, str]:
        """
        Validate and sanitize a command input
        
        Returns:
            (is_valid, sanitized_command)
        """
        if not command:
            return False, ""
        
        # Sanitize
        command = InputValidator.sanitize_string(
            command, 
            max_length=InputValidator.MAX_COMMAND_LENGTH,
            allow_mentions=True,
            allow_urls=False
        )
        
        # Remove command prefix if present
        if command.startswith('!'):
            command = command[1:]
        
        # Only allow alphanumeric, spaces, and underscores in command name
        command_parts = command.split(maxsplit=1)
        if command_parts:
            command_name = re.sub(r'[^a-zA-Z0-9_]', '', command_parts[0])
            if len(command_parts) > 1:
                command = f"{command_name} {command_parts[1]}"
            else:
                command = command_name
        
        return bool(command), command
    
    @staticmethod
    def validate_focus_text(focus: str) -> Tuple[bool, str]:
        """
        Validate and sanitize focus text for catchup command
        
        Returns:
            (is_valid, sanitized_focus)
        """
        if not focus:
            return True, ""  # Empty focus is valid
        
        focus = InputValidator.sanitize_string(
            focus,
            max_length=InputValidator.MAX_FOCUS_LENGTH,
            allow_mentions=False,
            allow_urls=False
        )
        
        # Remove any remaining special characters that could affect prompts
        focus = re.sub(r'[<>{}\\]', '', focus)
        
        return bool(focus), focus
    
    @staticmethod
    def sanitize_username(username: str) -> str:
        """Sanitize a Discord username for safe display"""
        if not username:
            return "Unknown User"
        
        username = InputValidator.sanitize_string(
            username,
            max_length=InputValidator.MAX_USERNAME_LENGTH,
            allow_mentions=False,
            allow_urls=False
        )
        
        # Discord usernames can't have certain characters
        username = re.sub(r'[@#:`]', '', username)
        
        return username or "Unknown User"
    
    @staticmethod
    def sanitize_channel_name(channel_name: str) -> str:
        """Sanitize a Discord channel name"""
        if not channel_name:
            return "unknown-channel"
        
        channel_name = InputValidator.sanitize_string(
            channel_name,
            max_length=100,
            allow_mentions=False,
            allow_urls=False
        )
        
        # Discord channel names are lowercase with hyphens
        channel_name = channel_name.lower()
        channel_name = re.sub(r'[^a-z0-9-]', '-', channel_name)
        channel_name = re.sub(r'-+', '-', channel_name)
        
        return channel_name.strip('-') or "unknown-channel"
    
    @staticmethod
    def validate_json_key(key: str) -> Tuple[bool, str]:
        """
        Validate a key for JSON storage
        
        Returns:
            (is_valid, sanitized_key)
        """
        if not key:
            return False, ""
        
        # Only allow alphanumeric, underscores, and hyphens
        key = re.sub(r'[^a-zA-Z0-9_-]', '', key)
        
        # Limit length
        key = key[:100]
        
        return bool(key), key
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape Discord markdown characters"""
        if not text:
            return ""
        
        # Escape Discord markdown
        markdown_chars = ['*', '_', '~', '`', '|', '>', '#']
        for char in markdown_chars:
            text = text.replace(char, f'\\{char}')
        
        return text


class RateLimitValidator:
    """Validates rate limiting for various operations"""
    
    def __init__(self):
        self.command_limits = {
            'catchup': (5, 300),  # 5 uses per 5 minutes
            'birthday': (10, 60),  # 10 uses per minute
            'admin': (20, 60),  # 20 uses per minute
            'perspectives': (10, 60),  # 10 uses per minute
        }
    
    def get_limit(self, command: str) -> Tuple[int, int]:
        """Get rate limit for a command (uses, seconds)"""
        return self.command_limits.get(command, (30, 60))  # Default: 30/minute


# Singleton instances
input_validator = InputValidator()
rate_validator = RateLimitValidator()