import json
import agentscope
from agentscope.agent import ReActAgent, UserAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg
from agentscope.memory import InMemoryMemory
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
from .search_utils import get_search_engine
from .models import LLMSettings
from .prompts import PROMPTS

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

class BenchmarkAgentFactory:
    @staticmethod
    def create_agent(model, verbose: bool = False, update_callback=None):
        # Create Toolkit and register tool
        toolkit = Toolkit()
        toolkit.register_tool_function(web_search_tool)
        toolkit.register_tool_function(answer_question)
        
        memory = StreamingMemory(update_callback=update_callback) if update_callback else InMemoryMemory()

        return ReActAgent(
            name="Assistant",
            sys_prompt=PROMPTS["agent_react_system"],
            model=model,
            toolkit=toolkit,
            memory=memory,
            formatter=OpenAIChatFormatter(),
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
