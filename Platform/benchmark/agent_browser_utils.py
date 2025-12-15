import json
import agentscope
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg
from agentscope.memory import InMemoryMemory
from agentscope.formatter import OpenAIChatFormatter
from agentscope.model import OpenAIChatModel
from .models import LLMSettings
from .browser_utils import BrowserClientManager
from .utils import print_debug
from asgiref.sync import sync_to_async
from .agent_utils import StreamingMemory, answer_question # Direct import

async def navigate_to_url(url: str):
    """
    Navigates the browser to the specified URL.
    Args:
        url (str): The URL to navigate to.
    Returns:
        ToolResponse: Information about the navigation, including the new URL.
    """
    try:
        client = BrowserClientManager.get_client()
        result = await sync_to_async(client.call_mcp_tool)("browser/navigate", {"url": url})
        return ToolResponse(content=json.dumps(result))
    except Exception as e:
        return ToolResponse(content=f"Error navigating to {url}: {str(e)}")

async def get_dom_snapshot():
    """
    Retrieves a snapshot of the current page's Document Object Model (DOM).
    This provides an accessibility tree-like representation of the page content.
    Returns:
        ToolResponse: A JSON representation of the DOM snapshot.
    """
    try:
        client = BrowserClientManager.get_client()
        result = await sync_to_async(client.call_mcp_tool)("dom/snapshot", {})
        
        # The snapshot can be huge. Let's extract relevant parts for the agent.
        # This part might need refinement based on actual snapshot structure.
        if result and 'snapshot' in result and 'html' in result['snapshot']:
            # For now, just return a simplified version or extract key info
            # A full HTML might be too much for the LLM context
            simplified_snapshot = {
                "title": result['snapshot'].get('title'),
                "url": result['snapshot'].get('url'),
                "body_content_length": len(result['snapshot'].get('html', '')),
                # Can add more selective information here
            }
            # Or, if we want some text content:
            # text_content = result['snapshot'].get('innerText', result['snapshot'].get('textContent', ''))[:1000] # Truncate
            # simplified_snapshot['text_content_preview'] = text_content

            return ToolResponse(content=json.dumps(simplified_snapshot))
        
        return ToolResponse(content=json.dumps(result)) # Fallback if snapshot structure differs
    except Exception as e:
        return ToolResponse(content=f"Error getting DOM snapshot: {str(e)}")

async def click_element(selector: str):
    """
    Clicks on an element identified by a CSS selector.
    Args:
        selector (str): The CSS selector of the element to click.
    Returns:
        ToolResponse: Confirmation of click or error message.
    """
    try:
        client = BrowserClientManager.get_client()
        result = await sync_to_async(client.call_mcp_tool)("input/click", {"selector": selector})
        return ToolResponse(content=json.dumps(result))
    except Exception as e:
        return ToolResponse(content=f"Error clicking element '{selector}': {str(e)}")

async def type_text(selector: str, text: str):
    """
    Types text into an input field identified by a CSS selector.
    Args:
        selector (str): The CSS selector of the input field.
        text (str): The text to type.
    Returns:
        ToolResponse: Confirmation of typing or error message.
    """
    try:
        client = BrowserClientManager.get_client()
        result = await sync_to_async(client.call_mcp_tool)("input/type", {"selector": selector, "text": text})
        return ToolResponse(content=json.dumps(result))
    except Exception as e:
        return ToolResponse(content=f"Error typing into '{selector}': {str(e)}")

async def scroll_page(direction: str = "down", amount: int = 500):
    """
    Scrolls the page up or down.
    Args:
        direction (str): 'up' or 'down'. Defaults to 'down'.
        amount (int): Number of pixels to scroll. Defaults to 500.
    Returns:
        ToolResponse: Confirmation of scroll or error message.
    """
    try:
        client = BrowserClientManager.get_client()
        # MCP server might have a unified scroll tool or separate ones
        # Assuming a 'page/scroll' or similar tool
        result = await sync_to_async(client.call_mcp_tool)("page/scroll", {"direction": direction, "amount": amount})
        return ToolResponse(content=json.dumps(result))
    except Exception as e:
        return ToolResponse(content=f"Error scrolling page: {str(e)}")

# Placeholder for a browser-specific system prompt
BROWSER_AGENT_SYSTEM_PROMPT = """You are an intelligent browser automation agent tasked with completing tasks by interacting with web pages.
You have access to the following tools:
1. `navigate_to_url(url: str)`: Navigates the browser to a specified URL.
2. `get_dom_snapshot()`: Retrieves a snapshot of the current page's DOM for analysis.
3. `click_element(selector: str)`: Clicks on an element identified by a CSS selector.
4. `type_text(selector: str, text: str)`: Types text into an input field.
5. `scroll_page(direction: str, amount: int)`: Scrolls the page up or down.
6. `answer_question(answer: str)`: Submit the final answer after completing the task.

**Instructions:**
1.  **Understand the Goal:** Analyze the user's request to understand what needs to be achieved on the web page.
2.  **Explore the Page:** Use `navigate_to_url` to go to the starting page. Then use `get_dom_snapshot` to understand the page structure and identify interactive elements. Scroll if necessary.
3.  **Interact:** Use `click_element` and `type_text` to interact with the page to fulfill the task.
4.  **Formulate Answer:** Once the task is complete and you have gathered the required information, use `answer_question` to submit the final answer.

**Format:**
Always output your thought process as "Thought: [Your reasoning]" before taking any action.

**WARNING:**
You MUST use the `answer_question` tool to submit your final answer.
Do NOT output the answer directly as text.
If you find the answer or complete the task, your next action MUST be `answer_question`.
"""

class BrowserAgentFactory:
    @staticmethod
    def create_agent(model, verbose: bool = False, update_callback=None):
        toolkit = Toolkit()
        toolkit.register_tool_function(navigate_to_url)
        toolkit.register_tool_function(get_dom_snapshot)
        toolkit.register_tool_function(click_element)
        toolkit.register_tool_function(type_text)
        toolkit.register_tool_function(scroll_page)
        toolkit.register_tool_function(answer_question) # Reuse from agent_utils or define a new one if needed

        memory = InMemoryMemory() # Can use StreamingMemory if real-time trace is desired
        if update_callback:
            from .agent_utils import StreamingMemory # Reuse existing StreamingMemory
            memory = StreamingMemory(update_callback=update_callback)

        return ReActAgent(
            name="BrowserAgent",
            sys_prompt=BROWSER_AGENT_SYSTEM_PROMPT,
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
