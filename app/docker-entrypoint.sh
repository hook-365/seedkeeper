#!/bin/bash
set -e

echo "🌱 Starting Seedkeeper for The Garden Café..."

# Check if views directory is empty
if [ -z "$(ls -A /app/views)" ]; then
    echo "📚 Views directory is empty. Downloading perspectives from lightward.com..."
    python download_views.py
    echo "✅ Perspectives downloaded successfully!"
else
    echo "📚 Found existing perspectives in /app/views"
    echo "   Total files: $(ls -1 /app/views/*.txt 2>/dev/null | wc -l)"
fi

# Start the bot
echo "🌿 Seedkeeper is tending to The Garden Café..."
exec python seedkeeper.py