#!/bin/bash

# Telegram Auto Forwarder - Docker Logs Viewer

echo "📋 Telegram Auto Forwarder - Live Logs"
echo "======================================"

# Check if container is running
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Telegram Auto Forwarder is not running"
    echo "💡 Start it with: ./docker-deploy.sh"
    exit 1
fi

echo "📊 Container Status:"
docker-compose ps
echo ""
echo "📋 Live Logs (Press Ctrl+C to exit):"
echo "======================================"

# Follow logs with colors
docker-compose logs -f --tail=50
