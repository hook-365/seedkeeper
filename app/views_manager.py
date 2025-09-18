#!/usr/bin/env python3
"""
Simplified views manager using single views.txt file from Lightward
"""

import requests
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Tuple

class ViewsManager:
    """Manages perspectives from Lightward's single views.txt file"""

    def __init__(self, views_file: str = "views.txt"):
        self.views_file = Path(views_file)
        self.views_url = "https://lightward.com/views.txt"
        self.perspectives = {}
        self.core_perspectives = []
        self.regular_perspectives = []

    def download_views(self) -> Dict:
        """Download the latest views.txt from Lightward"""
        print(f"📚 Downloading perspectives from {self.views_url}...")

        try:
            response = requests.get(self.views_url, timeout=30)
            response.raise_for_status()

            # Save to file
            self.views_file.write_text(response.text, encoding='utf-8')

            file_size = len(response.text)
            perspective_count = response.text.count('<file name="')

            print(f"✅ Downloaded {perspective_count} perspectives ({file_size:,} bytes)")

            return {
                "success": True,
                "count": perspective_count,
                "size": file_size,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"❌ Error downloading views: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def parse_views(self) -> None:
        """Parse the views.txt file into perspectives"""
        if not self.views_file.exists():
            print("⚠️ No views.txt file found. Run download_views() first.")
            return

        content = self.views_file.read_text(encoding='utf-8')

        # Clear existing perspectives
        self.perspectives = {}
        self.core_perspectives = []
        self.regular_perspectives = []

        # Parse each perspective using regex
        pattern = r'<file name="([^"]+)">(.*?)</file>'
        matches = re.findall(pattern, content, re.DOTALL)

        for name, text in matches:
            # Clean up the text (remove leading/trailing whitespace)
            text = text.strip()

            # Store the perspective
            self.perspectives[name] = text

            # Categorize based on filename
            # Core perspectives are the essential ones from Lightward
            core_names = [
                'aliveness', 'awareness', 'double-consent', 'emergency',
                'lightward', 'presence', 'three-body', 'unknown'
            ]

            # Check if this is a core perspective
            filename = name.split('/')[-1] if '/' in name else name
            if filename in core_names:
                self.core_perspectives.append((name, text))
            else:
                self.regular_perspectives.append((name, text))

        print(f"📖 Parsed {len(self.perspectives)} perspectives")
        print(f"   - Core: {len(self.core_perspectives)}")
        print(f"   - Regular: {len(self.regular_perspectives)}")

    def get_all_perspectives(self) -> List[Tuple[str, str]]:
        """Get all perspectives as (name, content) tuples"""
        if not self.perspectives:
            self.parse_views()

        # Return core first, then regular
        return self.core_perspectives + self.regular_perspectives

    def get_perspective(self, name: str) -> str:
        """Get a specific perspective by name"""
        if not self.perspectives:
            self.parse_views()

        # Try exact match first
        if name in self.perspectives:
            return self.perspectives[name]

        # Try without path prefix
        for key, value in self.perspectives.items():
            if key.endswith(f"/{name}") or key.endswith(name):
                return value

        return None

    def check_for_updates(self) -> bool:
        """Check if remote views.txt is different from local"""
        try:
            # Get remote file size/content
            response = requests.head(self.views_url, timeout=10)
            remote_size = int(response.headers.get('content-length', 0))

            # Compare with local
            if self.views_file.exists():
                local_size = self.views_file.stat().st_size
                return remote_size != local_size

            return True  # No local file, definitely need update

        except Exception:
            return False  # Can't check, assume no update needed

    def get_stats(self) -> Dict:
        """Get statistics about loaded perspectives"""
        if not self.perspectives:
            self.parse_views()

        return {
            "total": len(self.perspectives),
            "core": len(self.core_perspectives),
            "regular": len(self.regular_perspectives),
            "file_exists": self.views_file.exists(),
            "file_size": self.views_file.stat().st_size if self.views_file.exists() else 0
        }


def format_update_message(result: Dict) -> str:
    """Format update result for Discord"""
    if not result["success"]:
        return f"❌ **Update Failed**\n{result.get('error', 'Unknown error')}"

    return (
        f"✨ **Perspectives Updated!**\n\n"
        f"📚 Downloaded {result['count']} perspectives\n"
        f"💾 File size: {result['size']:,} bytes\n"
        f"⏰ Updated at: {result['timestamp']}\n\n"
        f"*All perspectives are now synchronized with Lightward.*"
    )


if __name__ == "__main__":
    # Test the views manager
    manager = ViewsManager()

    # Download latest views
    result = manager.download_views()
    print("\n" + format_update_message(result))

    # Parse and show stats
    manager.parse_views()
    stats = manager.get_stats()
    print(f"\nStats: {stats}")