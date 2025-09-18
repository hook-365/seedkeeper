#!/usr/bin/env python3
"""
Natural Language Processor for Seedkeeper
Interprets conversational messages as bot commands
"""

import re
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

@dataclass
class CommandIntent:
    """Represents an interpreted command intent"""
    command: str
    args: List[str]
    confidence: float
    original_message: str

class NLPProcessor:
    """Natural language processing for command interpretation"""
    
    def __init__(self):
        # Define patterns for natural language to command mapping
        self.command_patterns = {
            # Help/Commands patterns
            "commands": [
                (r"\b(what can you do|what do you do|help me|help|commands?|your commands?)\b", 0.9),
                (r"\b(show me commands?|list commands?|available commands?)\b", 0.95),
                (r"\b(what are your|tell me your|show your) (commands?|abilities|features)\b", 0.9),
                (r"\bhow (do i use|to use) (you|this bot|seedkeeper)\b", 0.85),
            ],
            
            # Hello/Introduction patterns
            "hello": [
                (r"^(hi|hello|hey|greetings?|howdy|yo)[\s\.\!\?]*$", 0.9),  # Only if it's JUST a greeting
                (r"\b(introduce yourself|who are you|tell me about yourself)\b", 0.9),
                (r"\bwhat('s| is) (your name|seedkeeper)\b", 0.85),
            ],
            
            # Catchup patterns
            "catchup": [
                (r"\b(catch me up|catchup|catch up|what did i miss|what happened)\b", 0.9),
                (r"\b(summarize|summary of|recap)( the)?( conversation| chat| messages?)?", 0.9),
                (r"\b(fill me in|bring me up to speed|update me)( on what happened)?", 0.85),
                (r"\bwhat('s| has) been (happening|going on|discussed)\b", 0.8),
            ],
            
            # Birthday patterns
            "birthday": [
                (r"\bmy birthday (is|is on)", 0.9),
                (r"\bi was born (on|in)", 0.9),
                (r"\b(set|add|record|save)( my)? birthday", 0.9),
                (r"\b(when is|whose|who has a) birthday", 0.85),
                (r"\b(upcoming|next|list) birthdays?\b", 0.9),
                (r"\bbirthday (list|upcoming|today|this week)\b", 0.95),
                (r"\b(tell me about|show me|what) (the )?birthdays?\b", 0.9),  # Catches "tell me about the birthdays"
                (r"\bbirthdays? (you know|stored|saved)\b", 0.9),
            ],
            
            # Garden wisdom patterns
            "seeds": [
                (r"\b(plant|give me|share|need)( a| some)? seeds?\b", 0.85),
                (r"\b(conversation starter|ice breaker|something to talk about)\b", 0.9),
                (r"\bthings? (are|is) quiet\b", 0.8),
            ],
            
            "tend": [
                (r"\btend( the)?( garden| community)?", 0.9),
                (r"\b(care for|nurture)( the)?( garden| community)", 0.9),
                (r"\b(community|garden) (care|wisdom|advice)\b", 0.85),
                (r"\bhow (can i|to) help the community\b", 0.85),
            ],
            
            "seasons": [
                (r"\b(current|this) season\b", 0.8),
                (r"\b(community|garden) (phase|season|cycle)\b", 0.85),
                (r"\bwhat season (are we in|is it)\b", 0.9),
            ],
            
            "garden": [
                (r"\bhow('s| is) the garden", 0.9),
                (r"\bgarden (status|state)", 0.9),
                (r"\b(check on|look at|view) the garden\b", 0.85),
                (r"\bgarden perspective\b", 0.95),
            ],
            
            # Admin patterns (lower confidence for safety)
            "admin": [
                (r"\b(make me|add me as|i want to be) (an )?admin\b", 0.7),
                (r"\b(admin|administrator) (commands?|help|status)\b", 0.8),
                (r"\b(who are|list|show) (the )?admins?\b", 0.85),
            ],
            
            # Status/Health patterns
            "health": [
                (r"\b(status|health|how are you doing)\b", 0.8),
                (r"\b(are you|you) (ok|okay|working|alive|online)\b", 0.85),
                (r"\b(system|bot) (status|health|check)\b", 0.9),
            ],
            
            # Feedback patterns - be more specific to avoid false positives
            "feedback": [
                (r"\b(i want to|how to|can i|i'd like to) (give|leave|submit|provide) feedback\b", 0.95),
                (r"\bsubmit (a |an )?(bug report|issue|suggestion)\b", 0.9),
                (r"\bgive you feedback\b", 0.9),
                (r"\bfeedback for (the |this )?bot\b", 0.9),
            ],
        }
        
        # Question words that increase confidence
        self.question_indicators = [
            "what", "how", "when", "where", "who", "why", "can", "could", 
            "would", "should", "is", "are", "do", "does", "will"
        ]
        
        # Bot name variations
        self.bot_names = ["seedkeeper", "seed keeper", "bot", "you"]
    
    def process_message(self, content: str) -> Optional[CommandIntent]:
        """
        Process a message and return command intent if detected
        
        Args:
            content: The message content to process
            
        Returns:
            CommandIntent if a command is detected, None otherwise
        """
        # Clean and normalize the message
        normalized = content.lower().strip()
        
        # Check if message is directed at the bot or is a question
        is_directed = self._is_directed_at_bot(normalized)
        is_question = self._is_question(normalized)
        
        # Skip if it's clearly not meant for the bot
        if not is_directed and not is_question and not self._is_standalone_command(normalized):
            return None
        
        # Try to match patterns
        best_match = None
        best_confidence = 0.0
        
        for command, patterns in self.command_patterns.items():
            for pattern, base_confidence in patterns:
                if re.search(pattern, normalized):
                    # Adjust confidence based on context
                    confidence = base_confidence
                    
                    # Boost confidence if directed at bot
                    if is_directed:
                        confidence = min(1.0, confidence + 0.1)
                    
                    # Boost confidence if it's a question
                    if is_question:
                        confidence = min(1.0, confidence + 0.05)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = command
        
        # Only return if confidence is high enough
        if best_match and best_confidence >= 0.7:
            # Extract any arguments from the message
            args = self._extract_args(normalized, best_match)
            
            return CommandIntent(
                command=best_match,
                args=args,
                confidence=best_confidence,
                original_message=content
            )
        
        return None
    
    def _is_directed_at_bot(self, message: str) -> bool:
        """Check if message is directed at the bot"""
        for name in self.bot_names:
            if name in message:
                return True
        
        # Check for @mentions (will be handled by Discord mention check)
        return False
    
    def _is_question(self, message: str) -> bool:
        """Check if message is a question"""
        # Check for question mark
        if "?" in message:
            return True
        
        # Check for question words at the start
        words = message.split()
        if words and words[0] in self.question_indicators:
            return True
        
        return False
    
    def _is_standalone_command(self, message: str) -> bool:
        """Check if message is a standalone command word"""
        # Very short messages that match command triggers
        if len(message.split()) <= 5:  # Increased to handle phrases like "catch me up"
            standalone_triggers = [
                "help", "commands", "hello", "hi", "catch", "catchup", 
                "birthday", "birthdays", "status", "health", "summarize",
                "fill me in", "give me", "tend", "garden", "how's"
            ]
            return any(trigger in message for trigger in standalone_triggers)
        return False
    
    def _extract_args(self, message: str, command: str) -> List[str]:
        """Extract arguments from the message for the given command"""
        args = []
        
        if command == "birthday":
            # Extract date patterns (MM-DD or Month Day)
            date_pattern = r'\b(\d{1,2}[-/]\d{1,2})\b'
            date_match = re.search(date_pattern, message)
            if date_match:
                args.append(date_match.group(1))
            else:
                # Try month name pattern
                month_pattern = r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b'
                month_match = re.search(month_pattern, message)
                if month_match:
                    month_map = {
                        "january": "01", "february": "02", "march": "03", "april": "04",
                        "may": "05", "june": "06", "july": "07", "august": "08",
                        "september": "09", "october": "10", "november": "11", "december": "12"
                    }
                    month = month_map.get(month_match.group(1))
                    day = month_match.group(2).zfill(2)
                    args.append(f"{month}-{day}")
        
        elif command == "catchup":
            # Extract message links
            link_pattern = r'https://discord(?:app)?\.com/channels/\d+/\d+/\d+'
            link_match = re.search(link_pattern, message)
            if link_match:
                args.append(link_match.group(0))
            
            # Extract focus keywords
            focus_keywords = ["technical", "social", "summary", "detailed", "quick"]
            for keyword in focus_keywords:
                if keyword in message:
                    args.append(keyword)
                    break
        
        return args
    
    def get_command_response_style(self, command: str) -> str:
        """Get the appropriate response style for a command"""
        casual_commands = ["hello", "seeds", "tend", "seasons", "garden"]
        if command in casual_commands:
            return "casual"
        return "standard"