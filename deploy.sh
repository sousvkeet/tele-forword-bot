#!/bin/bash

# Telegram Auto Forwarder - Production Deployment Script

echo "🚀 Telegram Auto Forwarder - Production Deployment"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Creating .env file from example..."
    cp .env.example .env
    echo "❗ Please edit .env file with your configuration before starting!"
fi

# Make start script executable
chmod +x start.sh

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your Telegram API credentials"
echo "2. Run: ./start.sh"
echo ""
echo "🌐 Dashboard will be available at: http://localhost:5001"
echo "🔑 Default login: admin / admin"
echo ""
