# Telemetry Ingestion

Scripts for streaming vehicle sensor data from the Android app into Databricks Delta Lake via **Zerobus Ingest** — achieving sub-second ingestion latency. This data powers the medallion architecture (Bronze → Silver → Gold) that feeds driver scores, vehicle health metrics, and insurance profiles.

## Data Flow

```
Android App              Telemetry Server           Databricks
(sensor fields)   ──▶   (Flask + Zerobus SDK)  ──▶  Delta Lake
 every 5 seconds          HTTP POST → stream         (Bronze table)
                                                         │
                                                    ┌────▼────┐
                                                    │ Silver   │ (cleaned/validated)
                                                    └────┬────┘
                                                    ┌────▼────┐
                                                    │  Gold    │ (driver scores,
                                                    └─────────┘  vehicle health,
                                                                  insurance profiles)
```

## Files

| File | Description |
|------|-------------|
| `telemetry_server.py` | Flask server that receives HTTP POST telemetry from the Android app and forwards to Databricks via Zerobus SDK. Run this on a machine accessible to the Android app. |
| `zerobus_telemetry_resptapi.py` | Direct Zerobus ingestion via REST API (OAuth-based). Useful for environments where the SDK isn't available. |
| `zerobus_vehicle_telemetry_ingest.py` | Databricks notebook version — runs inside a Databricks cluster using the Zerobus SDK directly. |
| `Synthetic_Telemetry_Producer.py` | Databricks notebook that generates synthetic telemetry data (random engine temp, tyre pressures, AC temp) and streams to Delta Lake. Useful for testing without the Android app. |
| `requirements_telemetry_server.txt` | Python dependencies for `telemetry_server.py` |

## Telemetry Schema

Each record streamed to Delta Lake contains:

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `timestamp` | long | epoch microseconds | Record timestamp |
| `engine_temp` | float | 85.0 - 120.0 °C | Engine temperature |
| `ac_temp` | float | 16.0 - 30.0 °C | AC set temperature |
| `tpms_fl` | int | 25 - 40 PSI | Front-left tyre pressure |
| `tpms_fr` | int | 25 - 40 PSI | Front-right tyre pressure |
| `tpms_bl` | int | 25 - 40 PSI | Back-left tyre pressure |
| `tpms_br` | int | 25 - 40 PSI | Back-right tyre pressure |

## Quick Start

### Option 1: Flask Telemetry Server (for Android app)

```bash
pip install -r requirements_telemetry_server.txt
python telemetry_server.py
# Server runs on port 5001, accepts POST /telemetry
```

The Android app sends JSON payloads to this server every 5 seconds.

### Option 2: Synthetic Data (no Android app needed)

Run `Synthetic_Telemetry_Producer.py` or `zerobus_vehicle_telemetry_ingest.py` in a Databricks notebook to stream synthetic telemetry directly.

## Configuration

Update these values in your chosen script before running:

```python
SERVER_ENDPOINT = "<workspace-id>.zerobus.<region>.azuredatabricks.net"
WORKSPACE_URL = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net"
TABLE_NAME = "<catalog>.<schema>.car_telemetry"
CLIENT_ID = "<your-service-principal-client-id>"
CLIENT_SECRET = "<your-service-principal-client-secret>"
```

### Prerequisites

- Databricks workspace with **Zerobus Ingest** enabled
- A Delta Lake table created in Unity Catalog for telemetry data
- Service principal with appropriate permissions (USE CATALOG, USE SCHEMA, MODIFY on table)

## Dependencies

```
flask>=2.0.0
flask-cors>=3.0.0
databricks-zerobus-ingest-sdk
```
