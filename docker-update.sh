#!/bin/bash

# Telegram Auto Forwarder - Docker Update Script

echo "🔄 Updating Telegram Auto Forwarder..."
echo "======================================"

# Stop current containers
echo "🛑 Stopping current containers..."
docker-compose down

# Rebuild with no cache for fresh update
echo "🏗️  Rebuilding Docker image..."
docker-compose build --no-cache

# Start updated containers
echo "🚀 Starting updated containers..."
docker-compose up -d

# Wait for startup
echo "⏳ Waiting for application to start..."
sleep 15

# Check status
if docker-compose ps | grep -q "Up"; then
    echo "✅ Update completed successfully!"
    echo ""
    echo "📊 Container Status:"
    docker-compose ps
    echo ""
    echo "🌐 Dashboard: http://localhost:5001"
    echo "📋 View logs: ./docker-logs.sh"
else
    echo "❌ Update failed"
    echo "📋 Check logs: docker-compose logs"
fi
