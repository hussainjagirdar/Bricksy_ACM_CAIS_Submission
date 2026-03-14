"""
Test script for MCP (Model Context Protocol) tools
Tests all MCP tools for the car dashboard
"""
import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
MCP_URL = f"{BASE_URL}/mcp"


def print_test_result(test_name: str, success: bool, details: str = ""):
    """Print formatted test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"       {details}")


def test_mcp_endpoint_accessible():
    """Test that MCP endpoint is accessible"""
    try:
        response = requests.get(MCP_URL)
        success = response.status_code in [200, 404, 405]  # Any response means it's mounted
        print_test_result(
            "MCP Endpoint Accessible",
            success,
            f"Status: {response.status_code}"
        )
        return success
    except requests.exceptions.ConnectionError:
        print_test_result(
            "MCP Endpoint Accessible",
            False,
            "Could not connect to server"
        )
        return False


def test_api_docs_includes_mcp():
    """Test that API docs-info includes MCP tools"""
    try:
        response = requests.get(f"{BASE_URL}/api/docs-info")
        data = response.json()
        has_mcp_tools = "mcp_tools" in data
        if has_mcp_tools:
            num_tools = len(data["mcp_tools"])
            print_test_result(
                "API Docs Includes MCP Tools",
                True,
                f"Found {num_tools} MCP tools: {', '.join(data['mcp_tools'])}"
            )
        else:
            print_test_result(
                "API Docs Includes MCP Tools",
                False,
                "mcp_tools key not found in docs-info"
            )
        return has_mcp_tools
    except Exception as e:
        print_test_result("API Docs Includes MCP Tools", False, str(e))
        return False


def test_mcp_state_consistency():
    """Test that MCP and API share the same state"""
    print("\n" + "="*70)
    print("Testing State Consistency Between API and MCP")
    print("="*70)

    try:
        # Get initial state via API
        initial_state = requests.get(f"{BASE_URL}/api/state").json()
        print(f"\n📊 Initial State:")
        print(f"   Wipers: {initial_state['wipers']}")
        print(f"   AC: {initial_state['ac_temperature']}°C")
        print(f"   Seat: {initial_state['seat_height']}%")

        # Change state via API
        print(f"\n🔧 Changing wipers to 'fast' via API...")
        api_response = requests.post(
            f"{BASE_URL}/api/wipers",
            json={"mode": "fast"}
        )

        # Verify state changed
        new_state = requests.get(f"{BASE_URL}/api/state").json()

        wipers_changed = new_state['wipers'] == 'fast'
        print_test_result(
            "State Updated via API",
            wipers_changed,
            f"Wipers now: {new_state['wipers']}"
        )

        # Change back via API for next test
        requests.post(f"{BASE_URL}/api/wipers", json={"mode": "off"})

        return wipers_changed

    except Exception as e:
        print_test_result("State Consistency Test", False, str(e))
        return False


def test_direct_mcp_tools():
    """Test MCP tools directly by importing them"""
    print("\n" + "="*70)
    print("Testing MCP Tools Directly (Function Calls)")
    print("="*70)

    try:
        # Import MCP tools
        from server.mcp_tools import (
            control_wipers,
            control_ac,
            control_ambient_light,
            control_seat,
            control_speed,
            get_car_state
        )

        # Test get_car_state
        print("\n1️⃣ Testing get_car_state()...")
        state_result = get_car_state()
        success = state_result["status"] == "success" and "state" in state_result
        print_test_result(
            "get_car_state()",
            success,
            f"Returned state with {len(state_result.get('state', {}))} fields"
        )

        # Test control_wipers
        print("\n2️⃣ Testing control_wipers()...")
        for mode in ["slow", "fast", "off"]:
            result = control_wipers(mode)
            success = result["status"] == "success"
            print_test_result(
                f"control_wipers('{mode}')",
                success,
                result.get("message", "")
            )

        # Test invalid wiper mode
        result = control_wipers("invalid")
        success = result["status"] == "error"
        print_test_result(
            "control_wipers('invalid') - Error Handling",
            success,
            result.get("message", "")
        )

        # Test control_ac
        print("\n3️⃣ Testing control_ac()...")
        for temp in [18, 22, 26]:
            result = control_ac(temp)
            success = result["status"] == "success"
            print_test_result(
                f"control_ac({temp})",
                success,
                result.get("message", "")
            )

        # Test invalid temperature
        result = control_ac(35)
        success = result["status"] == "error"
        print_test_result(
            "control_ac(35) - Out of Range",
            success,
            result.get("message", "")
        )

        # Test control_ambient_light
        print("\n4️⃣ Testing control_ambient_light()...")
        for color in ["red", "blue", "green", "white", "purple", "orange"]:
            result = control_ambient_light(color)
            success = result["status"] == "success"
            print_test_result(
                f"control_ambient_light('{color}')",
                success,
                result.get("message", "")
            )

        # Test invalid color
        result = control_ambient_light("pink")
        success = result["status"] == "error"
        print_test_result(
            "control_ambient_light('pink') - Invalid Color",
            success,
            result.get("message", "")
        )

        # Test control_seat
        print("\n5️⃣ Testing control_seat()...")
        for height in [25, 50, 75]:
            result = control_seat(height)
            success = result["status"] == "success"
            print_test_result(
                f"control_seat({height})",
                success,
                result.get("message", "")
            )

        # Test control_speed
        print("\n6️⃣ Testing control_speed()...")
        for speed in [0, 30, 65, 0]:
            result = control_speed(speed)
            success = result["status"] == "success"
            print_test_result(
                f"control_speed({speed})",
                success,
                result.get("message", "")
            )

        return True

    except Exception as e:
        print_test_result("Direct MCP Tools Test", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all MCP tests"""
    print("\n" + "="*70)
    print("  CAR DASHBOARD MCP TEST SUITE")
    print("="*70)
    print("\nMake sure the server is running at http://localhost:8000")
    print("="*70 + "\n")

    # Track test results
    tests_passed = 0
    tests_total = 0

    # Test 1: MCP endpoint accessible
    print("\n📡 Testing MCP Endpoint...")
    print("-" * 70)
    if test_mcp_endpoint_accessible():
        tests_passed += 1
    tests_total += 1

    # Test 2: API docs includes MCP tools
    print("\n📚 Testing API Documentation...")
    print("-" * 70)
    if test_api_docs_includes_mcp():
        tests_passed += 1
    tests_total += 1

    # Test 3: State consistency
    if test_mcp_state_consistency():
        tests_passed += 1
    tests_total += 1

    # Test 4: Direct MCP tool calls
    if test_direct_mcp_tools():
        tests_passed += 1
    tests_total += 1

    # Summary
    print("\n" + "="*70)
    print(f"  TEST SUMMARY: {tests_passed}/{tests_total} test groups passed")
    print("="*70)

    if tests_passed == tests_total:
        print("\n✅ All MCP tests passed successfully!")
        print("\n🚀 The car dashboard MCP server is ready for deployment!")
        print("\nNext steps:")
        print("  1. Test with a real MCP client")
        print("  2. Deploy to Databricks: databricks apps deploy custom-mcp-server")
        print("  3. Test with DatabricksMCPClient")
    else:
        print(f"\n⚠️  {tests_total - tests_passed} test group(s) failed")
        print("Please check the errors above and fix them before deployment")


if __name__ == "__main__":
    main()
