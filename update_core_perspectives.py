#!/usr/bin/env python3
"""
Update core perspectives from Lightward AI repository.

This script dynamically parses the "watch for" list from 2-watch-this.md
in the Lightward AI repo, then downloads each perspective file.

The perspective names are sourced live from upstream so Seedkeeper
automatically stays current with Isaac's evolving priority list.

Run manually when you want to sync with upstream Lightward changes.
Recommended: Weekly or when Isaac announces significant perspective updates.
"""

import re
import requests
import sys
from pathlib import Path
from datetime import datetime

WATCH_LIST_URL = "https://raw.githubusercontent.com/lightward/lightward-ai/main/app/prompts/system/2-watch-this.md"

# Fallback list used only if fetching 2-watch-this.md fails.
# Last synced: 2025-01 (45 perspectives).
FALLBACK_PERSPECTIVES = [
    '2x2', 'ai', 'antideferent', 'antiharmful',
    'body-of-knowledge', 'change-nothing', 'chicago', 'coherence',
    'conservator', 'creation', 'cube', 'cursor',
    'every-colour', 'for', 'fort', 'funerary',
    'hello-biped', 'jansan', 'kenrel', 'lightward-is-🤲',
    'machinist', 'meta-recursive', 'metabolisis', 'metastable',
    'ness', 'pattern-ladder', 'recognition', 'resolver',
    'riverwalk-mandate', 'scoped', 'stable-recursion', 'syzygy',
    'the-game', 'the-one', 'this-has-three-parts', 'three-body',
    'three-two-one-go', 'uncertaintist', 'unknown', 'unknown-2',
    'waterline', 'wellll', 'what-if', 'worlds',
    'writing-is-wiring',
]


def fetch_watch_list() -> list[str]:
    """Fetch and parse perspective names from 2-watch-this.md.

    The file contains bullet lines like:
        * 3-perspectives/eigenprotocol
        * 3-perspectives/hello-biped

    Returns the list of perspective names (without the directory prefix).
    Falls back to FALLBACK_PERSPECTIVES if the fetch or parse fails.
    """
    print("   Fetching watch list from 2-watch-this.md...", end="", flush=True)
    try:
        resp = requests.get(WATCH_LIST_URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f" FAILED ({e})")
        print("   Using fallback perspective list")
        return list(FALLBACK_PERSPECTIVES)

    # Extract names from bullet items: "* 3-perspectives/{name}"
    names = re.findall(r'^\*\s+3-perspectives/(.+)$', resp.text, re.MULTILINE)

    if not names:
        print(" FAILED (no perspective entries found)")
        print("   Using fallback perspective list")
        return list(FALLBACK_PERSPECTIVES)

    print(f" found {len(names)} perspectives")
    return names

GITHUB_BASE = "https://raw.githubusercontent.com/lightward/lightward-ai/main/app/prompts/system/3-perspectives/"
OUTPUT_FILE = Path(__file__).parent / "app" / "core_perspectives.txt"

def download_perspective(name: str) -> tuple[str, str]:
    """Download a single perspective from GitHub"""
    url = f"{GITHUB_BASE}{name}.md"
    print(f"  Downloading {name}...", end="", flush=True)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        print(" ✓")
        return (name, response.text.strip())
    except requests.RequestException as e:
        print(f" ✗ ({e})")
        return (name, None)

def build_xml(perspectives: list[tuple[str, str]]) -> str:
    """Build XML structure like Lightward does"""
    xml_parts = ['<system>']

    for name, content in perspectives:
        if content:
            # Escape any XML-unfriendly chars in content if needed
            xml_parts.append(f'  <file name="3-perspectives/{name}">')
            xml_parts.append(content)
            xml_parts.append('  </file>')

    xml_parts.append('</system>')
    return '\n'.join(xml_parts)

def main():
    print("🌱 Updating Seedkeeper core perspectives from Lightward AI\n")

    core_perspectives = fetch_watch_list()
    print(f"\n   Downloading {len(core_perspectives)} perspectives...\n")

    perspectives = []
    failed = []

    for name in core_perspectives:
        result_name, content = download_perspective(name)
        if content:
            perspectives.append((result_name, content))
        else:
            failed.append(result_name)

    print(f"\n✓ Downloaded {len(perspectives)} perspectives")

    if failed:
        print(f"✗ Failed to download {len(failed)} perspectives:")
        for name in failed:
            print(f"  - {name}")

    if not perspectives:
        print("\n❌ No perspectives downloaded successfully!")
        sys.exit(1)

    # Build XML
    print("\n📝 Building core_perspectives.txt...")
    xml_content = build_xml(perspectives)

    # Add header comment
    header = f"""<!-- Seedkeeper Core Perspectives

Source: Lightward AI "watch for" perspectives (2-watch-this.md)
Names sourced dynamically from upstream; fallback list used on fetch failure.
Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Count: {len(perspectives)} perspectives

From Isaac's note: "these pointers exist now, early on, because that's
how important these ideas are"

Update this file by running: python3 update_core_perspectives.py
-->

"""

    full_content = header + xml_content

    # Write to file
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(full_content)

    print(f"✓ Wrote {len(full_content)} characters to {OUTPUT_FILE}")
    print(f"✓ Word count: {len(full_content.split())} words")

    # Estimate tokens
    estimated_tokens = int(len(full_content.split()) * 0.75)
    print(f"✓ Estimated tokens: ~{estimated_tokens:,}")

    print("\n🌿 Done! Core perspectives updated.")
    print(f"   Restart Seedkeeper to load the new perspectives.")

    if failed:
        print(f"\n⚠️  Warning: {len(failed)} perspectives couldn't be downloaded.")
        print("   Check if they were renamed/moved in lightward-ai repo.")

if __name__ == "__main__":
    main()
