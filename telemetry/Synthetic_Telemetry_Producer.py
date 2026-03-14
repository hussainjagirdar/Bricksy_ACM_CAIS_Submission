# Databricks notebook source
# MAGIC %pip install databricks-zerobus-ingest-sdk

# COMMAND ----------

# MAGIC %md
# MAGIC ##Syncronously

# COMMAND ----------

import time
import random
from datetime import datetime, timezone
from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

# Configuration - see "Before you begin" section for how to obtain these values.
server_endpoint = "<workspace-id>.zerobus.<region>.azuredatabricks.net"
workspace_url = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net"
table_name = "<catalog>.<schema>.car_telemetry"
client_id = "<client_id>"
client_secret = "<client_secret>"


# 1. Initialize SDK
sdk = ZerobusSdk(server_endpoint, workspace_url)
table_properties = TableProperties(table_name)
options = StreamConfigurationOptions(record_type=RecordType.JSON)
stream = sdk.create_stream(client_id, client_secret, table_properties, options)


def generate_telemetry():

    now_iso = int(time.time()*1000000)
    return {        
        "timestamp": now_iso, 
        "ac_temp": float(round(random.uniform(18.0, 26.0), 2)),
        "engine_temp": float(round(random.uniform(85.0, 105.0), 2)),
        "tpms_fl": int(random.randint(30, 35)),
        "tpms_fr": int(random.randint(30, 35)),
        "tpms_bl": int(random.randint(30, 35)),
        "tpms_br": int(random.randint(30, 35))
    }

try:
    print("Stream initialized. Sending data...")
    for i in range(100):
        record = generate_telemetry()
        ack = stream.ingest_record(record)
        ack.wait_for_ack()
        print(f"Sent record {i}")

except Exception as e:
    print(f"Error: {e}")
    # If the error persists, print the record to debug what exactly was sent
    print(f"Failed record payload: {record}")
    
finally:
    # Safely close
    try:
        stream.close()
    except Exception:
        pass

# COMMAND ----------

