import json
import os
import asyncio
import agentscope
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg
from agentscope.memory import InMemoryMemory
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
from agentscope.mcp import StdIOStatefulClient
from .models import LLMSettings
from .utils import print_debug
from asgiref.sync import sync_to_async, async_to_sync

# Define answer_question locally to prevent implicit import of other tools
def answer_question(answer: str):
    """
    Finalize the task by submitting the answer to the user.
    You MUST use this tool to provide the final response after you have gathered sufficient information.
    Do not just output text; call this tool with your answer.
    
    Args:
        answer (str): The comprehensive answer to the user's question, citing sources if available.
    """
    return ToolResponse(content="Answer submitted successfully.")

# Updated System Prompt
BROWSER_AGENT_SYSTEM_PROMPT = """You are an intelligent browser automation agent.
You have access to a set of tools to interact with the browser. 
Your goal is to complete the user's task using these tools.

**CRITICAL INSTRUCTION:**
You MUST use the provided browser tools (e.g., `navigate_page`, `google_search` if available, `click`, `read_page`) to gather information. 
Do NOT rely on your internal knowledge. You must VERIFY all information by browsing the web.
Even if you think you know the answer, you must prove it by visiting a webpage.

**General Instructions:**
1.  **Explore:** Use navigation and inspection tools (like `dom_snapshot` or similar) to understand the page.
2.  **Interact:** Use input tools (click, type, etc.) to manipulate the page.
3.  **Answer:** Once you have completed the task and verified the info, you MUST use the `answer_question` tool to submit your final answer.

**Tool Usage:**
- Always output your thought process "Thought: ..." before using a tool.
- The available tools are automatically provided to you. Check them for specific capabilities and arguments.

**WARNING:**
- You MUST use `answer_question(answer="...")` to finish.
- Do NOT return the answer as plain text.
"""

class BrowserAgentFactory:
    @staticmethod
    async def create_agent(model, verbose: bool = False, update_callback=None):
        toolkit = Toolkit()
        
        # 1. Fetch available tools from MCP
        try:
            # Construct path to the local MCP server script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            mcp_root = os.path.join(current_dir, 'mcp', 'chrome-devtools-mcp')
            # build/src/index.js is the compiled entry point
            mcp_script = os.path.join(mcp_root, 'build', 'src', 'index.js')
            
            if not os.path.exists(mcp_script):
                 print_debug(f"MCP server script not found at {mcp_script}. Ensure it is built.")
            else:
                # Initialize StdIO Client
                client = StdIOStatefulClient(
                    name="chrome_devtools",
                    command="node",
                    args=[mcp_script],
                    cwd=mcp_root # Set CWD to the repo root
                )
                
                await client.connect()
                await toolkit.register_mcp_client(client)
                print_debug(f"Registered MCP tools from {client.name}")
                
        except Exception as e:
            print_debug(f"Failed to fetch/register MCP tools: {e}")
        
        # 2. Register mandatory local tools
        toolkit.register_tool_function(answer_question)

        # DEBUG: Print all registered tools
        print_debug(f"BrowserAgent Toolkit Tools: {list(toolkit.tools.keys())}")
        
        memory = InMemoryMemory()
        if update_callback:
            from .agent_utils import StreamingMemory
            memory = StreamingMemory(update_callback=update_callback)

        agent = ReActAgent(
            name="BrowserAgent",
            sys_prompt=BROWSER_AGENT_SYSTEM_PROMPT,
            model=model,
            toolkit=toolkit,
            memory=memory,
            formatter=OpenAIChatFormatter(),
        )
        
        # Attach client to agent for cleanup
        if 'client' in locals():
            agent.mcp_client = client
            
        return agent

    @staticmethod
    def init_agentscope(llm_settings: LLMSettings):
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
        return model