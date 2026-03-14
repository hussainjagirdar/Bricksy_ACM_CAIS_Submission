"""
ServiceHub — FastAPI application combining REST API, MCP server, and static frontend.

Architecture:
  - FastMCP server exposed at /mcp (Streamable HTTP, stateless)
  - REST API routers under /api/*
  - React SPA served from /static at the root
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware

from .mcp_tools import load_tools
from .routers import bookings, driver_profile, service_centers, slots
from .utils import header_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp_server = FastMCP(name="servicehub-mcp")
load_tools(mcp_server)
mcp_app = mcp_server.http_app()

# ---------------------------------------------------------------------------
# REST API app
# ---------------------------------------------------------------------------

api_app = FastAPI(title="ServiceHub API", version="1.0.0")
api_app.include_router(service_centers.router)
api_app.include_router(slots.router)
api_app.include_router(bookings.router)
api_app.include_router(driver_profile.router)

# ---------------------------------------------------------------------------
# Lifespan — DB init then MCP lifespan
# ---------------------------------------------------------------------------

_mcp_lifespan = mcp_app.router.lifespan_context


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Auto-init DB schema + seed data (idempotent)
    try:
        from .db_init import run_init
        from .database import get_connection
        with get_connection() as conn:
            run_init(conn)
        logger.info("DB auto-init completed successfully")
    except Exception:
        logger.exception("DB auto-init failed")

    async with _mcp_lifespan(app) as state:
        yield state


# ---------------------------------------------------------------------------
# Combined app — merges MCP routes + API routes
# ---------------------------------------------------------------------------

combined_app = FastAPI(
    title="ServiceHub",
    description="Automotive Service Portal + MCP Server",
    version="1.0.0",
    routes=[*mcp_app.routes, *api_app.routes],
    lifespan=_lifespan,
)

class HeaderCaptureMiddleware(BaseHTTPMiddleware):
    """Capture incoming HTTP headers into header_store for downstream use."""

    async def dispatch(self, request: Request, call_next):
        header_store.set(dict(request.headers))
        return await call_next(request)


combined_app.add_middleware(HeaderCaptureMiddleware)
combined_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the React SPA — must be mounted AFTER all API routes
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    combined_app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
