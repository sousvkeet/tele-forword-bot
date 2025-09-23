#!/bin/bash

# Telegram Auto Forwarder - Production Start Script

echo "🚀 Starting Telegram Auto Forwarder..."
echo "======================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: ./deploy.sh first"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please run: ./deploy.sh first"
    exit 1
fi

# Check if required dependencies are installed
echo "📦 Checking dependencies..."
python -c "import flask, telethon, asyncio_throttle" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies!"
    echo "Please run: ./deploy.sh first"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Start the application
echo ""
echo "✅ Starting Telegram Auto Forwarder..."
echo "🌐 Dashboard will be available at: http://localhost:5001"
echo "🔑 Default login: admin / admin"
echo ""
echo "Press Ctrl+C to stop"
echo "===================="

# Start with proper logging
python app.py 2>&1 | tee logs/app.log
