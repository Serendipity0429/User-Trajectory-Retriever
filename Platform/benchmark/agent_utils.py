import os
import json
import agentscope
from .search_utils import get_search_engine
from .models import LLMSettings, AgentSettings
from .prompts import PROMPTS
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.memory import InMemoryMemory
try:
    from agentscope.memory import Mem0LongTermMemory
except ImportError:
    Mem0LongTermMemory = None

try:
    from agentscope.memory import ReMePersonalLongTermMemory
except ImportError:
    ReMePersonalLongTermMemory = None

from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
from agentscope.embedding import OpenAITextEmbedding
from agentscope.mcp import StdIOStatefulClient
from .utils import print_debug
from asgiref.sync import sync_to_async


@sync_to_async
def get_search_engine_safe():
    return get_search_engine()

async def web_search_tool(query: str):
    """
    Perform a web search to retrieve up-to-date information. 
    Use this tool when you need external knowledge to answer the user's question.
    The output will be a list of search results containing titles, links, and snippets.
    
    Args:
        query (str): The specific search query string. Be precise.
        
    Returns:
        ToolResponse: The search results in JSON format.
    """
    try:
        engine = await get_search_engine_safe()
        results = await sync_to_async(engine.search)(query)
        
        if not results:
             return ToolResponse(content="No results found. Please try again with a different or more specific query.")
        
        # Check for error dict
        if isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict) and results[0].get('error'):
            return ToolResponse(content=f"Search Error: {results[0].get('error')}")

        return ToolResponse(content=json.dumps(results))
    except Exception as e:
        return ToolResponse(content=f"Error executing search: {str(e)}")

def answer_question(answer: str):
    """
    Finalize the task by submitting the answer to the user.
    You MUST use this tool to provide the final response after you have gathered sufficient information.
    Do not just output text; call this tool with your answer.
    
    Args:
        answer (str): The comprehensive answer to the user's question, citing sources if available.
    """
    return ToolResponse(content="Answer submitted successfully.")

class StreamingMemory(InMemoryMemory):
    def __init__(self, update_callback=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_callback = update_callback

    async def add(self, memories, **kwargs):
        await super().add(memories, **kwargs)
        if self.update_callback:
            # Pass a copy of content to avoid concurrent modification issues
            # self.content is a list, accessing it is sync
            self.update_callback(list(self.content))

def create_memory(memory_type, user_id, update_callback=None, model=None, llm_settings=None):
    """Helper to initialize agent memory based on settings."""
    print_debug(f"Initializing memory with type: {memory_type}")
    
    embedding_model = None
    if llm_settings:
        try:
             # Default to text-embedding-3-small if not configured elsewhere
             # Assuming standard OpenAI compatible API for embeddings
            embedding_model = OpenAITextEmbedding(
                api_key=llm_settings.llm_api_key, 
                model_name="text-embedding-3-small"
            )
        except Exception as e:
            print_debug(f"Failed to init embedding model: {e}")

    memory = None
    if memory_type == 'mem0' and Mem0LongTermMemory:
        try:
            memory = Mem0LongTermMemory(user_name=user_id, model=model, embedding_model=embedding_model)
        except Exception as e:
            print_debug(f"Failed to init Mem0: {e}")

    elif memory_type == 'reme' and ReMePersonalLongTermMemory:
        try:
            memory = ReMePersonalLongTermMemory(user_name=user_id, model=model, embedding_model=embedding_model)
        except Exception as e:
            print_debug(f"Failed to init ReMe: {e}")
            
    if memory is None:
        # Default fallback to StreamingMemory which handles callback internally
        return StreamingMemory(update_callback=update_callback) if update_callback else InMemoryMemory()

    # If we initialized a third-party memory AND have a callback, wrap the add method
    if update_callback:
        original_add = memory.add
        
        async def wrapped_add(memories, **kwargs):
            # Call original
            await original_add(memories, **kwargs)
            
            # Trigger callback
            try:
                # Try standard get_memory interface
                msgs = await memory.get_memory()
                if msgs is not None:
                     update_callback(msgs)
            except Exception as e:
                print_debug(f"Error in memory callback wrapper: {e}")
                # Fallback: try accessing content directly if available
                if hasattr(memory, 'content'):
                    update_callback(list(memory.content))

        memory.add = wrapped_add
        
    return memory

class VanillaAgentFactory:
    @staticmethod
    def create_agent(model, verbose: bool = False, update_callback=None):
        # Create Toolkit and register tool
        toolkit = Toolkit()
        toolkit.register_tool_function(web_search_tool)
        toolkit.register_tool_function(answer_question)
        
        agent_settings = AgentSettings.get_effective_settings()
        llm_settings = LLMSettings.get_effective_settings()
        memory = create_memory(agent_settings.memory_type, "vanilla_agent_user", update_callback, model=model, llm_settings=llm_settings)

        return ReActAgent(
            name="Assistant",
            sys_prompt=PROMPTS["vanilla_agent_react_system"],
            model=model,
            toolkit=toolkit,
            memory=memory,
            formatter=OpenAIChatFormatter(),
            max_iters=30,
        )

    @staticmethod
    def init_agentscope(llm_settings: LLMSettings):
        """
        Initialize AgentScope with the project's LLM settings.
        """
        # Initialize basic agentscope environment (logging, etc.)
        try:
            agentscope.init(logging_level="INFO", use_monitor=False)
        except TypeError:
            agentscope.init(logging_level="INFO")
        
        # Create model instance directly
        model = OpenAIChatModel(
            model_name=llm_settings.llm_model,
            api_key=llm_settings.llm_api_key,
            client_kwargs={
                "base_url": llm_settings.llm_base_url,
            },
            stream=True 
        )
        return model
class BrowserAgentFactory:
    @staticmethod
    async def create_agent(model, toolkit: Toolkit, mcp_client: StdIOStatefulClient, verbose: bool = False, update_callback=None):
        # DEBUG: Print all registered tools
        print_debug(f"BrowserAgent Toolkit Tools: {list(toolkit.tools.keys())}")
        
        agent_settings = await sync_to_async(AgentSettings.get_effective_settings)()
        llm_settings = await sync_to_async(LLMSettings.get_effective_settings)()
        memory = create_memory(agent_settings.memory_type, "browser_agent_user", update_callback, model=model, llm_settings=llm_settings)

        agent = ReActAgent(
            name="BrowserAgent",
            sys_prompt=PROMPTS["browser_agent_system"],
            model=model,
            toolkit=toolkit,
            memory=memory,
            formatter=OpenAIChatFormatter(),
            max_iters=30,
        )
        
        # Attach client to agent for cleanup
        if mcp_client:
            agent.mcp_client = mcp_client
            
        return agent

    @staticmethod
    def init_agentscope(llm_settings: LLMSettings):
        """
        Initialize AgentScope with the project's LLM settings.
        Returns model and toolkit. MCP connection is handled externally.
        """
        try:
            agentscope.init(logging_level="INFO", use_monitor=False)
        except TypeError:
            agentscope.init(logging_level="INFO")

        model = OpenAIChatModel(
            model_name=llm_settings.llm_model,
            api_key=llm_settings.llm_api_key,
            client_kwargs={
                "base_url": llm_settings.llm_base_url,
            },
            stream=True 
        )
        
        toolkit = Toolkit()
        toolkit.register_tool_function(answer_question)

        return model, toolkit