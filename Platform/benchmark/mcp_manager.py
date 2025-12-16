import os
from agentscope.mcp import StdIOStatefulClient
from agentscope.tool import Toolkit
from .utils import print_debug

class MCPManager:
    """
    Manages the connection to the Chrome DevTools MCP server.
    Decouples transport logic from the agent factory.
    """
    def __init__(self):
        self.client = None

    async def connect(self, toolkit: Toolkit):
        """
        Connects to the MCP server and registers tools with the provided toolkit.
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Adjust path to match where this file is located relative to the mcp folder
            mcp_root = os.path.join(current_dir, 'mcp', 'chrome-devtools-mcp')
            mcp_script = os.path.join(mcp_root, 'build', 'src', 'index.js')
            mcp_args = [
                mcp_script,
                "--isolated",
            ]
            
            if not os.path.exists(mcp_script):
                 print_debug(f"MCP server script not found at {mcp_script}. Ensure it is built.")
                 return None

            self.client = StdIOStatefulClient(
                name="chrome_devtools",
                command="node",
                args=mcp_args,
                cwd=mcp_root
            )
            await self.client.connect()
            await toolkit.register_mcp_client(self.client)
            print_debug(f"Registered MCP tools from {self.client.name}")
            return self.client
                
        except Exception as e:
            print_debug(f"Failed to fetch/register MCP tools: {e}")
            return None

    async def disconnect(self):
        """
        Safely disconnects the MCP client.
        """
        if self.client:
            try:
                if hasattr(self.client, 'disconnect'):
                    await self.client.disconnect()
                elif hasattr(self.client, 'close'):
                    await self.client.close()
            except Exception as e:
                print_debug(f"Error disconnecting MCP client: {e}")
            finally:
                self.client = None
