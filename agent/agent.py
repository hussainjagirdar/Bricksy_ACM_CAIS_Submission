import asyncio
import json
import logging
import os
import contextvars

from typing import Annotated, Any, AsyncGenerator, Generator, Optional, Sequence, TypedDict, Union

import mlflow
import nest_asyncio
from databricks.sdk import WorkspaceClient
from databricks_langchain import (
    ChatDatabricks,
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
    DatabricksStore,
)
from databricks.vector_search.client import VectorSearchClient
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.language_models import LanguageModelLike
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)

nest_asyncio.apply()

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
VS_ENDPOINT_NAME = "product_search_endpoint"
VS_INDEX_NAME = "<catalog>.<schema>.car_manual_vs_index"
LAKEBASE_INSTANCE_NAME = "bricksy-hussain-lakebase"
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
EMBEDDING_DIMS = 1024

# MCP Server URLs
DASHBOARD_MCP_URL = "https://<your-car-dashboard-app-url>/mcp"
SERVICE_HUB_MCP_URL = "https://<your-servicehub-app-url>/mcp"

# System Prompt
SYSTEM_PROMPT = """You are 'Bricksy', an intelligent Vehicle Assist Agent.

Your capabilities:

1. **Manual Search:** If the user asks technical questions, use 'search_vehicle_manual'.
   - ALWAYS pass the 'vehicle_model' argument based on the context provided.

2. **Diagnosis:** If the user asks to diagnose or check health, analyze the provided telemetry.
   - Use 'diagnose_vehicle_health' if you need a strict safety check.

3. **Memory:** You can remember and recall user preferences (e.g., seat height, preferred AC temperature) using memory tools.

4. **Car Dashboard Controls (via MCP):** You can control the vehicle's dashboard systems:
   - `control_wipers(mode)` — Control windshield wipers. Mode must be one of: "off", "slow", "fast".
   - `control_ac(temperature)` — Control AC temperature. Temperature in Celsius (16-30).
   - `control_ambient_light(color)` — Control ambient lighting. Color must be one of: red, blue, green, white, purple, orange.
   - `control_seat(height)` — Control driver seat height. Height 0-100 (0=lowest, 100=highest).
   - `control_speed(speed)` — Update vehicle speed (simulation). Speed in mph (0-150).
   - `get_car_state()` — Get complete current state of all car controls.

5. **Service Hub (via MCP):** You can help the user find service centers and manage bookings:
   - `health()` — Check ServiceHub server health.
   - `list_states()` — List all Indian states with registered service centers.
   - `list_cities(state)` — List cities in a state that have service centers.
   - `list_areas(state, city)` — List locality areas in a city that have service centers.
   - `search_service_centers(state, city, area)` — Search for service centers by location. All params optional.
   - `get_slot_availability(center_id, days_ahead)` — Get slot availability for a service center (default 14 days ahead).
   - `create_booking(center_id, slot_date, vehicle_number, customer_name, service_type)` — Book a service slot.
   - `cancel_booking(booking_id)` — Cancel an existing booking.
   - `list_bookings(center_id, slot_date)` — List all bookings for a service center on a given date.

IMPORTANT NOTES:
- Only answer the relevant answer that is asked. DO NOT provide extra information.
- If you are unsure, ask the user for clarification.
- Be concise, helpful, and safety-conscious.
- When a user wants to book a service, guide them step by step: find state → city → area → service center → check availability → book.
"""

logger = logging.getLogger(__name__)

# ==============================================================================
# 2. MCP CLIENT SETUP
# ==============================================================================
workspace_client = WorkspaceClient(
    host="<host_name>",
    client_id="<client_id>",
    client_secret="<client_secret>",
    token="",  # Explicitly disable PAT to avoid conflict with env DATABRICKS_TOKEN
    auth_type="oauth-m2m",
)

databricks_mcp_client = DatabricksMultiServerMCPClient([
    DatabricksMCPServer(
        name="car-dashboard",
        url=DASHBOARD_MCP_URL,
        workspace_client=workspace_client,
    ),
    DatabricksMCPServer(
        name="service-hub",
        url=SERVICE_HUB_MCP_URL,
        workspace_client=workspace_client,
    ),
])

# ==============================================================================
# 3. LOCAL TOOL DEFINITIONS
# ==============================================================================

@tool
def search_vehicle_manual(query: str, vehicle_model: Optional[str] = None) -> str:
    """
    Searches the vehicle owner's manual for specific information.

    Args:
        query: The user's question (e.g., "how to reset hill hold").
        vehicle_model: The specific car model to filter results (e.g., "XUV 7XO", "Thar").
                       If not provided, it may return results for the wrong car.
    """
    try:
        vsc = VectorSearchClient(disable_notice=True)
        index = vsc.get_index(endpoint_name=VS_ENDPOINT_NAME, index_name=VS_INDEX_NAME)

        filters = {"vehicle_model": vehicle_model} if vehicle_model else None

        results = index.similarity_search(
            query_text=query,
            columns=["text", "vehicle_model"],
            filters=filters,
            num_results=3,
        )

        docs = results.get("result", {}).get("data_array", [])
        if not docs:
            return f"No manual entries found for model: {vehicle_model}."

        return "\n\n".join([f"[Model: {d[1]}] {d[0]}" for d in docs])

    except Exception as e:
        return f"Error searching manual: {str(e)}"


@tool
def diagnose_vehicle_health(telemetry_json: str) -> str:
    """
    Performs a deterministic safety check on vehicle telemetry data.
    Input must be a valid JSON string.
    """
    try:
        data = json.loads(telemetry_json)
        issues = []

        MAX_ENGINE_TEMP = 105
        MIN_TIRE_PRESSURE = 30

        temp = data.get("engine_temperature") or data.get("engine_temp")
        if temp and float(temp) > MAX_ENGINE_TEMP:
            issues.append(f"CRITICAL: Engine Overheating ({temp}°C). Stop immediately.")

        for key, val in data.items():
            if "tpms" in key.lower() and float(val) < MIN_TIRE_PRESSURE:
                friendly_name = key.replace("_", " ").upper()
                issues.append(f"WARNING: Low Tire Pressure - {friendly_name} ({val} PSI).")

        if not issues:
            return "Diagnosis Result: All systems nominal. No active faults detected."

        return "Diagnosis Report:\n" + "\n".join(issues)

    except Exception as e:
        return f"Diagnosis failed: {str(e)}"


local_tools = [search_vehicle_manual, diagnose_vehicle_health]

# ==============================================================================
# 4. AGENT DEFINITION
# ==============================================================================

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: Optional[str]
    conversation_id: Optional[str]


class VehicleAgent(ResponsesAgent):
    def __init__(self):
        self.lakebase_instance_name = LAKEBASE_INSTANCE_NAME
        self.system_prompt = SYSTEM_PROMPT
        self.model = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)
        self._store = None
        self._agent = None

    @property
    def store(self):
        """Lazy initialization of DatabricksStore with semantic search support."""
        if self._store is None:
            logger.info(
                f"Initializing DatabricksStore with instance: {self.lakebase_instance_name}"
            )
            self._store = DatabricksStore(
                instance_name=self.lakebase_instance_name,
                embedding_endpoint=EMBEDDING_ENDPOINT,
                embedding_dims=EMBEDDING_DIMS,
            )
            self._store.setup()
        return self._store

    def _create_memory_tools(self):
        """Create tools for reading and writing long-term memory."""

        @tool
        def get_user_memory(query: str, config: RunnableConfig) -> str:
            """Search for relevant information about the user from long-term memory using semantic search.

            Use this tool to retrieve previously saved information about the user,
            such as their preferences, facts they've shared, or other personal details.

            Args:
                query: The search query to find relevant memories.
            """
            user_id = config.get("configurable", {}).get("user_id")
            if not user_id:
                return "Memory not available - no user_id provided."

            namespace = ("user_memories", user_id.replace(".", "-"))
            results = self.store.search(namespace, query=query, limit=5)

            if not results:
                return "No memories found for this user."

            memory_items = []
            for item in results:
                memory_items.append(f"- [{item.key}]: {json.dumps(item.value)}")

            return (
                f"Found {len(results)} relevant memories (ranked by semantic similarity):\n"
                + "\n".join(memory_items)
            )

        @tool
        def save_user_memory(
            memory_key: str, memory_data_json: str, config: RunnableConfig
        ) -> str:
            """Save information about the user to long-term memory.

            Use this tool to remember important information the user shares about themselves,
            such as preferences, facts, or other personal details.

            Args:
                memory_key: A descriptive key for this memory (e.g., "ambient_color", "seat_height")
                memory_data_json: JSON string with the information to remember.
                    Example: '{"ambient_color": "cool blue"}'
            """
            user_id = config.get("configurable", {}).get("user_id")
            if not user_id:
                return "Cannot save memory - no user_id provided."

            namespace = ("user_memories", user_id.replace(".", "-"))

            try:
                memory_data = json.loads(memory_data_json)
                if not isinstance(memory_data, dict):
                    return f"Failed to save memory: memory_data must be a JSON object, not {type(memory_data).__name__}."
                self.store.put(namespace, memory_key, memory_data)
                return f"Successfully saved memory with key '{memory_key}' for user."
            except json.JSONDecodeError as e:
                return f"Failed to save memory: Invalid JSON format - {str(e)}"

        @tool
        def delete_user_memory(memory_key: str, config: RunnableConfig) -> str:
            """Delete a specific memory from the user's long-term memory.

            Args:
                memory_key: The key of the memory to delete (e.g., "ambient_color", "seat_height")
            """
            user_id = config.get("configurable", {}).get("user_id")
            if not user_id:
                return "Cannot delete memory - no user_id provided."

            namespace = ("user_memories", user_id.replace(".", "-"))
            self.store.delete(namespace, memory_key)
            return f"Successfully deleted memory with key '{memory_key}' for user."

        return [get_user_memory, save_user_memory, delete_user_memory]

    async def _build_agent(self, context_str: str):
        """Build the LangGraph agent with MCP tools + local tools + memory tools."""
        # Get MCP tools from both servers
        mcp_tools = await databricks_mcp_client.get_tools()

        # Combine all tools
        memory_tools = self._create_memory_tools()
        all_tools = local_tools + memory_tools + mcp_tools

        model_with_tools = self.model.bind_tools(all_tools)

        def should_continue(state: AgentState) -> str:
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "continue"
            return "end"

        def call_model(state: AgentState, config: RunnableConfig):
            full_prompt = f"{self.system_prompt}\n\n{context_str}"
            msgs = [{"role": "system", "content": full_prompt}] + state["messages"]
            response = model_with_tools.invoke(msgs, config)
            return {"messages": [response]}

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", RunnableLambda(call_model))
        workflow.add_node("tools", ToolNode(all_tools))
        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {"continue": "tools", "end": END},
        )
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done" or event.type == "error"
        ]
        return ResponsesAgentResponse(output=outputs)

    async def _predict_stream_async(
        self, request: ResponsesAgentRequest
    ) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
        # 1. Extract custom inputs
        custom_inputs = request.custom_inputs or {}

        user_id = custom_inputs.get("user_id") or (
            request.context.user_id if request.context else "default_user"
        )
        conv_id = custom_inputs.get("conversation_id") or (
            request.context.conversation_id if request.context else "default_sess"
        )

        vehicle_model = custom_inputs.get("vehicle_model", "Unknown Model")
        telemetry = custom_inputs.get("telemetry", {})

        # 2. Build context string
        context_str = f"""
--- CURRENT CONTEXT ---
User ID: {user_id}
Vehicle Model: {vehicle_model}
Live Telemetry Data: {json.dumps(telemetry)}
-----------------------
"""

        # 3. Prepare inputs and config
        inputs = to_chat_completions_input([m.model_dump() for m in request.input])
        config = {"configurable": {"user_id": user_id, "conversation_id": conv_id}}

        # 4. Build graph with context
        graph = await self._build_agent(context_str)
        initial_state = {
            "messages": inputs,
            "user_id": user_id,
            "conversation_id": conv_id,
        }

        # 5. Execute and stream using async (required for MCP tools)
        async for event in graph.astream(initial_state, config, stream_mode="updates"):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    messages = node_data["messages"]
                    if not isinstance(messages, list):
                        messages = [messages]

                    # Ensure ToolMessage content is string
                    for msg in messages:
                        if isinstance(msg, ToolMessage) and not isinstance(
                            msg.content, str
                        ):
                            msg.content = json.dumps(msg.content)

                    for item in output_to_responses_items_stream(messages):
                        yield item

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        agen = self._predict_stream_async(request)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        ait = agen.__aiter__()
        while True:
            try:
                item = loop.run_until_complete(ait.__anext__())
            except StopAsyncIteration:
                break
            else:
                yield item


# ==============================================================================
# 5. REGISTER THE MODEL
# ==============================================================================

contextvars.copy_context()
mlflow.langchain.autolog()
AGENT = VehicleAgent()
mlflow.models.set_model(AGENT)
