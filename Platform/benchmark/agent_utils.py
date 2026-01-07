import os
import json
import asyncio
import agentscope
from .search_utils import get_search_engine, WebCrawler
from .models import BenchmarkSettings
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

def mark_justification(evidence_content: str, source_url: str, reasoning: str):
    """
    Mark a specific piece of text from a webpage as evidence for your final answer.
    You MUST use this tool before providing the final answer to ground your response in the retrieved data.
    
    Args:
        evidence_content (str): The exact text found on the page.
        source_url (str): The URL where this text was found.
        reasoning (str): Briefly explain why this evidence is relevant.
    """
    return ToolResponse(content="Justification marked.")

def answer_question(answer: str):
    """
    Finalize the task by submitting the answer to the user.
    You MUST use this tool to provide the final response after you have gathered sufficient information.
    Ensure you have used `mark_justification` to highlight your evidence before calling this.
    
    Args:
        answer (str): The comprehensive answer to the user's question, citing sources if available.
    """
    return ToolResponse(content="Answer submitted successfully.")

def create_memory(memory_type, user_id, model=None, llm_settings=None):
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
        memory = InMemoryMemory()
    
    # Implementation of the update hook upon initialization
    # This allows pipelines to subscribe to memory updates for real-time trace rendering
    memory._update_hook = None
    original_add = memory.add
    
    async def wrapped_add(*args, **kwargs):
        await original_add(*args, **kwargs)
        if callable(memory._update_hook):
            # The hook can be sync or async
            res = memory._update_hook()
            if asyncio.iscoroutine(res):
                await res
                
    memory.add = wrapped_add
        
    return memory

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
    def create_agent(model, verbose: bool = False):
        # Create Toolkit and register tool
        toolkit = Toolkit()
        toolkit.register_tool_function(think)
        toolkit.register_tool_function(web_search_tool)
        toolkit.register_tool_function(visit_page)
        toolkit.register_tool_function(answer_question)
        
        settings = BenchmarkSettings.get_effective_settings()
        memory = create_memory(settings.memory_type, "vanilla_agent_user", model=model, llm_settings=settings)

        return ReActAgent(
            name="Assistant",
            sys_prompt=PROMPTS["vanilla_agent_system_prompt"],
            model=model,
            toolkit=toolkit,
            memory=memory,
            formatter=OpenAIChatFormatter(),
            max_iters=30,
        )

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
    async def create_agent(model, toolkit: Toolkit, mcp_client: StdIOStatefulClient, verbose: bool = False):
        # DEBUG: Print all registered tools
        print_debug(f"BrowserAgent Toolkit Tools: {list(toolkit.tools.keys())}")
        
        settings = await sync_to_async(BenchmarkSettings.get_effective_settings)()
        memory = create_memory(settings.memory_type, "browser_agent_user", model=model, llm_settings=settings)

        agent = ReActAgent(
            name="BrowserAgent",
            sys_prompt=PROMPTS["browser_agent_system_prompt"],
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
