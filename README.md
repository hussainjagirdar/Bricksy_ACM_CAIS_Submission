# Bricksy: A Governed Edge-to-Lakehouse AI Assistant for Next-Generation Smart Vehicles

> **ACM CAIS 2026 Demo Paper** | Hussain Jagirdar & Ravichandan CV, Databricks

Bricksy is an AI-powered vehicle copilot that uses the **Model Context Protocol (MCP)** as a standardised interface to orchestrate real-time car hardware controls, service centre bookings, vehicle diagnostics, and driver behaviour analysis through natural voice interaction.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────────────┐
│   Android App   │────▶│        Bricksy Agent (LangGraph)             │
│  (Voice + STT/  │◀────│   Claude 3.7 Sonnet on Databricks Serving    │
│   TTS + Sensors)│     │                                              │
└────────┬────────┘     │  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
         │              │  │  Hybrid  │ │Determin- │ │   Semantic   │  │
         │ Zerobus      │  │   RAG    │ │istic     │ │   Memory     │  │
         │ (5s interval) │  │(manuals) │ │Diagnosis │ │ (LakeBase)   │  │
         ▼              │  └─────────┘ └──────────┘ └──────────────┘  │
┌─────────────────┐     │                    │                         │
│   Delta Lake    │     └────────────────────┼─────────────────────────┘
│ Bronze→Silver→  │              ┌───────────┴───────────┐
│     Gold        │              ▼                       ▼
│ (Unity Catalog) │     ┌────────────────┐     ┌─────────────────┐
└─────────────────┘     │ Car Dashboard  │     │   ServiceHub    │
                        │   MCP Server   │     │   MCP Server    │
                        │   (6 tools)    │     │   (13 tools)    │
                        │  FastMCP + SSE │     │ FastMCP + SQL   │
                        └────────────────┘     └─────────────────┘
```

**Key features:**
- **19 MCP tools** across two independently deployed servers
- **Voice-first** Android interface with STT/TTS for driver safety
- **Real-time telemetry** ingestion via Databricks Zerobus into Delta Lake (medallion architecture)
- **Compound AI system**: LLM reasoning + deterministic diagnosis + hybrid RAG + semantic memory + MCP actuation
- **SSE-based digital twin** dashboard reflecting vehicle state changes within 200-300ms
- **Dual-channel booking**: same APIs serve both voice agent and web portal

## Repository Structure

```
bricksy/
├── README.md                  ← You are here
├── paper/                     ← ACM CAIS 2026 demo paper (LaTeX)
│   ├── main.tex
│   ├── references.bib
│   └── figures/
├── android-app/               ← Kotlin Android client (voice + sensor emulation)
│   ├── README.md
│   ├── app/src/main/
│   └── build.gradle.kts
├── agent/                     ← Bricksy LangGraph agent backend
│   ├── README.md
│   ├── agent.py               (LangGraph agent with MCP + RAG + memory)
│   └── bricksy_backend.py     (Databricks notebook: deploy + test agent)
├── car-dashboard-mcp/         ← Car Dashboard MCP Server (6 tools + SSE dashboard)
│   ├── README.md
│   ├── server/                (FastMCP tools + FastAPI REST + SSE)
│   └── static/                (Web dashboard UI)
├── servicehub-mcp/            ← ServiceHub MCP Server (13 tools + React portal)
│   ├── README.md
│   ├── server/                (FastMCP tools + FastAPI REST + routers)
│   ├── frontend/              (React + TypeScript + Recharts)
│   └── init_db.py             (PostgreSQL schema + seed data)
├── telemetry/                 ← Zerobus telemetry ingestion scripts
│   ├── README.md
│   ├── telemetry_server.py    (Flask wrapper for Zerobus SDK)
│   └── zerobus_*.py           (Direct Zerobus ingestion examples)
└── VIDEO_PLAN.md              ← Demo video recording plan
```

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| Android App | Android Studio, JDK 11+, Android SDK 29+ |
| Car Dashboard MCP | Python 3.10+, `uv` package manager |
| ServiceHub MCP | Python 3.11+, PostgreSQL 16+, Node.js 18+ (for frontend) |
| Agent Backend | Databricks workspace with Model Serving, Unity Catalog, LakeBase |
| Telemetry | Databricks workspace with Zerobus Ingest enabled |

## Quick Start

### 1. Deploy Car Dashboard MCP Server

```bash
cd car-dashboard-mcp
python -m venv venv && source venv/bin/activate
pip install -e .
python backend.py
# Dashboard: http://localhost:8000/dashboard
# MCP endpoint: http://localhost:8000/mcp
```

### 2. Deploy ServiceHub MCP Server

```bash
cd servicehub-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
python init_db.py          # Seed PostgreSQL with service centres + drivers
cd frontend && npm install && npm run build && cd ..
uvicorn server.app:combined_app --host 0.0.0.0 --port 8001
# Portal: http://localhost:8001
# MCP endpoint: http://localhost:8001/mcp
```

### 3. Deploy Agent Backend

Update configuration in `agent/agent.py`:
- Set `DASHBOARD_MCP_URL` and `SERVICE_HUB_MCP_URL` to your deployed MCP server URLs
- Set `VS_INDEX_NAME` to your Databricks Vector Search index
- Set `LAKEBASE_INSTANCE_NAME` to your LakeBase instance

Deploy as a Databricks Model Serving endpoint (see `agent/README.md`).

### 4. Run Android App

Open `android-app/` in Android Studio. Update the backend endpoint URL in `MainActivity.kt` to point to your deployed agent. Build and run on an emulator or device (API 29+).

### 5. Start Telemetry Streaming

```bash
cd telemetry
pip install -r requirements_telemetry_server.txt
python telemetry_server.py
```

## Databricks Deployment

Both MCP servers are designed to deploy as **Databricks Apps** using `uv`:

```bash
# Car Dashboard
cd car-dashboard-mcp
databricks apps create car-dashboard --app-yaml app.yaml

# ServiceHub
cd servicehub-mcp
databricks apps create servicehub --app-yaml app.yaml
```

The agent deploys as a **Databricks Model Serving endpoint** via MLflow.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Mobile Client | Kotlin, Jetpack Compose, SpeechRecognizer, TextToSpeech |
| Agent | LangGraph, Claude 3.7 Sonnet, MLflow, Databricks Model Serving |
| MCP Servers | FastMCP, FastAPI, uvicorn |
| Car Dashboard | HTML/CSS/JS, Server-Sent Events |
| ServiceHub Portal | React 18, TypeScript, Vite, Recharts |
| Database | PostgreSQL (Databricks LakeBase), Delta Lake |
| Telemetry | Databricks Zerobus, Delta Lake (medallion architecture) |
| Vector Search | Databricks Vector Search, GTE-Large (1024-dim) |
| Memory | Databricks LakeBase + DatabricksStore |

## Paper

The accompanying ACM CAIS 2026 demo paper is in `paper/`. To compile:

```bash
cd paper
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

## Citation

```bibtex
@inproceedings{jagirdar2026bricksy,
  title={Bricksy: A Governed Edge-to-Lakehouse AI Assistant for Next-Generation Smart Vehicles},
  author={Jagirdar, Hussain and CV, Ravichandan},
  booktitle={Proceedings of the ACM Conference on AI Systems (CAIS '26)},
  year={2026}
}
```

## License

This project is released for academic and research purposes as a companion to the ACM CAIS 2026 demo paper.
