"""
MCP (Model Context Protocol) tools for car dashboard
Exposes car controls as MCP tools for LLM agents
"""
from fastmcp import FastMCP
from typing import Dict, Any

from .state import car_state_manager, COLOR_MAP

# Create MCP server instance
mcp = FastMCP("Car Dashboard")


@mcp.tool()
def control_wipers(mode: str) -> str:
    """
    Control windshield wipers

    Args:
        mode: Wiper mode - must be one of: "off", "slow", "fast"

    Returns:
        Status message
    """
    if mode not in ["off", "slow", "fast"]:
        return f"Error: Invalid wiper mode '{mode}'. Use: off, slow, fast"

    car_state_manager.update_state("wipers", mode)
    return f"Success: Wipers set to {mode}"


@mcp.tool()
def control_ac(temperature: int) -> str:
    """
    Control AC temperature

    Args:
        temperature: Temperature in Celsius (16-30)

    Returns:
        Status message
    """
    if not 16 <= temperature <= 30:
        return f"Error: Invalid temperature {temperature}°C. Must be between 16-30°C"

    car_state_manager.update_state("ac_temperature", temperature)
    return f"Success: AC temperature set to {temperature}°C"


@mcp.tool()
def control_ambient_light(color: str) -> str:
    """
    Control ambient lighting color using natural language

    Args:
        color: Color name - must be one of: red, blue, green, white, purple, or orange

    Returns:
        Status message
    """
    color_lower = color.lower()

    if color_lower not in COLOR_MAP:
        available_colors = ", ".join(COLOR_MAP.keys())
        return f"Error: Invalid color '{color}'. Available colors: {available_colors}"

    car_state_manager.update_state("ambient_light_color", color_lower)
    return f"Success: Ambient light color set to {color_lower}"


@mcp.tool()
def control_seat(height: int) -> str:
    """
    Control driver seat height

    Args:
        height: Seat height 0-100 (0=lowest, 100=highest)

    Returns:
        Status message
    """
    if not 0 <= height <= 100:
        return f"Error: Invalid seat height {height}. Must be between 0-100"

    car_state_manager.update_state("seat_height", height)
    return f"Success: Seat height set to {height}% (0=lowest, 100=highest)"


@mcp.tool()
def control_speed(speed: int) -> str:
    """
    Update vehicle speed (demonstration/simulation purposes)

    Args:
        speed: Speed in mph (0-150)

    Returns:
        Status message
    """
    if not 0 <= speed <= 150:
        return f"Error: Invalid speed {speed} mph. Must be between 0-150"

    car_state_manager.update_state("speed", speed)
    return f"Success: Speed set to {speed} mph"


@mcp.tool()
def get_car_state() -> str:
    """
    Get complete current state of all car controls

    Returns:
        Human-readable string containing all car state values
    """
    state = car_state_manager.get_state()
    return (
        f"Car State:\n"
        f"- Wipers: {state['wipers']}\n"
        f"- AC Temperature: {state['ac_temperature']}°C\n"
        f"- Ambient Light: {state['ambient_light_color']}\n"
        f"- Seat Height: {state['seat_height']}%\n"
        f"- Speed: {state['speed']} mph\n"
        f"- Fuel Level: {state['fuel_level']}%\n"
        f"- Last Updated: {state['last_updated']}"
    )
