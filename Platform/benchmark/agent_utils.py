import os
import json
import agentscope
from .search_utils import get_search_engine
from .models import LLMSettings
from .prompts import PROMPTS
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.memory import InMemoryMemory
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
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
        
        if not results or (isinstance(results, list) and len(results) == 0):
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
            try:
                # Pass a copy of content to avoid concurrent modification issues
                # self.content is a list, accessing it is sync
                self.update_callback(list(self.content))
            except Exception as e:
                print(f"Error in StreamingMemory callback: {e}")

class VanillaAgentFactory:
    @staticmethod
    def create_agent(model, verbose: bool = False, update_callback=None):
        # Create Toolkit and register tool
        toolkit = Toolkit()
        toolkit.register_tool_function(web_search_tool)
        toolkit.register_tool_function(answer_question)
        
        memory = StreamingMemory(update_callback=update_callback) if update_callback else InMemoryMemory()

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
        
        memory = InMemoryMemory()
        if update_callback:
            memory = StreamingMemory(update_callback=update_callback)

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
    async def init_agentscope(llm_settings: LLMSettings, skip_mcp: bool = False):
        """
        Initialize AgentScope with the project's LLM settings.
        """
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

        mcp_client = None
        if not skip_mcp:
             mcp_client = await BrowserAgentFactory.connect_mcp(toolkit)
        
        return model, toolkit, mcp_client

    @staticmethod
    async def connect_mcp(toolkit: Toolkit):
        mcp_client = None
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            mcp_root = os.path.join(current_dir, 'mcp', 'chrome-devtools-mcp')
            mcp_script = os.path.join(mcp_root, 'build', 'src', 'index.js')
            mcp_args = [
                mcp_script,
                "--isolated",
            ]
            
            if not os.path.exists(mcp_script):
                 print_debug(f"MCP server script not found at {mcp_script}. Ensure it is built.")
            else:
                mcp_client = StdIOStatefulClient(
                    name="chrome_devtools",
                    command="node",
                    args=mcp_args,
                    cwd=mcp_root
                )
                await mcp_client.connect()
                await toolkit.register_mcp_client(mcp_client)
                print_debug(f"Registered MCP tools from {mcp_client.name}")
                
        except Exception as e:
            print_debug(f"Failed to fetch/register MCP tools: {e}")
        return mcp_client   