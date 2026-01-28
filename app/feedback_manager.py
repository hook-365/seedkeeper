#!/usr/bin/env python3
"""
Feedback collection and management for Seedkeeper
Allows anonymous feature suggestions and feedback collection
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import random
import asyncio
from persistence import atomic_json_write

class FeedbackManager:
    """Manages feedback collection and anonymous submission"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.feedback_file = os.path.join(data_dir, "feedback.json")
        self.feedback_sessions_file = os.path.join(data_dir, "feedback_sessions.json")
        self.feedback_queue_file = os.path.join(data_dir, "feedback_queue.json")
        self.feedback = []
        self.sessions = {}  # Track active feedback sessions
        self.queue = []  # Queue of feedback to send to owner
        self.ensure_data_directory()
        self.load_data()
        
        # Feature ideas to poll about
        self.feature_prompts = [
            "daily garden wisdom messages at a set time",
            "reminder commands (!remind me in 2 hours to...)",
            "weekly server activity summaries",
            "custom birthday messages you can set for friends",
            "garden journals - personal notes only you can see",
            "seasonal events and celebrations",
            "collaborative story growing in the garden",
            "mindfulness moments and breathing reminders",
            "achievement system for community participation",
            "scheduled catchup summaries (daily/weekly)",
            "anonymous message board for the community",
            "plant growing game with daily care",
            "community polls and decision making",
            "gratitude wall where people share what they're thankful for",
            "dream journal and dream sharing features"
        ]
        
    def ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def load_data(self):
        """Load feedback data from JSON files"""
        # Load feedback history
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r') as f:
                    self.feedback = json.load(f)
            except:
                self.feedback = []
        
        # Load active sessions
        if os.path.exists(self.feedback_sessions_file):
            try:
                with open(self.feedback_sessions_file, 'r') as f:
                    self.sessions = json.load(f)
            except:
                self.sessions = {}
        
        # Load feedback queue
        if os.path.exists(self.feedback_queue_file):
            try:
                with open(self.feedback_queue_file, 'r') as f:
                    self.queue = json.load(f)
            except:
                self.queue = []
    
    def save_data(self):
        """Save all feedback data"""
        try:
            atomic_json_write(self.feedback_file, self.feedback, indent=2, default=str)
            atomic_json_write(self.feedback_sessions_file, self.sessions, indent=2, default=str)
            atomic_json_write(self.feedback_queue_file, self.queue, indent=2, default=str)
        except Exception as e:
            print(f"Error saving feedback data: {e}")
    
    def start_feedback_session(self, user_id: str, channel_id: str, feature: str = None) -> Dict:
        """Start a feedback collection session"""
        # Cancel any existing session for this user
        if user_id in self.sessions:
            del self.sessions[user_id]
        
        # Select a random feature if not specified
        if not feature:
            feature = random.choice(self.feature_prompts)
        
        # Create session
        session = {
            'user_id': user_id,
            'channel_id': channel_id,
            'feature': feature,
            'timestamp': datetime.utcnow().isoformat(),
            'stage': 'initial',
            'responses': {}
        }
        
        self.sessions[user_id] = session
        self.save_data()
        
        return {
            'success': True,
            'feature': feature,
            'session': session
        }
    
    def process_feedback_response(self, user_id: str, response: str) -> Dict:
        """Process a user's feedback response"""
        if user_id not in self.sessions:
            return {
                'success': False,
                'message': "No active feedback session found."
            }
        
        session = self.sessions[user_id]
        stage = session.get('stage', 'initial')
        
        if stage == 'initial':
            # First response - interest level
            session['responses']['interest'] = response
            session['stage'] = 'details'
            self.save_data()
            
            return {
                'success': True,
                'next_prompt': "💭 **Great! Let's dig deeper...**\n\nWhat specific aspects of this feature would be most valuable to you?\n\n*Share any thoughts, ideas, or concerns - or type 'skip' to move on.*",
                'stage': 'details'
            }
        
        elif stage == 'details':
            # Detailed feedback
            if response.lower() != 'skip':
                session['responses']['details'] = response
            session['stage'] = 'anonymous'
            self.save_data()
            
            return {
                'success': True,
                'next_prompt': "🤝 **Final step:**\n\nWould you like to share this feedback anonymously with the bot developer?\n\n• **Yes** - Your feedback helps shape the garden (no identifying info is shared)\n• **No** - Your thoughts stay private between us\n\n*Type 'yes' or 'no'*",
                'stage': 'anonymous'
            }
        
        elif stage == 'anonymous':
            # Permission to share
            share = response.lower() in ['yes', 'y', 'sure', 'ok', 'okay']
            session['responses']['share'] = share
            session['stage'] = 'complete'
            
            if share:
                # Add to queue for bot owner
                feedback_entry = {
                    'feature': session['feature'],
                    'interest': session['responses'].get('interest'),
                    'details': session['responses'].get('details', 'No details provided'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'anonymous': True
                }
                self.queue.append(feedback_entry)
                self.feedback.append(feedback_entry)
            
            # Clear session
            del self.sessions[user_id]
            self.save_data()
            
            if share:
                return {
                    'success': True,
                    'message': "Thank you! Your feedback has been anonymously recorded and will help shape the garden's growth. 🌱",
                    'complete': True
                }
            else:
                return {
                    'success': True,
                    'message': "Thank you for your thoughts! They remain with you alone. 🌿",
                    'complete': True
                }
        
        return {
            'success': False,
            'message': "Unexpected feedback stage"
        }
    
    def get_pending_feedback_for_owner(self) -> List[Dict]:
        """Get all pending feedback for the bot owner (read-only, does not clear)."""
        return self.queue.copy()

    def acknowledge_pending_feedback(self) -> int:
        """Clear the pending feedback queue after successful delivery. Returns count cleared."""
        count = len(self.queue)
        self.queue = []
        self.save_data()
        return count
    
    def get_feedback_summary(self) -> Dict:
        """Get a summary of collected feedback"""
        if not self.feedback:
            return {
                'total': 0,
                'features': {},
                'recent': []
            }
        
        # Count feedback by feature
        feature_counts = {}
        for entry in self.feedback:
            feature = entry.get('feature', 'unknown')
            if feature not in feature_counts:
                feature_counts[feature] = {'count': 0, 'interested': 0}
            feature_counts[feature]['count'] += 1
            if 'yes' in str(entry.get('interest', '')).lower() or 'interest' in str(entry.get('interest', '')).lower():
                feature_counts[feature]['interested'] += 1
        
        # Get recent feedback (last 5)
        recent = self.feedback[-5:] if len(self.feedback) > 5 else self.feedback
        
        return {
            'total': len(self.feedback),
            'features': feature_counts,
            'recent': recent
        }
    
    def cancel_session(self, user_id: str) -> bool:
        """Cancel an active feedback session"""
        if user_id in self.sessions:
            del self.sessions[user_id]
            self.save_data()
            return True
        return False
    
    def suggest_random_feature(self) -> str:
        """Get a random feature suggestion for polling"""
        return random.choice(self.feature_prompts)