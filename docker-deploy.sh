#!/bin/bash

# Telegram Auto Forwarder - Docker Deployment Script

echo "🐳 Telegram Auto Forwarder - Docker Deployment"
echo "=============================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "📋 Creating .env file from template..."
    cp .env.docker .env
    echo "❗ Please edit .env file with your Telegram API credentials before continuing!"
    echo "   You can get your API credentials from: https://my.telegram.org"
    echo ""
    echo "📝 Required fields to fill:"
    echo "   - TELEGRAM_API_ID"
    echo "   - TELEGRAM_API_HASH" 
    echo "   - SECRET_KEY"
    echo ""
    echo "After editing .env, run this script again."
    exit 1
fi

# Validate required environment variables
echo "🔍 Validating environment configuration..."
source .env

if [ -z "$TELEGRAM_API_ID" ] || [ "$TELEGRAM_API_ID" = "your_api_id_here" ]; then
    echo "❌ TELEGRAM_API_ID is not set in .env file"
    exit 1
fi

if [ -z "$TELEGRAM_API_HASH" ] || [ "$TELEGRAM_API_HASH" = "your_api_hash_here" ]; then
    echo "❌ TELEGRAM_API_HASH is not set in .env file"
    exit 1
fi

echo "✅ Environment configuration validated"

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || true

# Build and start containers
echo "🏗️  Building Docker image..."
docker-compose build

echo "🚀 Starting Telegram Auto Forwarder..."
docker-compose up -d

# Wait for container to be ready
echo "⏳ Waiting for application to start..."
sleep 10

# Check container status
if docker-compose ps | grep -q "Up"; then
    echo "✅ Telegram Auto Forwarder is running!"
    echo ""
    echo "📊 Container Status:"
    docker-compose ps
    echo ""
    echo "🌐 Dashboard URL: http://localhost:5001"
    echo "🔑 Default login: admin / admin"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs:     docker-compose logs -f"
    echo "   Stop service:  docker-compose down"
    echo "   Restart:       docker-compose restart"
    echo "   Update:        docker-compose pull && docker-compose up -d"
    echo ""
else
    echo "❌ Failed to start Telegram Auto Forwarder"
    echo "📋 Check logs with: docker-compose logs"
    exit 1
fi
