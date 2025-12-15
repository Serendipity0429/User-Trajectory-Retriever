import os
import sys
import asyncio
import django

# Setup Django environment
sys.path.append(os.path.join(os.getcwd(), 'Platform'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'annotation_platform.settings')
django.setup()

from benchmark.agent_browser_utils import BrowserAgentFactory
from agentscope.mcp import StdIOStatefulClient

async def check_client_methods():
    current_dir = os.path.dirname(os.path.abspath('Platform/benchmark/agent_browser_utils.py'))
    mcp_root = os.path.join(current_dir, 'mcp', 'chrome-devtools-mcp')
    mcp_script = os.path.join(mcp_root, 'build', 'src', 'index.js')
    
    client = StdIOStatefulClient(
        name="chrome_devtools",
        command="node",
        args=[mcp_script],
        cwd=mcp_root
    )
    
    print("Client methods/attrs:")
    print(dir(client))
    
    # Try to see if it's a context manager
    if hasattr(client, '__aenter__'):
        print("Is async context manager")

if __name__ == "__main__":
    asyncio.run(check_client_methods())
