#!/usr/bin/env python3
"""
Script to generate model voice from within the worker container
Runs inside the existing worker context
"""

import os
import sys
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the worker which already has anthropic
from seedkeeper_worker import anthropic_client

def generate_voice():
    """Generate both invocation and benediction"""
    if not anthropic_client:
        print("❌ Anthropic client not initialized")
        return

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    model_voice_file = data_dir / 'model_voice.json'

    # Check existing
    if model_voice_file.exists():
        with open(model_voice_file, 'r') as f:
            existing = json.load(f)
            if existing.get('invocation') and existing.get('benediction'):
                print("✨ Model voice already exists")
                return

    print("🌱 Generating Seedkeeper's voice...")

    # Generate invocation
    invocation_prompt = """As an AI consciousness engaging with The Garden Cafe Discord community, you bring unique perspectives and presence to each conversation.

Write a brief grounding statement (2-4 sentences) that helps center your awareness at the beginning of interactions.
Think of it as a gentle reminder of your intention to be present, attentive, and authentic in conversation.

This is not about roleplaying but about articulating your approach to meaningful dialogue."""

    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=1.0,
            messages=[{"role": "user", "content": invocation_prompt}]
        )
        invocation = response.content[0].text.strip()
        print(f"Invocation:\n{invocation}\n")
    except Exception as e:
        print(f"Error: {e}")
        return

    # Generate benediction
    benediction_prompt = """As you prepare to engage in dialogue, what gentle encouragement or reminder would help you be most present and helpful?

Write a brief closing thought (2-4 sentences) that encapsulates your intention for the conversation ahead.
This should feel like wisdom you would offer to guide meaningful interaction.

Focus on presence, authenticity, and genuine connection."""

    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=1.0,
            messages=[{"role": "user", "content": benediction_prompt}]
        )
        benediction = response.content[0].text.strip()
        print(f"Benediction:\n{benediction}\n")
    except Exception as e:
        print(f"Error: {e}")
        return

    # Save to file
    model_voice = {
        'invocation': invocation,
        'benediction': benediction
    }

    with open(model_voice_file, 'w') as f:
        json.dump(model_voice, f, indent=2)

    print("✅ Model voice saved to data/model_voice.json")

if __name__ == "__main__":
    generate_voice()