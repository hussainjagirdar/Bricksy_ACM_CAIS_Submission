# Bricksy Agent Backend

LangGraph-based compound AI agent that orchestrates all Bricksy capabilities. Deployed as a **Databricks Model Serving endpoint** via MLflow.

## How It Works

The agent implements a cyclic LangGraph state graph:

```
          ┌──────────┐
          │  START    │
          └────┬─────┘
               ▼
          ┌──────────┐
    ┌────▶│  Agent   │──────┐
    │     │  Node    │      │ (no tool calls → END)
    │     └────┬─────┘      ▼
    │          │ (tool   ┌──────┐
    │          │  calls) │ END  │
    │          ▼         └──────┘
    │     ┌──────────┐
    └─────│  Tool    │
          │  Node    │
          └──────────┘
```

Each request reconstructs the graph with a dynamic system prompt containing the user's live telemetry context.

## Components

### LLM
- **Claude 3.7 Sonnet** via Databricks Model Serving (`databricks-claude-3-7-sonnet`)

### MCP Tools (19 total)
Connected to two remote MCP servers at runtime:
- **Car Dashboard MCP** (6 tools): vehicle hardware control
- **ServiceHub MCP** (13 tools): booking, analytics, insurance

### Local Tools
- **`search_vehicle_manual`**: Hybrid RAG over vehicle manuals using Databricks Vector Search (GTE-Large, 1024-dim). Filters by vehicle model for precise retrieval.
- **`diagnose_vehicle_health`**: Deterministic rule-based health checker:
  - Engine temp > 105°C → CRITICAL
  - Any TPMS < 30 PSI → WARNING
  - Fuel < 10% → WARNING
- **`get_user_memory` / `save_user_memory` / `delete_user_memory`**: Semantic memory via DatabricksStore backed by LakeBase with vector embeddings for cross-session preference recall.

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main LangGraph agent — the production agent deployed to Databricks Model Serving. Contains agent graph, tool definitions, MCP client setup, and MLflow ResponsesAgent wrapper. |
| `bricksy_backend.py` | Databricks notebook for deploying, testing, and iterating on the agent. Includes MCP client setup, agent registration with MLflow, and endpoint creation. |

## Configuration

Update these values in `agent.py` before deploying:

```python
# LLM
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"

# Vector Search (for manual RAG)
VS_ENDPOINT_NAME = "<your-vector-search-endpoint>"
VS_INDEX_NAME = "<catalog>.<schema>.car_manual_vs_index"

# Semantic Memory
LAKEBASE_INSTANCE_NAME = "<your-lakebase-instance-name>"
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
EMBEDDING_DIMS = 1024

# MCP Server URLs (your deployed Databricks Apps)
DASHBOARD_MCP_URL = "https://<your-car-dashboard-app-url>/mcp"
SERVICE_HUB_MCP_URL = "https://<your-servicehub-app-url>/mcp"
```

## Deployment

### 1. Prerequisites

- Databricks workspace with:
  - Model Serving enabled
  - Unity Catalog with a schema for the vector search index
  - LakeBase instance for semantic memory
  - Both MCP servers deployed as Databricks Apps

### 2. Create Vector Search Index

Upload vehicle owner manuals and create a Vector Search index using GTE-Large embeddings (1024 dimensions). The index should have columns for `content`, `vehicle_model`, and embedding vectors.

### 3. Register and Deploy

Use `bricksy_backend.py` in a Databricks notebook:

```python
# Log agent to MLflow
import mlflow
mlflow.langchain.log_model(agent, "bricksy-agent")

# Deploy to Model Serving
# (see bricksy_backend.py for full deployment code)
```

## Dependencies

```
mlflow
langchain-core
langgraph
databricks-langchain[memory]
databricks-sdk
databricks-mcp
databricks-vectorsearch
```

## Custom Inputs

The agent accepts these additional fields per request (injected by the Android app):

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string | Driver identifier for memory/preference lookup |
| `conversation_id` | string | Session ID for multi-turn conversations |
| `vehicle_model` | string | Vehicle model for RAG filtering (e.g., "XUV700") |
| `telemetry` | JSON | Live sensor snapshot (engine temp, TPMS, fuel, AC) |
