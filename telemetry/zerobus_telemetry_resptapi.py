import requests
import json
import time

# --- Configuration ---
# Update these based on your environment
CLIENT_ID = "<your-service-principal-client-id>"
CLIENT_SECRET = "<your-service-principal-client-secret>"

WORKSPACE_ID = "<your-workspace-id>"
WORKSPACE_URL = "https://adb-<workspace-id>.<suffix>.azuredatabricks.net"
REGION = "<your-region>"

# Table details
CATALOG = "<your-catalog>"
SCHEMA = "<your-schema>"
TABLE = "car_telemetry"
FULL_TABLE_NAME = f"{CATALOG}.{SCHEMA}.{TABLE}"

# Zerobus URI for Azure
ZEROBUS_URI = f"https://{WORKSPACE_ID}.zerobus.{REGION}.azuredatabricks.net"

def get_zerobus_oauth_token() -> str:
    """Fetches OAuth token with specific Zerobus authorization details."""
    token_url = f"{WORKSPACE_URL.rstrip('/')}/oidc/v1/token"
    
    # Define the privileges required for the token
    auth_details = [
        {
            "type": "unity_catalog_privileges",
            "privileges": ["USE CATALOG"],
            "object_type": "CATALOG",
            "object_full_path": CATALOG
        },
        {
            "type": "unity_catalog_privileges",
            "privileges": ["USE SCHEMA"],
            "object_type": "SCHEMA",
            "object_full_path": f"{CATALOG}.{SCHEMA}"
        },
        {
            "type": "unity_catalog_privileges",
            "privileges": ["SELECT", "MODIFY"],
            "object_type": "TABLE",
            "object_full_path": FULL_TABLE_NAME
        }
    ]

    # Parameters for the OAuth request
    data = {
        "grant_type": "client_credentials",
        "scope": "all-apis",
        "resource": f"api://databricks/workspaces/{WORKSPACE_ID}/zerobusDirectWriteApi",
        "authorization_details": json.dumps(auth_details)
    }

    print("Fetching scoped OAuth token...")
    print(f"Token URL: {token_url}")
    response = requests.post(
        token_url,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data=data
    )

    print(f"Token Response Status: {response.status_code}")
    
    if response.status_code == 200:
        try:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise Exception(f"No access_token in response: {token_data}")
            return access_token
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse token response: {response.text}") from e
    else:
        raise Exception(f"Failed to fetch token: {response.status_code} - {response.text}")

def ingest_record(token: str) -> None:
    """Sends a single telemetry record via REST API."""
    endpoint = f"{ZEROBUS_URI}/ingest-record?table_name={FULL_TABLE_NAME}"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "unity-catalog-endpoint": WORKSPACE_URL,
        "x-databricks-zerobus-table-name": FULL_TABLE_NAME
    }

    # Dummy telemetry payload
    payload = {
        "timestamp": int(time.time() * 1000000),
        "ac_temp": 22.5,
        "engine_temp": 98.2,
        "tpms_fl": 1,
        "tpms_fr": 3,
        "tpms_bl": 5,
        "tpms_br": 7
    }

    print(f"Ingesting record to {FULL_TABLE_NAME}...")
    print(f"Endpoint: {endpoint}")
    response = requests.post(endpoint, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body (raw): '{response.text}'")

    if response.status_code in (200, 201, 204):
        # Handle empty response body (common for successful ingestion APIs)
        if response.text.strip():
            try:
                print("Success! Response:", response.json())
            except json.JSONDecodeError:
                print("Success! Response (non-JSON):", response.text)
        else:
            print("Success! (Empty response body)")
    else:
        print(f"Ingestion Failed! Status: {response.status_code}")
        print("Response:", response.text)

if __name__ == "__main__":
    try:
        # Step 1: Get the specific token
        token = get_zerobus_oauth_token()
        
        # Step 2: Ingest the data
        ingest_record(token)
        
    except Exception as e:
        print(f"Error: {e}")