#!/bin/bash

# Quick test script for Car Dashboard API
# Usage: ./quick_test.sh

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "  Car Dashboard - Quick API Tests"
echo "=========================================="
echo ""

# Check if server is running
if ! curl -s "$BASE_URL/api/state" > /dev/null; then
    echo "❌ Server is not running!"
    echo "Start the server with: python backend.py"
    exit 1
fi

echo "✅ Server is running!"
echo ""

# Test 1: Turn on wipers (fast)
echo "🌧️  Test 1: Turning wipers to FAST mode..."
curl -X POST "$BASE_URL/api/wipers" \
  -H "Content-Type: application/json" \
  -d '{"mode":"fast"}'
echo -e "\n"
sleep 2

# Test 2: Set AC temperature
echo "🌡️  Test 2: Setting AC temperature to 20°C..."
curl -X POST "$BASE_URL/api/ac" \
  -H "Content-Type: application/json" \
  -d '{"temperature":20}'
echo -e "\n"
sleep 2

# Test 3: Change ambient light to red
echo "💡 Test 3: Changing ambient light to RED..."
curl -X POST "$BASE_URL/api/ambient-light" \
  -H "Content-Type: application/json" \
  -d '{"color":"#FF0000","brightness":80}'
echo -e "\n"
sleep 2

# Test 4: Adjust seat height
echo "🪑 Test 4: Setting seat height to 75%..."
curl -X POST "$BASE_URL/api/seat" \
  -H "Content-Type: application/json" \
  -d '{"height":75}'
echo -e "\n"
sleep 2

# Test 5: Set speed
echo "🚗 Test 5: Setting speed to 55 mph..."
curl -X POST "$BASE_URL/api/speed" \
  -H "Content-Type: application/json" \
  -d '{"speed":55}'
echo -e "\n"
sleep 2

# Get final state
echo "📊 Getting current state..."
curl -s "$BASE_URL/api/state" | python3 -m json.tool
echo ""

echo "=========================================="
echo "✅ All quick tests completed!"
echo "=========================================="
echo ""
echo "View the dashboard at: $BASE_URL"
echo "View API docs at: $BASE_URL/docs"
