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
        # engine.search might be sync or async. 
        # If engine.search is sync, we need to wrap it too? 
        # Usually search engines (Serper) do network I/O.
        # But get_search_engine() just returns the instance.
        # Check search_utils.py to be sure.
        # Assuming we need to run search in thread if it's sync.
        
        results = await sync_to_async(engine.search)(query)
        # Return JSON for structured parsing by frontend and LLM
        return ToolResponse(content=json.dumps(results))
    except Exception as e:
        return ToolResponse(content=f"Error: {str(e)}")

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
            sys_prompt="""You are an intelligent research agent tasked with answering user questions accurately.
You have access to the following tools:
1. `web_search_tool(query: str)`: Search the internet for information.
2. `answer_question(answer: str)`: Submit the final answer.

**Instructions:**
1.  **Analyze the Request:** Understand the user's question.
2.  **Information Retrieval:** Use `web_search_tool` to gather necessary information. You can use it multiple times if needed.
3.  **Reasoning:** Think step-by-step about the information you have. Explain your logic.
4.  **Refinement:** If the user provides feedback (e.g., "Incorrect"), analyze WHY it might be wrong. Did you miss a detail? Was the source outdated? Search again with a refined query.
5.  **Final Answer:** When you are confident, use `answer_question` to submit the answer. The answer should be concise and directly address the question.

**Format:**
Always output your thought process as "Thought: [Your reasoning]" before taking any action.

**WARNING:**
You MUST use the `answer_question` tool to submit your final answer.
Do NOT output the answer directly as text.
If you find the answer, your next action MUST be `answer_question`.

For example:
Question: What is the capital of France?
Correct Answer: (call answer_question tool with the answer) Paris

Incorrect Answers:
- \"The capital of France is Paris.\" (contains extra words)
- \"Paris is the capital of France.\" (contains extra words)
- \"Paris.\" (contains a period)
""",
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
