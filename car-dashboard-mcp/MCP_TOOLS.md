# MCP Tools Documentation

## Available Tools

The car dashboard exposes 6 MCP tools for LLM agents to control car features.

## Tool Details

### 1. control_wipers

Control windshield wipers.

**Parameters:**
- `mode` (string, required): Wiper mode - must be "off", "slow", or "fast"

**Example:**
```python
control_wipers("slow")
```

**Response:**
```json
{
  "status": "success",
  "message": "Wipers set to slow",
  "wipers": "slow",
  "current_state": { ... }
}
```

---

### 2. control_ac

Control AC temperature.

**Parameters:**
- `temperature` (integer, required): Temperature in Celsius (16-30)

**Example:**
```python
control_ac(22)
```

**Response:**
```json
{
  "status": "success",
  "message": "AC temperature set to 22°C",
  "ac_temperature": 22,
  "current_state": { ... }
}
```

---

### 3. control_ambient_light

Control ambient lighting color using natural language.

**Parameters:**
- `color` (string, required): Color name - must be one of: red, blue, green, white, purple, or orange

**Example:**
```python
control_ambient_light("blue")
```

**Response:**
```json
{
  "status": "success",
  "message": "Ambient light color set to blue",
  "ambient_light_color": "blue",
  "hex_color": "#4A90E2",
  "current_state": { ... }
}
```

---

### 4. control_seat

Control driver seat height.

**Parameters:**
- `height` (integer, required): Seat height 0-100 (0=lowest, 100=highest)

**Example:**
```python
control_seat(75)
```

**Response:**
```json
{
  "status": "success",
  "message": "Seat height set to 75% (0=lowest, 100=highest)",
  "seat_height": 75,
  "current_state": { ... }
}
```

---

### 5. control_speed

Update vehicle speed (demonstration purposes).

**Parameters:**
- `speed` (integer, required): Speed in mph (0-150)

**Example:**
```python
control_speed(65)
```

**Response:**
```json
{
  "status": "success",
  "message": "Speed set to 65 mph",
  "speed": 65,
  "current_state": { ... }
}
```

---

### 6. get_car_state

Get complete current state of all car controls.

**Parameters:** None

**Example:**
```python
get_car_state()
```

**Response:**
```json
{
  "status": "success",
  "message": "Current car state retrieved",
  "state": {
    "wipers": "off",
    "ac_temperature": 22,
    "ambient_light_color": "blue",
    "seat_height": 50,
    "speed": 0,
    "fuel_level": 85,
    "last_updated": "2026-02-27T10:30:45.123456"
  }
}
```

## Natural Language Examples

When connected to an LLM agent, these tools enable natural language control:

### Example Conversations

**User:** "Turn on the wipers at slow speed"
**Agent:** *calls control_wipers("slow")*
**Response:** "I've set the wipers to slow mode."

---

**User:** "Make it cooler in here"
**Agent:** *calls control_ac(20)*
**Response:** "I've lowered the AC temperature to 20°C."

---

**User:** "Set the ambient lighting to a calming blue color"
**Agent:** *calls control_ambient_light("blue")*
**Response:** "I've set the ambient lighting to blue."

---

**User:** "What's the current state of the car?"
**Agent:** *calls get_car_state()*
**Response:** "The wipers are off, AC is at 22°C, ambient light is blue, seat is at 50% height, and the car is stationary."

## Error Handling

All tools return structured error responses when parameters are invalid:

```json
{
  "status": "error",
  "message": "Invalid wiper mode 'medium'. Use: off, slow, fast"
}
```

Common validation:
- Wipers: Must be "off", "slow", or "fast"
- AC: Must be 16-30°C
- Ambient light color: Must be red, blue, green, white, purple, or orange
- Seat height: Must be 0-100
- Speed: Must be 0-150 mph

## State Consistency

All tools update the shared `CarStateManager`, ensuring:
- ✅ Changes are immediately visible to API clients
- ✅ Real-time SSE updates trigger for web UI
- ✅ Subsequent tool calls see updated state
- ✅ `get_car_state()` returns latest values

## Testing Tools

Test tools locally:

```bash
# Start server
python backend.py

# In another terminal, run MCP tests
python test_mcp.py
```

Test individual tools in Python:

```python
from server.mcp_tools import control_wipers, control_ambient_light, get_car_state

# Test wiper control
result = control_wipers("fast")
print(result["message"])  # "Wipers set to fast"

# Test ambient light
result = control_ambient_light("purple")
print(result["message"])  # "Ambient light color set to purple"

# Check state
state = get_car_state()
print(state["state"]["wipers"])  # "fast"
print(state["state"]["ambient_light_color"])  # "purple"
```

## Databricks Integration

After deploying to Databricks, use the tools via the Databricks SDK:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# List tools
tools = w.apps.list_tools(app_name="car-dashboard-mcp")
for tool in tools.tools:
    print(f"- {tool.name}: {tool.description}")

# Call a tool
result = w.apps.call_tool(
    app_name="car-dashboard-mcp",
    tool_name="control_wipers",
    parameters={"mode": "fast"}
)
print(result.content)
```
