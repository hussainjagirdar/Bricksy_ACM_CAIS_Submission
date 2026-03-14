"""
Car Dashboard Application Factory
Creates a hybrid FastAPI + MCP server for car dashboard controls
Following Databricks official MCP server template pattern
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import os

from server.api import router as api_router
from server.mcp_tools import mcp
from server.state import car_state_manager


# Create the MCP HTTP app (MCP protocol routes)
mcp_app = mcp.http_app()

# Create custom FastAPI app (REST API routes)
custom_app = FastAPI(
    title="Car Dashboard API",
    description="REST API for car dashboard controls",
    version="1.0.0"
)

# Add CORS middleware to custom app
custom_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router for REST endpoints
custom_app.include_router(api_router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    custom_app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve main dashboard page
@custom_app.get("/dashboard")
async def dashboard():
    """Serve the main dashboard page"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return {"message": "Car Dashboard API", "docs": "/docs", "dashboard": "/dashboard"}


@asynccontextmanager
async def custom_lifespan(app: FastAPI):
    """
    Lifespan context to capture the main event loop for SSE notifications
    This enables MCP tools (running in sync context) to send SSE updates
    """
    # Capture the main event loop during startup
    loop = asyncio.get_running_loop()
    car_state_manager.set_main_loop(loop)

    yield

    # Cleanup on shutdown (if needed)


# Create combined app (MCP + Custom API) - Following Databricks pattern
combined_app = FastAPI(
    title="Car Dashboard MCP Server",
    description="Combined MCP protocol and REST API server for car controls",
    version="1.0.0",
    lifespan=custom_lifespan
)

# Add CORS to combined app
combined_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include MCP routes (MCP protocol at root)
combined_app.include_router(mcp_app.router)

# Include custom API routes
combined_app.include_router(api_router)

# Mount static files in combined app
if os.path.exists(static_dir):
    combined_app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Add dashboard endpoint to combined app
@combined_app.get("/dashboard")
async def combined_dashboard():
    """Serve the main dashboard page"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return {"message": "Car Dashboard MCP Server", "docs": "/docs", "dashboard": "/dashboard"}


# For backward compatibility
def create_app() -> FastAPI:
    """Return the combined app for compatibility"""
    return combined_app


# For direct execution
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(combined_app, host="0.0.0.0", port=8000)
