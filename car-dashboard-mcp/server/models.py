"""
Pydantic models for car dashboard API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional


class WiperControl(BaseModel):
    mode: str = Field(..., description="Wiper mode: off, slow, fast")


class ACControl(BaseModel):
    temperature: int = Field(..., ge=16, le=30, description="Temperature in Celsius (16-30)")


class AmbientLightControl(BaseModel):
    color: str = Field(..., description="Color name: red, blue, green, white, purple, or orange")


class SeatControl(BaseModel):
    height: int = Field(..., ge=0, le=100, description="Seat height (0=lowest, 100=highest)")


class SpeedControl(BaseModel):
    speed: int = Field(..., ge=0, le=150, description="Speed in mph")
