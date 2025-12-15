import os
import sys
import asyncio
import django
from django.conf import settings

# Setup Django environment
sys.path.append(os.path.join(os.getcwd(), 'Platform'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'annotation_platform.settings')
django.setup()

from benchmark.agent_browser_utils import BrowserAgentFactory
from benchmark.models import LLMSettings
from agentscope.message import Msg

# Mock LLM settings - assumes you have env vars or we can try to use a dummy to just see the tool list, 
# but to run we need a real model or a mock that returns tool calls.
# Since I can't easily mock the OpenAI API response here without a key, 
# I will try to inspect the agent's tool definitions directly to ensure they have descriptions.

def inspect_tools():
    llm_settings = LLMSettings(
        llm_model="gpt-4o",
        llm_api_key=os.environ.get("LLM_API_KEY", "fake-key"),
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    
    # Init AgentScope
    try:
        BrowserAgentFactory.init_agentscope(llm_settings)
    except Exception as e:
        print(f"Init warning: {e}")

    # Create agent
    agent = BrowserAgentFactory.create_agent(model=None)
    
    print(f"Total Tools: {len(agent.toolkit.tools)}")
    
    # Check a specific tool's schema
    tool_name = "navigate_page"
    # AgentScope Toolkit.tools keys are strings
    if tool_name in agent.toolkit.tools:
        print(f"\nTool: {tool_name}")
        schemas = agent.toolkit.get_json_schemas()
        for s in schemas:
            if s['function']['name'] == tool_name:
                print(f"Description: {s['function'].get('description')}")
                # print(f"Parameters: {s['function'].get('parameters')}")
                break
    else:
        print(f"Tool {tool_name} not found!")

if __name__ == "__main__":
    inspect_tools()
