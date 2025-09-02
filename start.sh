#!/bin/bash

# WhatsApp Memory Assistant Startup Script
# This script helps you start the application with proper setup

set -e

echo "🚀 WhatsApp Memory Assistant - Startup Script"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo "🔧 Please edit .env file with your API keys before continuing"
    echo ""
    echo "Required API keys:"
    echo "- TWILIO_ACCOUNT_SID"
    echo "- TWILIO_AUTH_TOKEN" 
    echo "- MEM0_API_KEY"
    echo "- OPENAI_API_KEY (optional, for audio transcription)"
    echo ""
    read -p "Press Enter after editing .env file..."
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  Virtual environment not found. Using system Python."
fi

# Check if Python dependencies are installed
echo "🔍 Checking dependencies..."
if ! python -c "import fastapi, uvicorn, sqlalchemy, twilio, mem0ai" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi



echo ""
echo "🎯 Choose startup mode:"
echo "1) Local testing (API only)"
echo "2) Full WhatsApp integration (with ngrok)"
echo "3) Exit"
echo ""

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo "🚀 Starting in local testing mode..."
        echo "📱 API will be available at http://localhost:8000"
        echo "📚 API docs at http://localhost:8000/docs"
        echo "🔍 Health check at http://localhost:8000/health"
        echo ""
        echo "Press Ctrl+C to stop"
        python main.py
        ;;
    2)
        echo "🚀 Starting in full WhatsApp integration mode..."
        echo ""
        echo "📱 Starting main application..."
        echo "🌐 Starting ngrok tunnel..."
        echo ""
        echo "⚠️  You'll need to configure Twilio webhook with the ngrok URL"
        echo ""
        
        # Start ngrok in background
        python setup_ngrok.py &
        NGROK_PID=$!
        
        # Wait a moment for ngrok to start
        sleep 2
        
        # Start main application
        python main.py
        
        # Cleanup
        kill $NGROK_PID 2>/dev/null || true
        ;;
    3)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac
