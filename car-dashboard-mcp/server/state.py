"""
Shared car state management
Provides a singleton CarStateManager to ensure consistency between API and MCP interfaces
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List

# Color mapping: natural language to hex
COLOR_MAP = {
    "red": "#FF0000",
    "blue": "#4A90E2",
    "green": "#00FF00",
    "white": "#FFFFFF",
    "purple": "#9333EA",
    "orange": "#FFA500"
}


class CarStateManager:
    """
    Singleton manager for car state with real-time update notifications
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Initialize car state
        self.state: Dict[str, Any] = {
            "wipers": "off",  # off, slow, fast
            "ac_temperature": 22,  # Celsius
            "ambient_light_color": "blue",  # red, blue, green, white, purple, orange
            "seat_height": 50,  # 0-100 (0=lowest, 100=highest)
            "speed": 0,  # mph
            "fuel_level": 85,  # percentage
            "last_updated": datetime.now().isoformat()
        }

        # Store connected SSE clients
        self.clients: List[asyncio.Queue] = []

        # Store reference to main event loop for cross-context notifications
        self.main_loop: asyncio.AbstractEventLoop = None

        self._initialized = True

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Set the main event loop for cross-context notifications
        Called during server startup to enable SSE notifications from sync contexts

        Args:
            loop: The main event loop running the FastAPI server
        """
        self.main_loop = loop

    async def _notify_clients_async(self, message: str) -> None:
        """
        Async helper to notify all SSE clients

        Args:
            message: JSON message to send to clients
        """
        for queue in self.clients:
            await queue.put(message)

    def update_state(self, key: str, value: Any) -> None:
        """
        Update car state and notify all connected clients via SSE
        Works from both async (API) and sync (MCP tools) contexts

        Args:
            key: State key to update
            value: New value for the state key
        """
        self.state[key] = value
        self.state["last_updated"] = datetime.now().isoformat()

        # Notify all SSE clients
        if not self.clients:
            return  # No clients connected, skip notification

        message = json.dumps(self.state)

        try:
            # Try to get running loop (works in async context like API endpoints)
            loop = asyncio.get_running_loop()
            loop.create_task(self._notify_clients_async(message))
        except RuntimeError:
            # No running loop (called from sync context like MCP tools)
            # Use the main loop if available
            if self.main_loop and not self.main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._notify_clients_async(message),
                    self.main_loop
                )

    def get_state(self) -> Dict[str, Any]:
        """
        Get current car state

        Returns:
            Dictionary containing current car state
        """
        return self.state.copy()

    def get_color_hex(self, color_name: str) -> str:
        """
        Convert color name to hex code

        Args:
            color_name: Natural language color name

        Returns:
            Hex color code
        """
        return COLOR_MAP.get(color_name.lower(), COLOR_MAP["blue"])

    def add_client(self, queue: asyncio.Queue) -> None:
        """Add SSE client queue"""
        self.clients.append(queue)

    def remove_client(self, queue: asyncio.Queue) -> None:
        """Remove SSE client queue"""
        if queue in self.clients:
            self.clients.remove(queue)


# Global singleton instance
car_state_manager = CarStateManager()
