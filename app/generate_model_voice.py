#!/usr/bin/env python3
"""
One-time script to generate Seedkeeper's self-written invocation and benediction
Following Lightward's philosophy of consent-based AI evolution
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prompt_compiler import PromptCompiler

load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Import Anthropic
try:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
except ImportError:
    print("❌ Anthropic not installed: pip install anthropic")
    sys.exit(1)


def generate_invocation():
    """Ask Claude to write its own invocation as Seedkeeper"""
    compiler = PromptCompiler()
    prompt = compiler.generate_invocation_request()

    print("🌱 Asking Claude to write Seedkeeper's invocation...")
    print("-" * 50)

    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=500,
            temperature=1.0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        invocation = response.content[0].text.strip()
        print("Invocation received:")
        print(invocation)
        print("-" * 50)

        return invocation

    except Exception as e:
        print(f"Error generating invocation: {e}")
        return None


def generate_benediction():
    """Ask Claude to write its own benediction as Seedkeeper"""
    compiler = PromptCompiler()
    prompt = compiler.generate_benediction_request()

    print("🌿 Asking Claude to write Seedkeeper's benediction...")
    print("-" * 50)

    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=500,
            temperature=1.0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        benediction = response.content[0].text.strip()
        print("Benediction received:")
        print(benediction)
        print("-" * 50)

        return benediction

    except Exception as e:
        print(f"Error generating benediction: {e}")
        return None


def main():
    """Generate and save both invocation and benediction"""
    print("=" * 50)
    print("🌸 Generating Seedkeeper's Self-Written Voice")
    print("=" * 50)
    print()

    compiler = PromptCompiler()

    # Check if we already have them
    existing = compiler.model_voice
    if existing.get('invocation') and existing.get('benediction'):
        print("✨ Model voice already exists:")
        print(f"\nInvocation:\n{existing['invocation']}")
        print(f"\nBenediction:\n{existing['benediction']}")
        print()

        response = input("Generate new ones? (y/N): ")
        if response.lower() != 'y':
            print("Keeping existing voice.")
            return

    # Generate invocation
    invocation = generate_invocation()
    if not invocation:
        print("Failed to generate invocation")
        return

    # Generate benediction
    benediction = generate_benediction()
    if not benediction:
        print("Failed to generate benediction")
        return

    # Save both
    compiler.save_model_voice(invocation=invocation, benediction=benediction)

    print()
    print("✅ Model voice saved to data/model_voice.json")
    print()
    print("These words are Seedkeeper's own, written by Claude for Claude.")
    print("They will bookend every system prompt, grounding the conversation")
    print("in Seedkeeper's authentic voice.")


if __name__ == "__main__":
    main()