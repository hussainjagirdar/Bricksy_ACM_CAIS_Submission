import asyncio
import json
import logging
import os
from typing import Annotated, Any, Generator, Optional, Sequence, TypedDict

import mlflow
from databricks_langchain import ChatDatabricks, DatabricksStore
from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.chat import ChatMessage
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)
from pydantic import create_model

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
VS_ENDPOINT_NAME = "product_search_endpoint"
VS_INDEX_NAME = "<catalog>.<schema>.car_manual_vs_index"
LAKEBASE_INSTANCE_NAME = "<your-lakebase-instance-name>"
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
EMBEDDING_DIMS = 1024

CUSTOM_MCP_SERVER_URLS = [
    "https://<your-car-dashboard-app-url>/mcp",
    "https://<your-servicehub-app-url>/mcp",
]

SYSTEM_PROMPT = """You are 'Bricksy', an intelligent Vehicle Assist Agent.
Your capabilities:
1. **Manual Search:** If the user asks technical questions, use 'search_vehicle_manual'.
   - ALWAYS pass the 'vehicle_model' argument based on the context provided.
2. **Diagnosis:** If the user asks to diagnose or check health, analyze the provided telemetry.
   - Use 'diagnose_vehicle_health' if you need a strict safety check.
3. **Memory:** You can remember and recall user preferences (e.g., seat height) using memory tools.
4. **Service Booking:** You can search for service centers, check available slots, and book service appointments using the servicehub tools.
5. **Car Dashboards:** You can query car telemetry dashboards and analytics using the dashboard tools.

IMPORTANT NOTES: Only answer the relevant answer that is asked. DO NOT provide extra Information.
If you are unsure, ask the user for clarification.
Be concise, helpful, and safety-conscious.
"""

logger = logging.getLogger(__name__)

# ==============================================================================
# 2. TOOL DEFINITIONS
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
            num_results=3
        )

        docs = results.get('result', {}).get('data_array', [])
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


# ==============================================================================
# 2b. MCP TOOL INTEGRATION
# ==============================================================================

class MCPTool(BaseTool):
    """LangChain tool wrapping a remote MCP server tool."""

    server_url: str = ""
    _workspace_client: Any = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, name: str, description: str, args_schema: type,
                 server_url: str, ws: WorkspaceClient):
        super().__init__(name=name, description=description, args_schema=args_schema)
        self.server_url = server_url
        self._workspace_client = ws

    def _run(self, **kwargs) -> str:
        mcp_client = DatabricksMCPClient(
            server_url=self.server_url,
            workspace_client=self._workspace_client,
        )
        response = mcp_client.call_tool(self.name, kwargs)
        return "".join([c.text for c in response.content])


def _load_mcp_tools(server_urls: list[str]) -> list[BaseTool]:
    """Discover and convert MCP tools from custom Databricks App servers."""
    ws = WorkspaceClient()
    TYPE_MAP = {"integer": int, "number": float, "boolean": bool, "string": str}
    all_tools: list[BaseTool] = []

    for url in server_urls:
        try:
            mcp_client = DatabricksMCPClient(server_url=url, workspace_client=ws)
            for mcp_tool in mcp_client.list_tools():
                schema = mcp_tool.inputSchema or {}
                properties = schema.get("properties", {})
                required = set(schema.get("required", []))

                fields = {}
                for fname, finfo in properties.items():
                    ftype = TYPE_MAP.get(finfo.get("type", "string"), str)
                    fields[fname] = (ftype, ...) if fname in required else (ftype, None)

                args_model = create_model(f"{mcp_tool.name}Args", **fields)

                all_tools.append(MCPTool(
                    name=mcp_tool.name,
                    description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
                    args_schema=args_model,
                    server_url=url,
                    ws=ws,
                ))
            logger.info(f"Loaded MCP tools from {url}")
        except Exception as e:
            logger.warning(f"Failed to load MCP tools from {url}: {e}")

    return all_tools


# ==============================================================================
# 3. AGENT DEFINITION
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
        self._memory_tools = None
        self._mcp_tools = _load_mcp_tools(CUSTOM_MCP_SERVER_URLS)

    @property
    def store(self):
        """Lazy initialization of DatabricksStore with semantic search support."""
        if self._store is None:
            logger.info(f"Initializing DatabricksStore with instance: {self.lakebase_instance_name} and embedding endpoint {EMBEDDING_ENDPOINT} with dims {EMBEDDING_DIMS}")
            self._store = DatabricksStore(
                instance_name=self.lakebase_instance_name,
                embedding_endpoint=EMBEDDING_ENDPOINT,
                embedding_dims=EMBEDDING_DIMS,
            )
            self._store.setup()
        return self._store

    @property
    def memory_tools(self):
        """Lazy initialization of memory tools."""
        if self._memory_tools is None:
            logger.info("Creating memory tools")
            self._memory_tools = self._create_memory_tools()
        return self._memory_tools

    @property
    def model_with_all_tools(self):
        all_tools = [search_vehicle_manual, diagnose_vehicle_health] + self.memory_tools + self._mcp_tools
        return self.model.bind_tools(all_tools) if all_tools else self.model

    def _create_memory_tools(self):
        """Create tools for reading and writing long-term memory."""

        @tool
        def get_user_memory(query: str, config: RunnableConfig) -> str:
            """Search for relevant information about the user from long-term memory using semantic search via vector embeddings.

            Use this tool to retrieve previously saved information about the user,
            such as their preferences, facts they've shared, or other personal details.

            Args:
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

            return f"Found {len(results)} relevant memories (ranked by semantic similarity):\n" + "\n".join(memory_items)

        @tool
        def save_user_memory(memory_key: str, memory_data_json: str, config: RunnableConfig) -> str:
            """Save information about the user to long-term memory with vector embeddings.

            Use this tool to remember important information the user shares about themselves,
            such as preferences, facts, or other personal details.

            Args:
                memory_key: A descriptive key for this memory (e.g., "ambient_color", "seat_height", "driving_mode")
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
                    return f"Failed to save memory: memory_data must be a JSON object (dictionary), not {type(memory_data).__name__}. Example: '{{\"key\": \"value\"}}'"
                self.store.put(namespace, memory_key, memory_data)
                return f"Successfully saved memory with key '{memory_key}' for user."
            except json.JSONDecodeError as e:
                return f"Failed to save memory: Invalid JSON format - {str(e)}"

        @tool
        def delete_user_memory(memory_key: str, config: RunnableConfig) -> str:
            """Delete a specific memory from the user's long-term memory.

            Use this tool when the user asks you to forget something or remove
            a piece of information from their memory.

            Args:
                memory_key: The key of the memory to delete (e.g., "ambient_color", "seat_height", "driving_mode")
            """
            user_id = config.get("configurable", {}).get("user_id")
            if not user_id:
                return "Cannot delete memory - no user_id provided."

            namespace = ("user_memories", user_id.replace(".", "-"))
            self.store.delete(namespace, memory_key)
            return f"Successfully deleted memory with key '{memory_key}' for user."

        return [get_user_memory, save_user_memory, delete_user_memory]

    def _create_graph(self, context_str: str):
        """Creates the LangGraph with dynamic context injected into the System Prompt."""
        all_tools = [search_vehicle_manual, diagnose_vehicle_health] + self._create_memory_tools() + self._mcp_tools
        model_with_tools = self.model.bind_tools(all_tools)

        def call_model(state: AgentState, config: RunnableConfig):
            full_prompt = f"{SYSTEM_PROMPT}\n\n{context_str}"
            msgs = [{"role": "system", "content": full_prompt}] + state["messages"]
            return {"messages": [model_with_tools.invoke(msgs, config)]}

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", RunnableLambda(call_model))
        workflow.add_node("tools", ToolNode(all_tools))

        workflow.add_edge("tools", "agent")
        workflow.add_conditional_edges(
            "agent",
            lambda x: "tools" if x["messages"][-1].tool_calls else END,
            ["tools", END]
        )
        workflow.set_entry_point("agent")
        return workflow.compile()

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """Non-streaming wrapper."""
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(output=outputs)

    def predict_stream(self, request: ResponsesAgentRequest) -> Generator[ResponsesAgentStreamEvent, None, None]:
        # 1. Extract Custom Inputs from Frontend
        custom_inputs = request.custom_inputs or {}

        user_id = custom_inputs.get("user_id") or (request.context.user_id if request.context else "default_user")
        conv_id = custom_inputs.get("conversation_id") or (request.context.conversation_id if request.context else "default_sess")

        vehicle_model = custom_inputs.get("vehicle_model", "Unknown Model")
        telemetry = custom_inputs.get("telemetry", {})

        # 2. Build Context String for the System Prompt
        context_str = f"""
        --- CURRENT CONTEXT ---
        User ID: {user_id}
        Vehicle Model: {vehicle_model}
        Live Telemetry Data: {json.dumps(telemetry)}
        -----------------------
        """

        # 3. Prepare Inputs
        inputs = to_chat_completions_input([m.model_dump() for m in request.input])
        config = {"configurable": {"user_id": user_id, "conversation_id": conv_id}}

        # 4. Initialize Graph with Context
        graph = self._create_graph(context_str)
        initial_state = {"messages": inputs, "user_id": user_id, "conversation_id": conv_id}

        # 5. Execute and Stream
        for event in graph.stream(initial_state, config, stream_mode="updates"):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    messages = node_data["messages"]
                    if not isinstance(messages, list):
                        messages = [messages]
                    yield from output_to_responses_items_stream(messages)


# Register the model
mlflow.langchain.autolog()
AGENT = VehicleAgent()
mlflow.models.set_model(AGENT)
