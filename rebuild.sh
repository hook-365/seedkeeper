#!/bin/bash
# Seedkeeper rebuild script - rebuilds and restarts the bot

echo "🔨 Rebuilding Seedkeeper Docker containers..."

# Navigate to the docker directory
cd /storage/docker/seedkeeper

# Pull latest code if needed (optional)
# git pull origin main 2>/dev/null

# Stop the current containers
docker-compose down

# Rebuild the images
echo "🏗️ Building new Docker image..."
docker-compose build --no-cache

# Start the containers again
echo "🚀 Starting updated containers..."
docker-compose up -d

# Show status
echo "✅ Rebuild complete!"
docker-compose ps

echo "📝 Checking logs..."
sleep 5
docker logs seedkeeper-worker --tail 20