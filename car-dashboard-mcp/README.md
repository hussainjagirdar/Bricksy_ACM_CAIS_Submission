# Car Dashboard MCP Server

FastMCP server exposing 6 tools for real-time vehicle hardware control, paired with a web-based dashboard that acts as a **simulated digital twin** of the vehicle cockpit. When the Bricksy agent invokes an MCP tool via voice command, the dashboard reflects the change within 200-300ms via Server-Sent Events (SSE).

## MCP Tools (6 total)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `control_wipers` | `mode`: off / slow / fast | Set wiper speed |
| `control_ac` | `temperature`: 16-30 (°C) | Set AC temperature |
| `control_ambient_light` | `color`: red / blue / green / white / purple / orange | Set ambient lighting |
| `control_seat` | `height`: 0-100 (%) | Adjust seat height |
| `control_speed` | `speed`: 0-150 (mph) | Set vehicle speed |
| `get_car_state` | (none) | Get current state of all controls |

## Architecture

```
┌──────────────┐     MCP Protocol      ┌──────────────────┐
│ Bricksy Agent│────────────────────▶  │  FastMCP Server   │
│ (LangGraph)  │                       │  /mcp endpoint    │
└──────────────┘                       └────────┬─────────┘
                                                │
                                      ┌─────────▼─────────┐
                                      │ CarStateManager    │
                                      │   (Singleton)      │
                                      └─────────┬─────────┘
                                                │ SSE broadcast
                                    ┌───────────▼───────────┐
                                    │  Web Dashboard (HTML)  │
                                    │  /dashboard endpoint   │
                                    └───────────────────────┘
```

**Key design**: MCP tools execute synchronously within the agent's tool call, updating the `CarStateManager` singleton, which asynchronously broadcasts state via SSE to all connected dashboard clients. A cross-context event loop bridge handles the sync-to-async notification.

## Project Structure

```
car-dashboard-mcp/
├── backend.py              # App factory: FastAPI + FastMCP combined app
├── server/
│   ├── __init__.py
│   ├── main.py             # Entry point for `uv run`
│   ├── mcp_tools.py        # 6 MCP tool definitions
│   ├── api.py              # REST API endpoints + SSE stream
│   ├── models.py           # Pydantic request models
│   └── state.py            # CarStateManager singleton + SSE broadcast
├── static/
│   ├── index.html          # Dashboard UI (3-panel: climate, speed/fuel, comfort)
│   ├── styles.css          # Glass-morphism dark theme
│   └── script.js           # SSE client + interactive controls
├── pyproject.toml          # Dependencies + entry point
├── app.yaml                # Databricks Apps deployment config
├── test_api.py             # REST API test suite
├── test_mcp.py             # MCP tool test suite
└── quick_test.sh           # Curl-based quick test
```

## Quick Start

```bash
# Install dependencies
python -m venv venv && source venv/bin/activate
pip install -e .

# Run server
python backend.py

# Or via uv (as Databricks does)
uv run car-dashboard-mcp
```

**Endpoints:**
- Dashboard UI: `http://localhost:8000/dashboard`
- MCP endpoint: `http://localhost:8000/mcp`
- REST API: `http://localhost:8000/api/state`
- SSE stream: `http://localhost:8000/api/events`

## Testing

```bash
# REST API tests
python test_api.py

# MCP tool tests
python test_mcp.py

# Quick curl test
bash quick_test.sh
```

## Databricks Deployment

```bash
databricks apps create car-dashboard --app-yaml app.yaml
```

The `app.yaml` runs `uv run car-dashboard-mcp` which invokes `server.main:main`.

## Tech Stack

- **MCP**: FastMCP 3.0+
- **API**: FastAPI + uvicorn
- **Real-time**: Server-Sent Events (SSE)
- **Frontend**: Vanilla HTML/CSS/JS with glass-morphism design
- **State**: Singleton pattern with async SSE broadcast
