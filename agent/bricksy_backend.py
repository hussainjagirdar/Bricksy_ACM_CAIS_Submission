# Databricks notebook source
# MAGIC %pip install -U -qqqq uv databricks-agents mlflow-skinny[databricks] databricks-langchain[memory] databricks-mcp
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import nest_asyncio
nest_asyncio.apply()

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient

# Replace with your deployed app URL
# mcp_server_url = "https://<your-car-dashboard-app-url>/mcp"
mcp_server_url = "https://<your-servicehub-app-url>/mcp"

workspace_client = WorkspaceClient(
    host="<host_name>",
    client_id="<client_id>",
    client_secret="<client_secret>"
)


mcp_client = DatabricksMCPClient(server_url=mcp_server_url, workspace_client=workspace_client)

# List available tools
tools = mcp_client.list_tools()
print(f"Available tools of service hub mcp : {tools}")

# COMMAND ----------

# %%writefile agent.py

# import json
# import logging
# import os
# from typing import Annotated, Any, Generator, Optional, Sequence, TypedDict

# import mlflow
# from databricks_langchain import ChatDatabricks, DatabricksStore
# from databricks.vector_search.client import VectorSearchClient
# from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
# from langchain_core.runnables import RunnableConfig, RunnableLambda
# from langchain_core.tools import tool
# from langgraph.graph import END, StateGraph
# from langgraph.graph.message import add_messages
# from langgraph.prebuilt.tool_node import ToolNode
# from mlflow.pyfunc import ResponsesAgent
# from mlflow.types.chat import ChatMessage
# from mlflow.types.responses import (
#     ResponsesAgentRequest,
#     ResponsesAgentResponse,
#     ResponsesAgentStreamEvent,
#     output_to_responses_items_stream,
#     to_chat_completions_input,
# )

# # ==============================================================================
# # 1. CONFIGURATION
# # ==============================================================================
# # TODO: Replace these with your actual Databricks Endpoint and Index names
# LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
# VS_ENDPOINT_NAME = "product_search_endpoint"
# VS_INDEX_NAME = "<catalog>.<schema>.car_manual_vs_index"
# LAKEBASE_INSTANCE_NAME = "<your-lakebase-instance-name>" # Leave empty if not using Lakebase
# EMBEDDING_ENDPOINT = "databricks-gte-large-en"  
# EMBEDDING_DIMS = 1024

# # Base System Prompt
# SYSTEM_PROMPT = """You are 'Bricksy', an intelligent Vehicle Assist Agent.
# Your capabilities:
# 1. **Manual Search:** If the user asks technical questions, use 'search_vehicle_manual'. 
#    - ALWAYS pass the 'vehicle_model' argument based on the context provided.
# 2. **Diagnosis:** If the user asks to diagnose or check health, analyze the provided telemetry.
#    - Use 'diagnose_vehicle_health' if you need a strict safety check.
# 3. **Memory:** You can remember and recall user preferences (e.g., seat height) using memory tools.

# IMPORTANT NOTES: Only answer the relevant answer that is asked. DO NOT provide extra Information.
# If you are unsure, ask the user for clarification.
# Be concise, helpful, and safety-conscious.
# """

# logger = logging.getLogger(__name__)

# # ==============================================================================
# # 2. TOOL DEFINITIONS
# # ==============================================================================


# # @tool
# # def genie_on_telemetry_tool(query: str) -> str:
# #     # Define the Genie Agent (The Logic)
# #     genie_agent_runnable = GenieAgent(
# #         genie_space_id="01f10101352e18cb968fbb5695433ad8", 
# #         genie_agent_name="Car_telemetry_genie",
# #         description="This agent can answer alert related questions on car's telemetry dataset on typre pressures and engine temperature. This genie can be useful for supervisor agent for finding anomolies in the telemetry data, and providing relevant alerts to the driver for their safety.",
# #     )
# #     return genie_agent_runnable.invoke({"messages": [{"role": "user", "content": query}]})


# @tool
# def search_vehicle_manual(query: str, vehicle_model: Optional[str] = None) -> str:
#     """
#     Searches the vehicle owner's manual for specific information.
    
#     Args:
#         query: The user's question (e.g., "how to reset hill hold").
#         vehicle_model: The specific car model to filter results (e.g., "XUV 7XO", "Thar").
#                        If not provided, it may return results for the wrong car.
#     """
#     try:
#         # Initialize client inside tool to ensure serialization safety
#         vsc = VectorSearchClient(disable_notice=True)
#         index = vsc.get_index(endpoint_name=VS_ENDPOINT_NAME, index_name=VS_INDEX_NAME)
        
#         # Dynamic Metadata Filtering
#         filters = {"vehicle_model": vehicle_model} if vehicle_model else None
        
#         results = index.similarity_search(
#             query_text=query,
#             columns=["text", "vehicle_model"], # Adjust based on your Delta Table columns
#             filters=filters,
#             num_results=3
#         )
        
#         docs = results.get('result', {}).get('data_array', [])
#         if not docs:
#             return f"No manual entries found for model: {vehicle_model}."
            
#         return "\n\n".join([f"[Model: {d[1]}] {d[0]}" for d in docs])
        
#     except Exception as e:
#         return f"Error searching manual: {str(e)}"

# @tool
# def diagnose_vehicle_health(telemetry_json: str) -> str:
#     """
#     Performs a deterministic safety check on vehicle telemetry data.
#     Input must be a valid JSON string.
#     """
#     try:
#         data = json.loads(telemetry_json)
#         issues = []
        
#         # Thresholds
#         MAX_ENGINE_TEMP = 105
#         MIN_TIRE_PRESSURE = 30
        
#         # 1. Check Engine Temp
#         temp = data.get("engine_temperature") or data.get("engine_temp")
#         if temp and float(temp) > MAX_ENGINE_TEMP:
#             issues.append(f"CRITICAL: Engine Overheating ({temp}°C). Stop immediately.")
            
#         # 2. Check Tire Pressures
#         for key, val in data.items():
#             if "tpms" in key.lower() and float(val) < MIN_TIRE_PRESSURE:
#                 friendly_name = key.replace("_", " ").upper()
#                 issues.append(f"WARNING: Low Tire Pressure - {friendly_name} ({val} PSI).")
                
#         if not issues:
#             return "Diagnosis Result: All systems nominal. No active faults detected."
            
#         return "Diagnosis Report:\n" + "\n".join(issues)

#     except Exception as e:
#         return f"Diagnosis failed: {str(e)}"

# # ==============================================================================
# # 3. AGENT DEFINITION
# # ==============================================================================

# class AgentState(TypedDict):
#     messages: Annotated[Sequence[BaseMessage], add_messages]
#     user_id: Optional[str]
#     conversation_id: Optional[str]

# class VehicleAgent(ResponsesAgent):
#     def __init__(self):
#         self.lakebase_instance_name = LAKEBASE_INSTANCE_NAME
#         self.system_prompt = SYSTEM_PROMPT
#         self.model = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)

#         self._store = None
#         self._memory_tools = None

#     @property
#     def store(self):
#         """Lazy initialization of DatabricksStore with semantic search support."""
#         if self._store is None:
#             logger.info(f"Initializing DatabricksStore with instance: {self.lakebase_instance_name} and embedding endpoint {EMBEDDING_ENDPOINT} with dims {EMBEDDING_DIMS}")
#             self._store = DatabricksStore(
#                 instance_name=self.lakebase_instance_name,
#                 embedding_endpoint=EMBEDDING_ENDPOINT,
#                 embedding_dims=EMBEDDING_DIMS,
#             )
#             self._store.setup()
#         return self._store

#     @property
#     def memory_tools(self):
#         """Lazy initialization of memory tools."""
#         if self._memory_tools is None:
#             logger.info("Creating memory tools")
#             self._memory_tools = self._create_memory_tools()
#         return self._memory_tools

#     @property
#     def model_with_all_tools(self):
#         all_tools = tools + self.memory_tools
#         return self.model.bind_tools(all_tools) if all_tools else self.model

#     def _create_memory_tools(self):
#         """Create tools for reading and writing long-term memory."""

#         @tool
#         def get_user_memory(query: str, config: RunnableConfig) -> str:
#             """Search for relevant information about the user from long-term memory using semantic search via vector embeddings.

#             Use this tool to retrieve previously saved information about the user,
#             such as their preferences, facts they've shared, or other personal details.

#             Args:
#             """
#             user_id = config.get("configurable", {}).get("user_id")
#             if not user_id:
#                 return "Memory not available - no user_id provided."

#             namespace = ("user_memories", user_id.replace(".", "-"))

#             results = self.store.search(namespace, query=query, limit=5)

#             if not results:
#                 return "No memories found for this user."

#             memory_items = []
#             for item in results:
#                 memory_items.append(f"- [{item.key}]: {json.dumps(item.value)}")

#             return f"Found {len(results)} relevant memories (ranked by semantic similarity):\n" + "\n".join(memory_items)

#         @tool
#         def save_user_memory(memory_key: str, memory_data_json: str, config: RunnableConfig) -> str:
#             """Save information about the user to long-term memory with vector embeddings.

#             Use this tool to remember important information the user shares about themselves,
#             such as preferences, facts, or other personal details.

#             Args:
#                 memory_key: A descriptive key for this memory (e.g., "ambient_color", "seat_height", "driving_mode")
#                 memory_data_json: JSON string with the information to remember.
#                     Example: '{"ambient_color": "cool blue"}'
#             """
#             user_id = config.get("configurable", {}).get("user_id")
#             if not user_id:
#                 return "Cannot save memory - no user_id provided."

#             namespace = ("user_memories", user_id.replace(".", "-"))

#             try:
#                 memory_data = json.loads(memory_data_json)
#                 # Validate that memory_data is a dictionary (not a list or other type)
#                 if not isinstance(memory_data, dict):
#                     return f"Failed to save memory: memory_data must be a JSON object (dictionary), not {type(memory_data).__name__}. Example: '{{\"key\": \"value\"}}'"
#                 self.store.put(namespace, memory_key, memory_data)
#                 return f"Successfully saved memory with key '{memory_key}' for user."
#             except json.JSONDecodeError as e:
#                 return f"Failed to save memory: Invalid JSON format - {str(e)}"

#         @tool
#         def delete_user_memory(memory_key: str, config: RunnableConfig) -> str:
#             """Delete a specific memory from the user's long-term memory.

#             Use this tool when the user asks you to forget something or remove
#             a piece of information from their memory.

#             Args:
#                 memory_key: The key of the memory to delete (e.g., "ambient_color", "seat_height", "driving_mode")
#             """
#             user_id = config.get("configurable", {}).get("user_id")
#             if not user_id:
#                 return "Cannot delete memory - no user_id provided."

#             namespace = ("user_memories", user_id.replace(".", "-"))

#             self.store.delete(namespace, memory_key)
#             return f"Successfully deleted memory with key '{memory_key}' for user."

#         return [get_user_memory, save_user_memory, delete_user_memory]

#     def _create_graph(self, context_str: str):
#         """
#         Creates the LangGraph with dynamic context injected into the System Prompt.
#         """
#         tools = [search_vehicle_manual, diagnose_vehicle_health] + self._create_memory_tools()
#         model_with_tools = self.model.bind_tools(tools)

#         def call_model(state: AgentState, config: RunnableConfig):
#             # Dynamic Prompt Injection: Combine Base Prompt + Live Context
#             full_prompt = f"{SYSTEM_PROMPT}\n\n{context_str}"
            
#             msgs = [{"role": "system", "content": full_prompt}] + state["messages"]
#             return {"messages": [model_with_tools.invoke(msgs, config)]}

#         workflow = StateGraph(AgentState)
#         workflow.add_node("agent", RunnableLambda(call_model))
#         workflow.add_node("tools", ToolNode(tools))
        
#         workflow.add_edge("tools", "agent")
#         workflow.add_conditional_edges(
#             "agent",
#             lambda x: "tools" if x["messages"][-1].tool_calls else END,
#             ["tools", END]
#         )
#         workflow.set_entry_point("agent")
#         return workflow.compile()

#     def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
#         """
#         Non-streaming wrapper. Required by the abstract base class.
#         """
#         # We consume the stream and return the final output items
#         outputs = [
#             event.item
#             for event in self.predict_stream(request)
#             if event.type == "response.output_item.done"
#         ]
#         return ResponsesAgentResponse(output=outputs)

    
#     def predict_stream(self, request: ResponsesAgentRequest) -> Generator[ResponsesAgentStreamEvent, None, None]:
#         # 1. Extract Custom Inputs from Frontend
#         custom_inputs = request.custom_inputs or {}
        
#         user_id = custom_inputs.get("user_id") or (request.context.user_id if request.context else "default_user")
#         conv_id = custom_inputs.get("conversation_id") or (request.context.conversation_id if request.context else "default_sess")
        
#         vehicle_model = custom_inputs.get("vehicle_model", "Unknown Model")
#         telemetry = custom_inputs.get("telemetry", {})

#         # 2. Build Context String for the System Prompt
#         context_str = f"""
#         --- CURRENT CONTEXT ---
#         User ID: {user_id}
#         Vehicle Model: {vehicle_model}
#         Live Telemetry Data: {json.dumps(telemetry)}
#         -----------------------
#         """

#         # 3. Prepare Inputs
#         inputs = to_chat_completions_input([m.model_dump() for m in request.input])
#         config = {"configurable": {"user_id": user_id, "conversation_id": conv_id}}
        
#         # 4. Initialize Graph with Context
#         graph = self._create_graph(context_str)
#         initial_state = {"messages": inputs, "user_id": user_id, "conversation_id": conv_id}
        
#         # 5. Execute and Stream
#         # stream_mode="updates" allows us to capture the fully formed messages from the agent node.
#         # This is required for `output_to_responses_items_stream` to generate the 'done' event 
#         # that the non-streaming `predict` method relies on.
#         for event in graph.stream(initial_state, config, stream_mode="updates"):
#             for node_name, node_data in event.items():
#                 if "messages" in node_data:
#                     messages = node_data["messages"]
#                     # Ensure messages is a list
#                     if not isinstance(messages, list):
#                         messages = [messages]
                        
#                     # This helper yields the necessary MLflow events:
#                     # 1. 'response.content_part.added' (content)
#                     # 2. 'response.output_item.done' (final object required by predict())
#                     yield from output_to_responses_items_stream(messages)

# # Register the model
# mlflow.langchain.autolog()
# AGENT = VehicleAgent()
# mlflow.models.set_model(AGENT)

# COMMAND ----------

# MAGIC %%writefile agent.py
# MAGIC import asyncio
# MAGIC import json
# MAGIC import logging
# MAGIC import os
# MAGIC import contextvars
# MAGIC
# MAGIC from typing import Annotated, Any, AsyncGenerator, Generator, Optional, Sequence, TypedDict, Union
# MAGIC
# MAGIC import mlflow
# MAGIC import nest_asyncio
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks_langchain import (
# MAGIC     ChatDatabricks,
# MAGIC     DatabricksMCPServer,
# MAGIC     DatabricksMultiServerMCPClient,
# MAGIC     DatabricksStore,
# MAGIC )
# MAGIC from databricks.vector_search.client import VectorSearchClient
# MAGIC from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
# MAGIC from langchain_core.messages.tool import ToolMessage
# MAGIC from langchain_core.language_models import LanguageModelLike
# MAGIC from langchain_core.runnables import RunnableConfig, RunnableLambda
# MAGIC from langchain_core.tools import BaseTool, tool
# MAGIC from langgraph.graph import END, StateGraph
# MAGIC from langgraph.graph.message import add_messages
# MAGIC from langgraph.prebuilt.tool_node import ToolNode
# MAGIC from mlflow.pyfunc import ResponsesAgent
# MAGIC from mlflow.types.responses import (
# MAGIC     ResponsesAgentRequest,
# MAGIC     ResponsesAgentResponse,
# MAGIC     ResponsesAgentStreamEvent,
# MAGIC     output_to_responses_items_stream,
# MAGIC     to_chat_completions_input,
# MAGIC )
# MAGIC
# MAGIC nest_asyncio.apply()
# MAGIC
# MAGIC # ==============================================================================
# MAGIC # 1. CONFIGURATION
# MAGIC # ==============================================================================
# MAGIC LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
# MAGIC VS_ENDPOINT_NAME = "product_search_endpoint"
# MAGIC VS_INDEX_NAME = "<catalog>.<schema>.car_manual_vs_index"
# MAGIC LAKEBASE_INSTANCE_NAME = "<your-lakebase-instance-name>"
# MAGIC EMBEDDING_ENDPOINT = "databricks-gte-large-en"
# MAGIC EMBEDDING_DIMS = 1024
# MAGIC
# MAGIC # MCP Server URLs
# MAGIC DASHBOARD_MCP_URL = "https://<your-car-dashboard-app-url>/mcp"
# MAGIC SERVICE_HUB_MCP_URL = "https://<your-servicehub-app-url>/mcp"
# MAGIC
# MAGIC # System Prompt
# MAGIC SYSTEM_PROMPT = """You are 'Bricksy', an intelligent Vehicle Assist Agent.
# MAGIC
# MAGIC Your capabilities:
# MAGIC
# MAGIC 1. **Manual Search:** If the user asks technical questions, use 'search_vehicle_manual'.
# MAGIC    - ALWAYS pass the 'vehicle_model' argument based on the context provided.
# MAGIC
# MAGIC 2. **Diagnosis:** If the user asks to diagnose or check health, analyze the provided telemetry.
# MAGIC    - Use 'diagnose_vehicle_health' if you need a strict safety check.
# MAGIC
# MAGIC 3. **Memory:** You can remember and recall user preferences (e.g., seat height, preferred AC temperature) using memory tools.
# MAGIC
# MAGIC 4. **Car Dashboard Controls (via MCP):** You can control the vehicle's dashboard systems:
# MAGIC    - `control_wipers(mode)` — Control windshield wipers. Mode must be one of: "off", "slow", "fast".
# MAGIC    - `control_ac(temperature)` — Control AC temperature. Temperature in Celsius (16-30).
# MAGIC    - `control_ambient_light(color)` — Control ambient lighting. Color must be one of: red, blue, green, white, purple, orange.
# MAGIC    - `control_seat(height)` — Control driver seat height. Height 0-100 (0=lowest, 100=highest).
# MAGIC    - `control_speed(speed)` — Update vehicle speed (simulation). Speed in mph (0-150).
# MAGIC    - `get_car_state()` — Get complete current state of all car controls.
# MAGIC
# MAGIC 5. **Service Hub (via MCP):** You can help the user find service centers and manage bookings:
# MAGIC    - `health()` — Check ServiceHub server health.
# MAGIC    - `list_states()` — List all Indian states with registered service centers.
# MAGIC    - `list_cities(state)` — List cities in a state that have service centers.
# MAGIC    - `list_areas(state, city)` — List locality areas in a city that have service centers.
# MAGIC    - `search_service_centers(state, city, area)` — Search for service centers by location. All params optional.
# MAGIC    - `get_slot_availability(center_id, days_ahead)` — Get slot availability for a service center (default 14 days ahead).
# MAGIC    - `create_booking(center_id, slot_date, vehicle_number, customer_name, service_type)` — Book a service slot.
# MAGIC    - `cancel_booking(booking_id)` — Cancel an existing booking.
# MAGIC    - `list_bookings(center_id, slot_date)` — List all bookings for a service center on a given date.
# MAGIC
# MAGIC IMPORTANT NOTES:
# MAGIC - Only answer the relevant answer that is asked. DO NOT provide extra information.
# MAGIC - If you are unsure, ask the user for clarification.
# MAGIC - Be concise, helpful, and safety-conscious.
# MAGIC - When a user wants to book a service, guide them step by step: find state → city → area → service center → check availability → book.
# MAGIC """
# MAGIC
# MAGIC logger = logging.getLogger(__name__)
# MAGIC
# MAGIC # ==============================================================================
# MAGIC # 2. MCP CLIENT SETUP
# MAGIC # ==============================================================================
# MAGIC workspace_client = WorkspaceClient(
# MAGIC     host="<host_name>",
# MAGIC     client_id="<client_id>",
# MAGIC     client_secret="<client_secret>",
# MAGIC     token="",  # Explicitly disable PAT to avoid conflict with env DATABRICKS_TOKEN
# MAGIC     auth_type="oauth-m2m",
# MAGIC )
# MAGIC
# MAGIC databricks_mcp_client = DatabricksMultiServerMCPClient([
# MAGIC     DatabricksMCPServer(
# MAGIC         name="car-dashboard",
# MAGIC         url=DASHBOARD_MCP_URL,
# MAGIC         workspace_client=workspace_client,
# MAGIC     ),
# MAGIC     DatabricksMCPServer(
# MAGIC         name="service-hub",
# MAGIC         url=SERVICE_HUB_MCP_URL,
# MAGIC         workspace_client=workspace_client,
# MAGIC     ),
# MAGIC ])
# MAGIC
# MAGIC # ==============================================================================
# MAGIC # 3. LOCAL TOOL DEFINITIONS
# MAGIC # ==============================================================================
# MAGIC
# MAGIC @tool
# MAGIC def search_vehicle_manual(query: str, vehicle_model: Optional[str] = None) -> str:
# MAGIC     """
# MAGIC     Searches the vehicle owner's manual for specific information.
# MAGIC
# MAGIC     Args:
# MAGIC         query: The user's question (e.g., "how to reset hill hold").
# MAGIC         vehicle_model: The specific car model to filter results (e.g., "XUV 7XO", "Thar").
# MAGIC                        If not provided, it may return results for the wrong car.
# MAGIC     """
# MAGIC     try:
# MAGIC         vsc = VectorSearchClient(disable_notice=True)
# MAGIC         index = vsc.get_index(endpoint_name=VS_ENDPOINT_NAME, index_name=VS_INDEX_NAME)
# MAGIC
# MAGIC         filters = {"vehicle_model": vehicle_model} if vehicle_model else None
# MAGIC
# MAGIC         results = index.similarity_search(
# MAGIC             query_text=query,
# MAGIC             columns=["text", "vehicle_model"],
# MAGIC             filters=filters,
# MAGIC             num_results=3,
# MAGIC         )
# MAGIC
# MAGIC         docs = results.get("result", {}).get("data_array", [])
# MAGIC         if not docs:
# MAGIC             return f"No manual entries found for model: {vehicle_model}."
# MAGIC
# MAGIC         return "\n\n".join([f"[Model: {d[1]}] {d[0]}" for d in docs])
# MAGIC
# MAGIC     except Exception as e:
# MAGIC         return f"Error searching manual: {str(e)}"
# MAGIC
# MAGIC
# MAGIC @tool
# MAGIC def diagnose_vehicle_health(telemetry_json: str) -> str:
# MAGIC     """
# MAGIC     Performs a deterministic safety check on vehicle telemetry data.
# MAGIC     Input must be a valid JSON string.
# MAGIC     """
# MAGIC     try:
# MAGIC         data = json.loads(telemetry_json)
# MAGIC         issues = []
# MAGIC
# MAGIC         MAX_ENGINE_TEMP = 105
# MAGIC         MIN_TIRE_PRESSURE = 30
# MAGIC
# MAGIC         temp = data.get("engine_temperature") or data.get("engine_temp")
# MAGIC         if temp and float(temp) > MAX_ENGINE_TEMP:
# MAGIC             issues.append(f"CRITICAL: Engine Overheating ({temp}°C). Stop immediately.")
# MAGIC
# MAGIC         for key, val in data.items():
# MAGIC             if "tpms" in key.lower() and float(val) < MIN_TIRE_PRESSURE:
# MAGIC                 friendly_name = key.replace("_", " ").upper()
# MAGIC                 issues.append(f"WARNING: Low Tire Pressure - {friendly_name} ({val} PSI).")
# MAGIC
# MAGIC         if not issues:
# MAGIC             return "Diagnosis Result: All systems nominal. No active faults detected."
# MAGIC
# MAGIC         return "Diagnosis Report:\n" + "\n".join(issues)
# MAGIC
# MAGIC     except Exception as e:
# MAGIC         return f"Diagnosis failed: {str(e)}"
# MAGIC
# MAGIC
# MAGIC local_tools = [search_vehicle_manual, diagnose_vehicle_health]
# MAGIC
# MAGIC # ==============================================================================
# MAGIC # 4. AGENT DEFINITION
# MAGIC # ==============================================================================
# MAGIC
# MAGIC class AgentState(TypedDict):
# MAGIC     messages: Annotated[Sequence[BaseMessage], add_messages]
# MAGIC     user_id: Optional[str]
# MAGIC     conversation_id: Optional[str]
# MAGIC
# MAGIC
# MAGIC class VehicleAgent(ResponsesAgent):
# MAGIC     def __init__(self):
# MAGIC         self.lakebase_instance_name = LAKEBASE_INSTANCE_NAME
# MAGIC         self.system_prompt = SYSTEM_PROMPT
# MAGIC         self.model = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)
# MAGIC         self._store = None
# MAGIC         self._agent = None
# MAGIC
# MAGIC     @property
# MAGIC     def store(self):
# MAGIC         """Lazy initialization of DatabricksStore with semantic search support."""
# MAGIC         if self._store is None:
# MAGIC             logger.info(
# MAGIC                 f"Initializing DatabricksStore with instance: {self.lakebase_instance_name}"
# MAGIC             )
# MAGIC             self._store = DatabricksStore(
# MAGIC                 instance_name=self.lakebase_instance_name,
# MAGIC                 embedding_endpoint=EMBEDDING_ENDPOINT,
# MAGIC                 embedding_dims=EMBEDDING_DIMS,
# MAGIC             )
# MAGIC             self._store.setup()
# MAGIC         return self._store
# MAGIC
# MAGIC     def _create_memory_tools(self):
# MAGIC         """Create tools for reading and writing long-term memory."""
# MAGIC
# MAGIC         @tool
# MAGIC         def get_user_memory(query: str, config: RunnableConfig) -> str:
# MAGIC             """Search for relevant information about the user from long-term memory using semantic search.
# MAGIC
# MAGIC             Use this tool to retrieve previously saved information about the user,
# MAGIC             such as their preferences, facts they've shared, or other personal details.
# MAGIC
# MAGIC             Args:
# MAGIC                 query: The search query to find relevant memories.
# MAGIC             """
# MAGIC             user_id = config.get("configurable", {}).get("user_id")
# MAGIC             if not user_id:
# MAGIC                 return "Memory not available - no user_id provided."
# MAGIC
# MAGIC             namespace = ("user_memories", user_id.replace(".", "-"))
# MAGIC             results = self.store.search(namespace, query=query, limit=5)
# MAGIC
# MAGIC             if not results:
# MAGIC                 return "No memories found for this user."
# MAGIC
# MAGIC             memory_items = []
# MAGIC             for item in results:
# MAGIC                 memory_items.append(f"- [{item.key}]: {json.dumps(item.value)}")
# MAGIC
# MAGIC             return (
# MAGIC                 f"Found {len(results)} relevant memories (ranked by semantic similarity):\n"
# MAGIC                 + "\n".join(memory_items)
# MAGIC             )
# MAGIC
# MAGIC         @tool
# MAGIC         def save_user_memory(
# MAGIC             memory_key: str, memory_data_json: str, config: RunnableConfig
# MAGIC         ) -> str:
# MAGIC             """Save information about the user to long-term memory.
# MAGIC
# MAGIC             Use this tool to remember important information the user shares about themselves,
# MAGIC             such as preferences, facts, or other personal details.
# MAGIC
# MAGIC             Args:
# MAGIC                 memory_key: A descriptive key for this memory (e.g., "ambient_color", "seat_height")
# MAGIC                 memory_data_json: JSON string with the information to remember.
# MAGIC                     Example: '{"ambient_color": "cool blue"}'
# MAGIC             """
# MAGIC             user_id = config.get("configurable", {}).get("user_id")
# MAGIC             if not user_id:
# MAGIC                 return "Cannot save memory - no user_id provided."
# MAGIC
# MAGIC             namespace = ("user_memories", user_id.replace(".", "-"))
# MAGIC
# MAGIC             try:
# MAGIC                 memory_data = json.loads(memory_data_json)
# MAGIC                 if not isinstance(memory_data, dict):
# MAGIC                     return f"Failed to save memory: memory_data must be a JSON object, not {type(memory_data).__name__}."
# MAGIC                 self.store.put(namespace, memory_key, memory_data)
# MAGIC                 return f"Successfully saved memory with key '{memory_key}' for user."
# MAGIC             except json.JSONDecodeError as e:
# MAGIC                 return f"Failed to save memory: Invalid JSON format - {str(e)}"
# MAGIC
# MAGIC         @tool
# MAGIC         def delete_user_memory(memory_key: str, config: RunnableConfig) -> str:
# MAGIC             """Delete a specific memory from the user's long-term memory.
# MAGIC
# MAGIC             Args:
# MAGIC                 memory_key: The key of the memory to delete (e.g., "ambient_color", "seat_height")
# MAGIC             """
# MAGIC             user_id = config.get("configurable", {}).get("user_id")
# MAGIC             if not user_id:
# MAGIC                 return "Cannot delete memory - no user_id provided."
# MAGIC
# MAGIC             namespace = ("user_memories", user_id.replace(".", "-"))
# MAGIC             self.store.delete(namespace, memory_key)
# MAGIC             return f"Successfully deleted memory with key '{memory_key}' for user."
# MAGIC
# MAGIC         return [get_user_memory, save_user_memory, delete_user_memory]
# MAGIC
# MAGIC     async def _build_agent(self, context_str: str):
# MAGIC         """Build the LangGraph agent with MCP tools + local tools + memory tools."""
# MAGIC         # Get MCP tools from both servers
# MAGIC         mcp_tools = await databricks_mcp_client.get_tools()
# MAGIC
# MAGIC         # Combine all tools
# MAGIC         memory_tools = self._create_memory_tools()
# MAGIC         all_tools = local_tools + memory_tools + mcp_tools
# MAGIC
# MAGIC         model_with_tools = self.model.bind_tools(all_tools)
# MAGIC
# MAGIC         def should_continue(state: AgentState) -> str:
# MAGIC             last_message = state["messages"][-1]
# MAGIC             if isinstance(last_message, AIMessage) and last_message.tool_calls:
# MAGIC                 return "continue"
# MAGIC             return "end"
# MAGIC
# MAGIC         def call_model(state: AgentState, config: RunnableConfig):
# MAGIC             full_prompt = f"{self.system_prompt}\n\n{context_str}"
# MAGIC             msgs = [{"role": "system", "content": full_prompt}] + state["messages"]
# MAGIC             response = model_with_tools.invoke(msgs, config)
# MAGIC             return {"messages": [response]}
# MAGIC
# MAGIC         workflow = StateGraph(AgentState)
# MAGIC         workflow.add_node("agent", RunnableLambda(call_model))
# MAGIC         workflow.add_node("tools", ToolNode(all_tools))
# MAGIC         workflow.set_entry_point("agent")
# MAGIC
# MAGIC         workflow.add_conditional_edges(
# MAGIC             "agent",
# MAGIC             should_continue,
# MAGIC             {"continue": "tools", "end": END},
# MAGIC         )
# MAGIC         workflow.add_edge("tools", "agent")
# MAGIC
# MAGIC         return workflow.compile()
# MAGIC
# MAGIC     def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
# MAGIC         outputs = [
# MAGIC             event.item
# MAGIC             for event in self.predict_stream(request)
# MAGIC             if event.type == "response.output_item.done" or event.type == "error"
# MAGIC         ]
# MAGIC         return ResponsesAgentResponse(output=outputs)
# MAGIC
# MAGIC     async def _predict_stream_async(
# MAGIC         self, request: ResponsesAgentRequest
# MAGIC     ) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
# MAGIC         # 1. Extract custom inputs
# MAGIC         custom_inputs = request.custom_inputs or {}
# MAGIC
# MAGIC         user_id = custom_inputs.get("user_id") or (
# MAGIC             request.context.user_id if request.context else "default_user"
# MAGIC         )
# MAGIC         conv_id = custom_inputs.get("conversation_id") or (
# MAGIC             request.context.conversation_id if request.context else "default_sess"
# MAGIC         )
# MAGIC
# MAGIC         vehicle_model = custom_inputs.get("vehicle_model", "Unknown Model")
# MAGIC         telemetry = custom_inputs.get("telemetry", {})
# MAGIC
# MAGIC         # 2. Build context string
# MAGIC         context_str = f"""
# MAGIC --- CURRENT CONTEXT ---
# MAGIC User ID: {user_id}
# MAGIC Vehicle Model: {vehicle_model}
# MAGIC Live Telemetry Data: {json.dumps(telemetry)}
# MAGIC -----------------------
# MAGIC """
# MAGIC
# MAGIC         # 3. Prepare inputs and config
# MAGIC         inputs = to_chat_completions_input([m.model_dump() for m in request.input])
# MAGIC         config = {"configurable": {"user_id": user_id, "conversation_id": conv_id}}
# MAGIC
# MAGIC         # 4. Build graph with context
# MAGIC         graph = await self._build_agent(context_str)
# MAGIC         initial_state = {
# MAGIC             "messages": inputs,
# MAGIC             "user_id": user_id,
# MAGIC             "conversation_id": conv_id,
# MAGIC         }
# MAGIC
# MAGIC         # 5. Execute and stream using async (required for MCP tools)
# MAGIC         async for event in graph.astream(initial_state, config, stream_mode="updates"):
# MAGIC             for node_name, node_data in event.items():
# MAGIC                 if "messages" in node_data:
# MAGIC                     messages = node_data["messages"]
# MAGIC                     if not isinstance(messages, list):
# MAGIC                         messages = [messages]
# MAGIC
# MAGIC                     # Ensure ToolMessage content is string
# MAGIC                     for msg in messages:
# MAGIC                         if isinstance(msg, ToolMessage) and not isinstance(
# MAGIC                             msg.content, str
# MAGIC                         ):
# MAGIC                             msg.content = json.dumps(msg.content)
# MAGIC
# MAGIC                     for item in output_to_responses_items_stream(messages):
# MAGIC                         yield item
# MAGIC
# MAGIC     def predict_stream(
# MAGIC         self, request: ResponsesAgentRequest
# MAGIC     ) -> Generator[ResponsesAgentStreamEvent, None, None]:
# MAGIC         agen = self._predict_stream_async(request)
# MAGIC         try:
# MAGIC             loop = asyncio.get_event_loop()
# MAGIC         except RuntimeError:
# MAGIC             loop = asyncio.new_event_loop()
# MAGIC             asyncio.set_event_loop(loop)
# MAGIC
# MAGIC         ait = agen.__aiter__()
# MAGIC         while True:
# MAGIC             try:
# MAGIC                 item = loop.run_until_complete(ait.__anext__())
# MAGIC             except StopAsyncIteration:
# MAGIC                 break
# MAGIC             else:
# MAGIC                 yield item
# MAGIC
# MAGIC
# MAGIC # ==============================================================================
# MAGIC # 5. REGISTER THE MODEL
# MAGIC # ==============================================================================
# MAGIC
# MAGIC contextvars.copy_context()
# MAGIC mlflow.langchain.autolog()
# MAGIC AGENT = VehicleAgent()
# MAGIC mlflow.models.set_model(AGENT)

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from agent import AGENT
import mlflow
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ChatContext
)

# ==============================================================================
# TEST CASE 1: Memory Storage (User's Example)
# ==============================================================================
print("\n--- Test 1: Memory Storage ---")

req_memory = ResponsesAgentRequest(
    # FIX: Pass a raw dictionary instead of a ChatMessage object
    input=[{
        "role": "user", 
        "content": "Please remember I like my driver seat height set to 'Medium' and I drive mostly in City mode and preferred ambient light color as blue."
    }],
    context=ChatContext(
        conversation_id="sess_abc_123",
        user_id="driver_alice"
    ),
    custom_inputs={
        "vehicle_model": "XUV 700",
        "telemetry": {} 
    }
)

result_memory = AGENT.predict(req_memory)
print(result_memory.model_dump(exclude_none=True))

# COMMAND ----------

# ==============================================================================
# TEST CASE 2: Diagnosis (Telemetry)
# ==============================================================================
print("\n--- Test 2: Vehicle Diagnosis ---")

req_diag = ResponsesAgentRequest(
    input=[{
        "role": "user", 
        "content": "Diagnose the current vehicle status."
    }],
    context=ChatContext(
        conversation_id="sess_abc_123",
        user_id="driver_alice"
    ),
    custom_inputs={
        "vehicle_model": "XUV 700",
        "telemetry": {
            "engine_temperature": 115, # Overheating!
            "tpms_fl": 28,             # Low pressure
            "tpms_fr": 35,
            "tpms_bl": 35,
            "tpms_br": 35
        }
    }
)

result_diag = AGENT.predict(req_diag)
print(result_diag.model_dump(exclude_none=True))

# COMMAND ----------

#==============================================================================
# TEST CASE 3: RAG (Manual Search)
# ==============================================================================

from agent import AGENT
import mlflow
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ChatContext
)

print("\n--- Test 3: Manual Search (RAG) ---")

req_rag = ResponsesAgentRequest(
    input=[{
        "role": "user", 
        "content": "What is the fuel capacity of my diesel car?"
    }],
    context=ChatContext(
        conversation_id="sess_abc_123",
        user_id="driver_alice@example.com"
    ),
    custom_inputs={
        "vehicle_model": "SCORPIO-N" 
    }
)

result_rag = AGENT.predict(req_rag)
print(result_rag.model_dump(exclude_none=True))

# COMMAND ----------

#==============================================================================
# TEST CASE 4: Check User Profile Memory
# ==============================================================================

from agent import AGENT
import mlflow
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ChatContext
)

print("\n--- Test 4: Check User Profile Memory ---")

req_rag = ResponsesAgentRequest(
    input=[{
        "role": "user", 
        "content": "Turn on my preferred ambient light."
    }],
    context=ChatContext(
        conversation_id="sess_abc_123",
        user_id="driver_alice"
    ),
    custom_inputs={
        "vehicle_model": "XUV 700" 
    }
)

result_rag = AGENT.predict(req_rag)
print(result_rag.model_dump(exclude_none=True))

# COMMAND ----------

result_rag.output[-1].content[-1]['text']

# COMMAND ----------

#==============================================================================
# TEST CASE 5: Set wipers to fast and driver seat to 90%
# ==============================================================================

from agent import AGENT
import mlflow
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ChatContext
)

print("\n--- Test 4: Check User Profile Memory ---")

req_rag = ResponsesAgentRequest(
    input=[{
        "role": "user", 
        "content": "Set wipers to fast and driver seat to 90%"
    }],
    context=ChatContext(
        conversation_id="sess_abc_123",
        user_id="driver_alice"
    ),
    custom_inputs={
        "vehicle_model": "XUV 700" 
    }
)

result_rag = AGENT.predict(req_rag)
print(result_rag.model_dump(exclude_none=True))

# COMMAND ----------

result_rag.output[-1].content[-1]['text']

# COMMAND ----------

# MAGIC %md
# MAGIC # Log the agent as an MLflow model
# MAGIC Log the agent as code from the agent.py file. See [MLflow - Models from Code](https://mlflow.org/docs/latest/models.html#models-from-code).
# MAGIC
# MAGIC ## Enable automatic authentication for Databricks resources
# MAGIC For the most common Databricks resource types, Databricks supports and recommends declaring resource dependencies for the agent upfront during logging. This enables automatic authentication passthrough when you deploy the agent. With automatic authentication passthrough, Databricks automatically provisions, rotates, and manages short-lived credentials to securely access these resource dependencies from within the agent endpoint.
# MAGIC
# MAGIC To enable automatic authentication, specify the dependent Databricks resources when calling `mlflow.pyfunc.log_model()`.
# MAGIC
# MAGIC **TODO:** 
# MAGIC - Add lakebase as a resource type
# MAGIC - If your Unity Catalog tool queries a [vector search index](https://docs.databricks.com/docs%20link) or leverages [external functions](https://docs.databricks.com/docs%20link), you need to include the dependent vector search index and UC connection objects, respectively, as resources. See docs ([AWS](https://docs.databricks.com/generative-ai/agent-framework/log-agent.html#specify-resources-for-automatic-authentication-passthrough) | [Azure](https://learn.microsoft.com/azure/databricks/generative-ai/agent-framework/log-agent#resources)).

# COMMAND ----------

import mlflow
from mlflow.models.resources import (
    DatabricksServingEndpoint,
    DatabricksVectorSearchIndex,
    DatabricksLakebase
)
from pkg_resources import get_distribution

from agent import LLM_ENDPOINT_NAME, VS_INDEX_NAME, LAKEBASE_INSTANCE_NAME

# 2. explicit Resource Definition
#    We manually list the resources because our tools are custom Python functions
resources = [
    # The LLM acting as the brain
    DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT_NAME),
    
    # The Vector Search Index for the RAG tool
    DatabricksVectorSearchIndex(index_name=VS_INDEX_NAME),
    
    # The Lakebase instance for User Memory (DatabricksStore)
    DatabricksLakebase(database_instance_name=LAKEBASE_INSTANCE_NAME)
]

# 3. Define Input Example with Custom Inputs
#    This tells the serving endpoint what the JSON payload looks like,
#    crucial for the "Playground" UI to generate the correct form.
input_example = {
    "input": [
        {
            "role": "user",
            "content": "Diagnose the current vehicle status."
        }
    ],
    # We explicitly add the custom_inputs schema here
    "custom_inputs": {
        "vehicle_model": "XUV 700",
        "telemetry": {
            "engine_temperature": 110,
            "tpms_fl": 28,
            "tpms_fr": 35,
            "tpms_bl": 35,
            "tpms_br": 35
        },
        "user_id": "driver_alice",
        "conversation_id": "sess_123"
    }
}

# 4. Log the Model
#    We specify the dependencies required for the agent to run in the container.
logged_agent_info = mlflow.pyfunc.log_model(
    artifact_path="bricksy_agent",
    python_model="agent.py",        # Points to the file you created earlier
    input_example=input_example,
    resources=resources,
    pip_requirements=[
        "mlflow==3.8.1",           # Ensure recent MLflow for Chat/Agent features
        "databricks-vectorsearch",  # Required for the manual search tool
        "databricks-langchain",     # Required for DatabricksStore
        "langgraph",
        "langchain-core",
        f"databricks-langchain[memory]=={get_distribution('databricks-langchain[memory]').version}"
    ]
)

print(f"Agent logged successfully! URI: {logged_agent_info.model_uri}")

# COMMAND ----------

# MAGIC %md
# MAGIC # Pre-deployment agent validation
# MAGIC Before registering and deploying the agent, perform pre-deployment checks using the mlflow.models.predict() API.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setting the memory - validation

# COMMAND ----------

# Define the input payload with Telemetry data
payload = {
    # 1. The User Prompt (Simulating the 'Diagnose' button click)
    "input": [
        {
            "role": "user", 
            "content": "Set wipers to fast and driver seat to 90%"
        }
    ],
    # 2. The Context Data (Telemetry, User Info, Vehicle Model)
    "custom_inputs": {
        "vehicle_model": "XUV 700",
        "telemetry": {
            "engine_temperature": 112,  # Example: Overheating (>105)
            "tpms_fl": 28,              # Example: Low Pressure (<30)
            "tpms_fr": 35,
            "tpms_bl": 35,
            "tpms_br": 35,
            "ac_temperature": 22
        },
        "user_id": "driver_bob",
        "conversation_id": "session_diag_001"
    }
}

# Run the prediction
mlflow.models.predict(
    model_uri=logged_agent_info.model_uri,
    input_data=payload,
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Retrieving the memory - validation

# COMMAND ----------

# # Define the input payload with Telemetry data
# payload = {
#     # 1. The User Prompt (Simulating the 'Diagnose' button click)
#     "input": [
#         {
#             "role": "user", 
#             "content": "Turn on my preferred ambient light and driving mode."
#         }
#     ],
#     # 2. The Context Data (Telemetry, User Info, Vehicle Model)
#     "custom_inputs": {
#         "vehicle_model": "XUV 700",
#         "telemetry": {
#             "engine_temperature": 112,  # Example: Overheating (>105)
#             "tpms_fl": 28,              # Example: Low Pressure (<30)
#             "tpms_fr": 35,
#             "tpms_bl": 35,
#             "tpms_br": 35,
#             "ac_temperature": 22
#         },
#         "user_id": "driver_bob",
#         "conversation_id": "session_diag_001"
#     }
# }

# # Run the prediction
# mlflow.models.predict(
#     model_uri=logged_agent_info.model_uri,
#     input_data=payload,
#     env_manager="uv",
# )

# COMMAND ----------

# MAGIC %md
# MAGIC # Register the model to Unity Catalog
# MAGIC Update the `catalog`, `schema`, and `model_name` below to register the MLflow model to Unity Catalog.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

# TODO: define the catalog, schema, and model name for your UC model
catalog = "<your-catalog>"
schema = "bricksy"
model_name = "bricksy_copilot_agent"

UC_MODEL_NAME = f"{catalog}.{schema}.{model_name}"

# register the model to UC
uc_registered_model_info = mlflow.register_model(
    model_uri=logged_agent_info.model_uri, name=UC_MODEL_NAME
)

# COMMAND ----------

# MAGIC %md
# MAGIC #Deploy the Agent

# COMMAND ----------

from databricks import agents
agents.deploy(UC_MODEL_NAME, uc_registered_model_info.version, tags = {"endpointSource": "docs"})

# COMMAND ----------

# MAGIC %md
# MAGIC #Query Deployed agent

# COMMAND ----------

from databricks.sdk import WorkspaceClient

endpoint = "<your-agent-endpoint-name>" # TODO: update this with your endpoint name

w = WorkspaceClient()
client = w.serving_endpoints.get_open_ai_client()

input_msgs = [{"role": "user", "content": "Hey do you know, after how many kms should I change my oil?"}]
## Run for non-streaming responses. Invokes `predict`
extra_body={
        "custom_inputs": {
          "vehicle_model": "XUV 700",
          "telemetry": {
              "engine_temperature": 112,  # Example: Overheating (>105)
              "tpms_fl": 28,              # Example: Low Pressure (<30)
              "tpms_fr": 35,
              "tpms_bl": 35,
              "tpms_br": 35,
              "ac_temperature": 22
          }
        },
        "user_id": "driver_bob",
        "conversation_id": "session_diag_001"
    }
response = client.responses.create(model=endpoint, input=input_msgs, extra_body=extra_body)
print(response)


# COMMAND ----------

