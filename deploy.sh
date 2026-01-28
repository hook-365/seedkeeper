#!/bin/bash

# Seedkeeper Deployment Script
set -e

echo "🌱 Building and deploying Seedkeeper..."
echo ""

cd /storage/docker/seedkeeper

docker compose build
docker compose up -d

echo ""
echo "✅ Seedkeeper deployed!"
echo ""
echo "📋 Check status:"
echo "   docker logs seedkeeper -f"
echo ""
echo "📁 Data stored in:"
echo "   Views: /storage/docker/seedkeeper/views/"
echo "   Data:  /storage/docker/seedkeeper/data/"
