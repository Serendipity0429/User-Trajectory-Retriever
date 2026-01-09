import json
import asyncio
import agentscope
from decouple import config
from .search import get_search_engine, WebCrawler
from ..models import BenchmarkSettings
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
from core.utils import print_debug
from asgiref.sync import sync_to_async


@sync_to_async
def get_search_engine_safe(fetch_full_content=None):
    return get_search_engine(fetch_full_content=fetch_full_content)

async def web_search_tool(query: str):
    """
    Perform a web search to retrieve up-to-date information. 
    The output will be a list of search results containing titles, links, and snippets.
    To see the full content of a result, use the `visit_page` tool with the link.
    
    Args:
        query (str): The specific search query string. Be precise.
        
    Returns:
        ToolResponse: The search results in JSON format.
    """
    try:
        # Force fetch_full_content=False to simulate human behavior (snippets only)
        engine = await get_search_engine_safe(fetch_full_content=False)
        results = await sync_to_async(engine.search)(query)
        
        if not results:
             return ToolResponse(content="No results found. Please try again with a different or more specific query.")
        
        # Check for error dict
        if isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict) and results[0].get('error'):
            return ToolResponse(content=f"Search Error: {results[0].get('error')}")

        return ToolResponse(content=json.dumps(results))
    except Exception as e:
        return ToolResponse(content=f"Error executing search: {str(e)}")

async def visit_page(url: str):
    """
    Visit a web page to read its full content.
    Use this tool to get detailed information from a search result URL.
    
    Args:
        url (str): The URL of the page to visit.
    """
    try:
        crawler = WebCrawler()
        # WebCrawler.extract is synchronous, run it in a thread
        content = await sync_to_async(crawler.extract)(url)
        
        if not content:
            return ToolResponse(content="Could not extract content from the page. It might be empty or inaccessible.")
            
        return ToolResponse(content=content)
    except Exception as e:
        return ToolResponse(content=f"Error visiting page: {str(e)}")

def answer_question(answer: str):
    """
    Finalize the task by submitting the answer to the user.
    You MUST use this tool to provide the final response after you have gathered sufficient information.

    Args:
        answer (str): The answer to the user's question.
    """
    return ToolResponse(content="Answer submitted successfully.")

def create_memory(memory_type, agent_name, user_id, model=None, llm_settings=None, run_id=None):
    """
    Helper to initialize agent memory based on settings.

    Args:
        memory_type: 'naive', 'mem0', or 'reme'
        agent_name: Name of the agent (e.g., 'VanillaAgent')
        user_id: Base user identifier
        model: LLM model for memory operations
        llm_settings: Settings for embedding model
        run_id: Optional run ID for memory isolation (appended to user_id)

    Returns a tuple: (short_term_memory, long_term_memory)
    - short_term_memory: InMemoryMemory for conversation history
    - long_term_memory: Mem0/ReMe for persistent knowledge (or None if naive/failed)
    """
    # Create unique user_id per run for memory isolation
    effective_user_id = f"{user_id}_run_{run_id}" if run_id else user_id
    print_debug(f"Initializing memory with type: {memory_type}, user_id: {effective_user_id}")

    # Short-term memory for conversation history (always created)
    short_term_memory = InMemoryMemory()

    # Implementation of the update hook for short-term memory
    # This allows pipelines to subscribe to memory updates for real-time trace rendering
    short_term_memory._update_hook = None
    original_add = short_term_memory.add

    async def wrapped_add(*args, **kwargs):
        await original_add(*args, **kwargs)
        if callable(short_term_memory._update_hook):
            # The hook can be sync or async
            res = short_term_memory._update_hook()
            if asyncio.iscoroutine(res):
                await res

    short_term_memory.add = wrapped_add

    # Long-term memory for persistent knowledge (optional)
    long_term_memory = None

    if memory_type == 'naive':
        # No long-term memory for naive mode
        return short_term_memory, None

    embedding_model = None
    if llm_settings:
        try:
            # Use embedding_model from settings (already populated from env if not set)
            embedding_model_name = llm_settings.embedding_model or "text-embedding-3-small"
            # text-embedding-3-small outputs 1536 dimensions by default
            # text-embedding-3-large outputs 3072 dimensions by default
            dimensions = 1536 if "small" in embedding_model_name else 3072
            embedding_model = OpenAITextEmbedding(
                api_key=llm_settings.llm_api_key,
                model_name=embedding_model_name,
                base_url=llm_settings.llm_base_url,
                dimensions=dimensions
            )
        except Exception as e:
            print_debug(f"Failed to init embedding model: {e}")

    if memory_type == 'mem0' and Mem0LongTermMemory:
        try:
            long_term_memory = Mem0LongTermMemory(
                agent_name=agent_name,
                user_name=effective_user_id,
                model=model,
                embedding_model=embedding_model,
                on_disk=False,  # Use in-memory storage to avoid Qdrant conflicts
            )
            print_debug(f"Successfully initialized Mem0 long-term memory (in-memory)")
        except Exception as e:
            print_debug(f"Failed to init Mem0: {e}")
    elif memory_type == 'mem0':
        print_debug(f"Mem0LongTermMemory not available (import failed)")

    elif memory_type == 'reme' and ReMePersonalLongTermMemory:
        try:
            long_term_memory = ReMePersonalLongTermMemory(
                agent_name=agent_name,
                user_name=effective_user_id,
                model=model,
                embedding_model=embedding_model
            )
            print_debug(f"Successfully initialized ReMe long-term memory")
        except Exception as e:
            print_debug(f"Failed to init ReMe: {e}")
    elif memory_type == 'reme':
        print_debug(f"ReMePersonalLongTermMemory not available (import failed)")

    return short_term_memory, long_term_memory

def think(thought: str):
    """
    Use this tool to record your thinking process or reasoning step.
    This helps you plan before taking actions.
    
    Args:
        thought (str): The detailed reasoning content.
    """
    return ToolResponse(content=thought)

class VanillaAgentFactory:
    @staticmethod
    def create_agent(model, verbose: bool = False, run_id=None):
        """
        Create a VanillaAgent with optional long-term memory.

        Args:
            model: The LLM model to use
            verbose: Enable verbose logging
            run_id: Optional run ID for memory isolation

        Returns:
            tuple: (agent, long_term_memory) where long_term_memory may be None
        """
        # Create Toolkit and register tool
        toolkit = Toolkit()
        toolkit.register_tool_function(think)
        toolkit.register_tool_function(web_search_tool)
        toolkit.register_tool_function(visit_page)
        toolkit.register_tool_function(answer_question)

        settings = BenchmarkSettings.get_effective_settings()
        print_debug(f"VanillaAgent: Creating agent with memory_type={settings.memory_type}")
        short_term_memory, long_term_memory = create_memory(
            settings.memory_type,
            agent_name="VanillaAgent",
            user_id="vanilla_agent_user",
            model=model,
            llm_settings=settings,
            run_id=run_id
        )
        print_debug(f"VanillaAgent: long_term_memory is {'set' if long_term_memory else 'None'}")

        # Build system prompt (static_control mode auto-handles memory, no need for prompt section)
        sys_prompt = PROMPTS["vanilla_agent_system_prompt"]

        # Build ReActAgent with proper memory parameters per AgentScope docs
        agent_kwargs = {
            "name": "Assistant",
            "sys_prompt": sys_prompt,
            "model": model,
            "toolkit": toolkit,
            "memory": short_term_memory,
            "formatter": OpenAIChatFormatter(),
            "max_iters": 30,
        }

        # Only add long-term memory if it was successfully created
        # Use static_control mode: system auto-retrieves before each reply and auto-records after
        if long_term_memory is not None:
            agent_kwargs["long_term_memory"] = long_term_memory
            agent_kwargs["long_term_memory_mode"] = "static_control"

        agent = ReActAgent(**agent_kwargs)

        # Debug: Print registered tools
        if hasattr(agent, 'toolkit') and agent.toolkit:
            print_debug(f"VanillaAgent registered tools: {list(agent.toolkit.tools.keys())}")

        return agent, long_term_memory

    @staticmethod
    def init_agentscope(llm_settings: BenchmarkSettings):
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
            stream=False 
        )
        return model
class BrowserAgentFactory:
    @staticmethod
    async def create_agent(model, toolkit: Toolkit, mcp_client: StdIOStatefulClient, verbose: bool = False, run_id=None):
        """
        Create a BrowserAgent with optional long-term memory.

        Args:
            model: The LLM model to use
            toolkit: Tool registry with MCP tools
            mcp_client: MCP client for browser automation
            verbose: Enable verbose logging
            run_id: Optional run ID for memory isolation

        Returns:
            tuple: (agent, long_term_memory) where long_term_memory may be None
        """
        # DEBUG: Print all registered tools
        print_debug(f"BrowserAgent Toolkit Tools: {list(toolkit.tools.keys())}")

        settings = await sync_to_async(BenchmarkSettings.get_effective_settings)()
        print_debug(f"BrowserAgent: Creating agent with memory_type={settings.memory_type}")
        short_term_memory, long_term_memory = create_memory(
            settings.memory_type,
            agent_name="BrowserAgent",
            user_id="browser_agent_user",
            model=model,
            llm_settings=settings,
            run_id=run_id
        )
        print_debug(f"BrowserAgent: long_term_memory is {'set' if long_term_memory else 'None'}")

        # Build system prompt (static_control mode auto-handles memory, no need for prompt section)
        sys_prompt = PROMPTS["browser_agent_system_prompt"]

        # Build ReActAgent with proper memory parameters per AgentScope docs
        agent_kwargs = {
            "name": "BrowserAgent",
            "sys_prompt": sys_prompt,
            "model": model,
            "toolkit": toolkit,
            "memory": short_term_memory,
            "formatter": OpenAIChatFormatter(),
            "max_iters": 30,
        }

        # Only add long-term memory if it was successfully created
        # Use static_control mode: system auto-retrieves before each reply and auto-records after
        if long_term_memory is not None:
            agent_kwargs["long_term_memory"] = long_term_memory
            agent_kwargs["long_term_memory_mode"] = "static_control"

        agent = ReActAgent(**agent_kwargs)

        # Debug: Print registered tools
        if hasattr(agent, 'toolkit') and agent.toolkit:
            print_debug(f"BrowserAgent registered tools: {list(agent.toolkit.tools.keys())}")

        # Attach client to agent for cleanup
        if mcp_client:
            agent.mcp_client = mcp_client

        return agent, long_term_memory

    @staticmethod
    def init_agentscope(llm_settings: BenchmarkSettings):
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
            stream=False 
        )
        
        toolkit = Toolkit()
        toolkit.register_tool_function(think)
        toolkit.register_tool_function(answer_question)

        return model, toolkit
