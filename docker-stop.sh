#!/bin/bash

# Telegram Auto Forwarder - Docker Stop Script

echo "🛑 Stopping Telegram Auto Forwarder..."
echo "======================================"

# Stop containers
docker-compose down

# Check if stopped successfully
if ! docker-compose ps | grep -q "Up"; then
    echo "✅ Telegram Auto Forwarder stopped successfully"
    echo ""
    echo "💡 To start again: ./docker-deploy.sh"
    echo "📋 To view logs when running: ./docker-logs.sh"
else
    echo "❌ Failed to stop some containers"
    echo "📊 Current status:"
    docker-compose ps
fi
