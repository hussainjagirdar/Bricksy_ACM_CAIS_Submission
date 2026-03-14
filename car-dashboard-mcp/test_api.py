"""
Test script to demonstrate the Car Dashboard API
This script sends various HTTP requests to control the car dashboard
"""
import requests
import time
import json

BASE_URL = "http://localhost:8000"

def print_response(title, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print(f"{'='*60}\n")

def test_get_state():
    """Get current car state"""
    response = requests.get(f"{BASE_URL}/api/state")
    print_response("GET CURRENT STATE", response)
    return response.json()

def test_wipers():
    """Test wiper controls"""
    print("\n🔧 TESTING WIPERS")
    print("-" * 60)

    modes = ["off", "slow", "fast", "off"]
    for mode in modes:
        print(f"Setting wipers to: {mode}")
        response = requests.post(
            f"{BASE_URL}/api/wipers",
            json={"mode": mode}
        )
        print_response(f"WIPERS: {mode.upper()}", response)
        time.sleep(1.5)

def test_ac_temperature():
    """Test AC temperature controls"""
    print("\n🌡️  TESTING AC TEMPERATURE")
    print("-" * 60)

    temperatures = [20, 22, 24, 21]
    for temp in temperatures:
        print(f"Setting temperature to: {temp}°C")
        response = requests.post(
            f"{BASE_URL}/api/ac",
            json={"temperature": temp}
        )
        print_response(f"AC TEMPERATURE: {temp}°C", response)
        time.sleep(1)

def test_ambient_light():
    """Test ambient lighting controls"""
    print("\n💡 TESTING AMBIENT LIGHTING")
    print("-" * 60)

    # Test different colors
    colors = ["red", "blue", "green", "white", "purple", "orange"]

    for color in colors:
        print(f"Setting ambient light to: {color}")
        response = requests.post(
            f"{BASE_URL}/api/ambient-light",
            json={"color": color}
        )
        print_response(f"AMBIENT LIGHT: {color.upper()}", response)
        time.sleep(1.5)

def test_seat_height():
    """Test seat height controls"""
    print("\n🪑 TESTING SEAT HEIGHT")
    print("-" * 60)

    heights = [25, 50, 75, 100, 50]
    for height in heights:
        print(f"Setting seat height to: {height}%")
        response = requests.post(
            f"{BASE_URL}/api/seat",
            json={"height": height}
        )
        print_response(f"SEAT HEIGHT: {height}%", response)
        time.sleep(1.5)

def test_speed_simulation():
    """Simulate driving with speed changes"""
    print("\n🚗 TESTING SPEED SIMULATION")
    print("-" * 60)

    speeds = [0, 20, 40, 60, 45, 30, 15, 0]
    for speed in speeds:
        print(f"Speed: {speed} mph")
        response = requests.post(
            f"{BASE_URL}/api/speed",
            json={"speed": speed}
        )
        if speed % 20 == 0:  # Print detailed response every 20 mph
            print_response(f"SPEED: {speed} MPH", response)
        time.sleep(0.8)

def test_combined_scenario():
    """Test a realistic driving scenario"""
    print("\n🎬 TESTING COMBINED SCENARIO: Morning Commute")
    print("-" * 60)

    scenarios = [
        {
            "description": "Start car - Set comfortable temperature",
            "action": lambda: requests.post(f"{BASE_URL}/api/ac", json={"temperature": 22})
        },
        {
            "description": "Adjust seat for driver",
            "action": lambda: requests.post(f"{BASE_URL}/api/seat", json={"height": 65})
        },
        {
            "description": "Set ambient lighting to calm blue",
            "action": lambda: requests.post(f"{BASE_URL}/api/ambient-light",
                                          json={"color": "blue"})
        },
        {
            "description": "Start driving - Speed up to 30 mph",
            "action": lambda: requests.post(f"{BASE_URL}/api/speed", json={"speed": 30})
        },
        {
            "description": "It's raining - Turn on wipers (slow)",
            "action": lambda: requests.post(f"{BASE_URL}/api/wipers", json={"mode": "slow"})
        },
        {
            "description": "Rain intensifies - Wipers to fast",
            "action": lambda: requests.post(f"{BASE_URL}/api/wipers", json={"mode": "fast"})
        },
        {
            "description": "Speed up to highway speed (65 mph)",
            "action": lambda: requests.post(f"{BASE_URL}/api/speed", json={"speed": 65})
        },
        {
            "description": "Too cold - Increase temperature",
            "action": lambda: requests.post(f"{BASE_URL}/api/ac", json={"temperature": 24})
        },
        {
            "description": "Rain stops - Turn off wipers",
            "action": lambda: requests.post(f"{BASE_URL}/api/wipers", json={"mode": "off"})
        },
        {
            "description": "Arriving - Slow down",
            "action": lambda: requests.post(f"{BASE_URL}/api/speed", json={"speed": 20})
        },
        {
            "description": "Parking - Stop",
            "action": lambda: requests.post(f"{BASE_URL}/api/speed", json={"speed": 0})
        }
    ]

    for scenario in scenarios:
        print(f"\n▶ {scenario['description']}")
        response = scenario['action']()
        print(f"  ✓ Success: {response.json()['status']}")
        time.sleep(2)

def test_mcp_endpoint():
    """Test that MCP endpoint is available"""
    print("\n🔌 TESTING MCP ENDPOINT")
    print("-" * 60)

    try:
        # Check if MCP endpoint is accessible
        response = requests.get(f"{BASE_URL}/mcp")
        print(f"MCP Endpoint Status Code: {response.status_code}")
        print("✅ MCP endpoint is accessible")

        # Check API docs includes MCP info
        response = requests.get(f"{BASE_URL}/api/docs-info")
        data = response.json()
        if "mcp_tools" in data:
            print(f"✅ API docs lists {len(data['mcp_tools'])} MCP tools")
            print(f"   Tools: {', '.join(data['mcp_tools'])}")

    except Exception as e:
        print(f"⚠️  MCP endpoint check: {e}")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  CAR DASHBOARD API TEST SUITE")
    print("="*60)
    print("\nMake sure the server is running at http://localhost:8000")
    print("Open http://localhost:8000 in your browser to see live updates!")
    print("\n" + "="*60)

    try:
        # Test connection
        print("\n🔌 Testing connection...")
        test_get_state()

        # Test MCP endpoint
        test_mcp_endpoint()

        # Run individual tests
        test_wipers()
        test_ac_temperature()
        test_ambient_light()
        test_seat_height()
        test_speed_simulation()

        # Run combined scenario
        test_combined_scenario()

        # Final state
        print("\n📊 FINAL STATE")
        test_get_state()

        print("\n✅ All tests completed successfully!")
        print("\nTIP: Try these individual commands:")
        print("  curl -X POST http://localhost:8000/api/wipers -H 'Content-Type: application/json' -d '{\"mode\":\"fast\"}'")
        print("  curl -X POST http://localhost:8000/api/ac -H 'Content-Type: application/json' -d '{\"temperature\":21}'")
        print("  curl -X POST http://localhost:8000/api/seat -H 'Content-Type: application/json' -d '{\"height\":80}'")

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server!")
        print("Please start the server first with: python backend.py")
        print("Or: uvicorn backend:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    main()
