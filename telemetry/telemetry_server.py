"""
Telemetry Server - Flask wrapper for Zerobus SDK
Receives telemetry data from Android app and ingests to Databricks Delta table.
Run with: python telemetry_server.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties
import time
import threading

app = Flask(__name__)
CORS(app)

# Zerobus Configuration
SERVER_ENDPOINT = "<workspace-id>.zerobus.<region>.azuredatabricks.net"
WORKSPACE_URL = "https://adb-<workspace-id>.<workspace-suffix>.azuredatabricks.net"
TABLE_NAME = "<catalog>.<schema>.car_telemetry"
CLIENT_ID = "<your-service-principal-client-id>"
CLIENT_SECRET = "<your-service-principal-client-secret>"

# Global state
sdk = None
stream = None
stream_lock = threading.Lock()
is_stream_active = False


def initialize_stream():
    """Initialize Zerobus SDK and create stream."""
    global sdk, stream, is_stream_active
    try:
        sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)
        table_properties = TableProperties(TABLE_NAME)
        options = StreamConfigurationOptions(record_type=RecordType.JSON)
        stream = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, table_properties, options)
        is_stream_active = True
        print("Zerobus stream initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize stream: {e}")
        return False


def close_stream():
    """Close Zerobus stream."""
    global stream, is_stream_active
    try:
        if stream:
            stream.close()
            stream = None
        is_stream_active = False
        print("Zerobus stream closed")
        return True
    except Exception as e:
        print(f"Error closing stream: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "stream_active": is_stream_active
    })


@app.route('/stream/start', methods=['POST'])
def start_stream():
    """Start the Zerobus stream."""
    global is_stream_active
    with stream_lock:
        if is_stream_active:
            return jsonify({
                "success": True,
                "message": "Stream already active"
            })
        success = initialize_stream()
        if success:
            return jsonify({
                "success": True,
                "message": "Stream started successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to start stream"
            }), 500


@app.route('/stream/stop', methods=['POST'])
def stop_stream():
    """Stop the Zerobus stream."""
    with stream_lock:
        success = close_stream()
        if success:
            return jsonify({
                "success": True,
                "message": "Stream stopped successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to stop stream"
            }), 500


@app.route('/telemetry', methods=['POST'])
def ingest_telemetry():
    """Ingest telemetry data to Zerobus."""
    global stream, is_stream_active
    if not is_stream_active or not stream:
        return jsonify({
            "success": False,
            "message": "Stream not active. Call /stream/start first."
        }), 400
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "No JSON data provided"
            }), 400
        # Add server timestamp if not provided
        if "timestamp" not in data:
            data["timestamp"] = int(time.time() * 1000000)
        # Build the telemetry record
        record = {
            "timestamp": data.get("timestamp"),
            "ac_temp": float(data.get("ac_temperature", 0)),
            "engine_temp": float(data.get("engine_temperature", 0)),
            "tpms_fl": int(data.get("tpms_fl", 0)),
            "tpms_fr": int(data.get("tpms_fr", 0)),
            "tpms_bl": int(data.get("tpms_bl", 0)),
            "tpms_br": int(data.get("tpms_br", 0))
        }
        with stream_lock:
            if stream and is_stream_active:
                ack = stream.ingest_record(record)
                ack.wait_for_ack()
                print(f"Ingested telemetry: {record}")
                return jsonify({
                    "success": True,
                    "message": "Telemetry ingested successfully",
                    "record": record
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Stream closed during ingestion"
                }), 500
    except Exception as e:
        print(f"Error ingesting telemetry: {e}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500


if __name__ == '__main__':
    print("Starting Telemetry Server...")
    print(f"Table: {TABLE_NAME}")
    print("Endpoints:")
    print("  GET  /health        - Health check")
    print("  POST /stream/start  - Start Zerobus stream")
    print("  POST /stream/stop   - Stop Zerobus stream")
    print("  POST /telemetry     - Ingest telemetry data")
    app.run(host='0.0.0.0', port=5000, debug=True)
