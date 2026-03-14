"""
FastAPI route handlers for car dashboard API
All endpoints use the shared CarStateManager for state consistency
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json

from .models import (
    WiperControl,
    ACControl,
    AmbientLightControl,
    SeatControl,
    SpeedControl
)
from .state import car_state_manager, COLOR_MAP

# Create API router
router = APIRouter(prefix="/api")


@router.get("/state")
async def get_state():
    """Get current car state"""
    return car_state_manager.get_state()


@router.get("/events")
async def events():
    """Server-Sent Events endpoint for real-time updates"""
    async def event_generator():
        queue = asyncio.Queue()
        car_state_manager.add_client(queue)
        try:
            # Send initial state
            yield f"data: {json.dumps(car_state_manager.get_state())}\n\n"

            # Send updates as they occur
            while True:
                message = await queue.get()
                yield f"data: {message}\n\n"
        except asyncio.CancelledError:
            car_state_manager.remove_client(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/wipers")
async def control_wipers(control: WiperControl):
    """Control windshield wipers"""
    if control.mode not in ["off", "slow", "fast"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid wiper mode. Use: off, slow, fast"
        )

    car_state_manager.update_state("wipers", control.mode)
    return {"status": "success", "wipers": control.mode}


@router.post("/ac")
async def control_ac(control: ACControl):
    """Control AC temperature"""
    car_state_manager.update_state("ac_temperature", control.temperature)
    return {"status": "success", "ac_temperature": control.temperature}


@router.post("/ambient-light")
async def control_ambient_light(control: AmbientLightControl):
    """Control ambient lighting color"""
    color = control.color.lower()

    if color not in COLOR_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid color '{control.color}'. Use: {', '.join(COLOR_MAP.keys())}"
        )

    car_state_manager.update_state("ambient_light_color", color)

    return {
        "status": "success",
        "ambient_light_color": color,
        "hex_color": COLOR_MAP[color]
    }


@router.post("/seat")
async def control_seat(control: SeatControl):
    """Control driver seat height"""
    car_state_manager.update_state("seat_height", control.height)
    return {"status": "success", "seat_height": control.height}


@router.post("/speed")
async def control_speed(control: SpeedControl):
    """Update vehicle speed (for demo purposes)"""
    car_state_manager.update_state("speed", control.speed)
    return {"status": "success", "speed": control.speed}


@router.get("/docs-info")
async def docs_info():
    """Information about API documentation"""
    return {
        "message": "API Documentation available at /docs",
        "endpoints": {
            "GET /api/state": "Get current car state",
            "GET /api/events": "Real-time updates via Server-Sent Events",
            "POST /api/wipers": "Control wipers (off/slow/fast)",
            "POST /api/ac": "Control AC temperature (16-30°C)",
            "POST /api/ambient-light": "Control ambient lighting",
            "POST /api/seat": "Control seat height (0-100)",
            "POST /api/speed": "Update speed (demo)"
        },
        "mcp_tools": [
            "control_wipers",
            "control_ac",
            "control_ambient_light",
            "control_seat",
            "control_speed",
            "get_car_state"
        ]
    }
