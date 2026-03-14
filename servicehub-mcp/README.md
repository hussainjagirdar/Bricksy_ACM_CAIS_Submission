# ServiceHub MCP Server

FastMCP server exposing 13 tools for automotive service centre management, booking, driver analytics, and insurance assessment. Includes a **React web portal** that provides the same booking functionality as the MCP tools — enabling a **dual-channel** design where customers book via voice (through Bricksy) and service staff book via the web UI, both operating on the same real-time data.

## MCP Tools (13 total)

### Service Centre Discovery
| Tool | Description |
|------|-------------|
| `list_states` | List all available states |
| `list_cities` | List cities in a state |
| `list_areas` | List areas in a city |
| `search_service_centers` | Find centres by state/city/area |

### Slot Management
| Tool | Description |
|------|-------------|
| `get_slot_availability` | Check available slots for a centre (next N days) |
| `create_booking` | Book a service appointment |
| `cancel_booking` | Cancel an existing booking |
| `list_bookings` | List bookings for a centre on a date |

### Driver Analytics
| Tool | Description |
|------|-------------|
| `list_vehicles` | List all registered vehicles with scores |
| `get_vehicle_summary` | Full vehicle profile with latest scores |
| `get_insurance_assessment` | 90-day aggregated insurance metrics |
| `compare_vehicles_insurance` | Side-by-side comparison (up to 10 vehicles) |
| `health` | Server + database health check |

## Architecture

```
┌──────────────┐     MCP Protocol      ┌──────────────────┐
│ Bricksy Agent│────────────────────▶  │  FastMCP Server   │
│ (LangGraph)  │                       │  /mcp endpoint    │
└──────────────┘                       └────────┬─────────┘
                                                │
┌──────────────┐     REST API           ┌───────▼─────────┐
│  React Web   │────────────────────▶  │  FastAPI Router   │
│   Portal     │◀────────────────────  │  /api/* endpoints  │
└──────────────┘                       └────────┬─────────┘
                                                │
                                      ┌─────────▼─────────┐
                                      │   PostgreSQL       │
                                      │ (Databricks        │
                                      │  LakeBase)         │
                                      └───────────────────┘
```

## Database Schema

- **service_centers** — 44 centres across 9 Indian states
- **service_slots** — Daily slot tracking (total/booked/available)
- **bookings** — Service appointments with vehicle and customer details
- **drivers** — 15 driver profiles (7 EV + 8 ICE) with vehicle specs
- **trip_logs** — 60 days of driving telemetry per driver
- **vehicle_health** — Weekly health snapshots (tyres, battery, brakes, engine)
- **driver_scores** — Weekly risk scores (safety, efficiency, eco, consistency)

## Project Structure

```
servicehub-mcp/
├── server/
│   ├── app.py              # FastAPI + FastMCP combined app
│   ├── main.py             # Entry point for `uv run`
│   ├── mcp_tools.py        # 13 MCP tool definitions
│   ├── database.py         # PostgreSQL connection pool (psycopg3)
│   ├── db_init.py          # Schema creation + seed on startup
│   ├── utils.py            # Auth header capture + WorkspaceClient
│   └── routers/
│       ├── service_centers.py   # GET /api/states, /cities, /areas, /centers
│       ├── slots.py             # GET /api/slots (availability)
│       ├── bookings.py          # GET/POST/DELETE /api/bookings
│       └── driver_profile.py    # GET /api/drivers, trips, scores, health
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Two tabs: Servicing Portal + Driver Profile
│   │   ├── api/index.ts         # API client (fetch wrappers)
│   │   ├── types/index.ts       # TypeScript interfaces
│   │   └── components/
│   │       ├── ServicePortal/   # Location selector, centre cards, booking modal
│   │       ├── DriverProfile/   # Scores, radar chart, insurance, health, trends
│   │       └── Layout/          # Header, tab navigation
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
├── agent.py                # LangGraph agent (alternative deployment)
├── init_db.py              # Standalone database initialisation
├── pyproject.toml          # Dependencies + entry point
├── app.yaml                # Databricks Apps deployment config
└── LOCAL_SETUP.md          # Local development instructions
```

## Quick Start

### 1. Database Setup

```bash
# Install PostgreSQL (macOS)
brew install postgresql@16
brew services start postgresql@16

# Create database
createdb servicehub

# Set environment variables
export PGHOST=localhost
export PGDATABASE=servicehub
export PGUSER=$(whoami)
export PGPASSWORD=""

# Seed database with sample data
python init_db.py
```

### 2. Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn server.app:combined_app --host 0.0.0.0 --port 8000
```

### 3. Frontend (Development)

```bash
cd frontend
npm install
npm run dev     # Dev server with hot reload (proxies /api to :8000)
```

### 4. Frontend (Production Build)

```bash
cd frontend
npm run build   # Outputs to ../static/ — served by FastAPI
```

**Endpoints:**
- Web portal: `http://localhost:8000`
- MCP endpoint: `http://localhost:8000/mcp`
- REST API: `http://localhost:8000/api/states`

## Databricks Deployment

```bash
databricks apps create servicehub --app-yaml app.yaml
```

Update `app.yaml` with your LakeBase connection details (PGHOST, PGUSER, PGENDPOINT).

## Tech Stack

- **MCP**: FastMCP 2.12+
- **API**: FastAPI + uvicorn
- **Database**: PostgreSQL via psycopg3 (connection pool)
- **Frontend**: React 18, TypeScript, Vite, Recharts
- **Auth**: Databricks OAuth (x-forwarded-access-token)
