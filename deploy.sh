#!/bin/bash

# Seedkeeper Deployment Script for Portainer
# Run this on your Docker host to build the image

set -e

echo "🌱 Building Seedkeeper Docker image..."
echo ""

# Navigate to the seedkeeper directory
cd /storage/docker/seedkeeper

# Build the Docker image
docker build -t seedkeeper:latest .

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Image built: seedkeeper:latest"
echo ""
echo "🚀 Next steps for Portainer deployment:"
echo ""
echo "1. Go to Portainer → Stacks → Add Stack"
echo "2. Name: seedkeeper"
echo "3. Repository: Use 'Upload' and select docker-compose.yml from /storage/docker/seedkeeper/"
echo "   OR"
echo "   Web editor: Copy the contents of docker-compose.yml"
echo ""
echo "4. Add Environment variables in Portainer:"
echo "   DISCORD_BOT_TOKEN=your_bot_token"
echo "   ANTHROPIC_API_KEY=your_claude_api_key"
echo "   BOT_OWNER_ID=your_discord_user_id (optional)"
echo ""
echo "5. Deploy the stack"
echo ""
echo "📁 Data will be stored in:"
echo "   Views: /storage/docker/seedkeeper/views/"
echo "   Data:  /storage/docker/seedkeeper/data/"
echo ""
echo "💡 The bot will auto-download perspectives on first run if views/ is empty"