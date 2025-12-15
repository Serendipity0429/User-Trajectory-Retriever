import os
import sys
import asyncio
import django

# Setup Django environment
sys.path.append(os.path.join(os.getcwd(), 'Platform'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'annotation_platform.settings')
django.setup()

from benchmark.agent_browser_utils import BrowserAgentFactory, print_debug

async def run_agent_task_mock():
    print("Starting agent task (mock)...")
    agent = await BrowserAgentFactory.create_agent(model=None)
    try:
        print(f"Agent created. Has client: {hasattr(agent, 'mcp_client')}")
        # Simulate work
        await asyncio.sleep(1)
        return "Done"
    finally:
        if hasattr(agent, 'mcp_client'):
            print("Closing MCP client...")
            try:
                await agent.mcp_client.close()
                print("MCP client closed.")
            except Exception as e:
                print(f"Error closing MCP client: {e}")

if __name__ == "__main__":
    try:
        res = asyncio.run(run_agent_task_mock())
        print(f"Result: {res}")
    except Exception as e:
        print(f"Failed with error: {e}")
