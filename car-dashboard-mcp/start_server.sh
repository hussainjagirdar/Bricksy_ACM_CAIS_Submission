#!/bin/bash

# Start the Car Dashboard Server
# This script activates the virtual environment and starts the server

echo "🚗 Starting Car Dashboard Server..."
echo "=================================="
echo ""

# Activate virtual environment
source venv/bin/activate

# Start the server
echo "✅ Virtual environment activated"
echo "🚀 Starting FastAPI server on http://localhost:8000"
echo ""
echo "📊 Dashboard: http://localhost:8000"
echo "📚 API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================="
echo ""

python backend.py
