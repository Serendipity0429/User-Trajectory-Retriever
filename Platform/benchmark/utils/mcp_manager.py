import os
from agentscope.mcp import StdIOStatefulClient
from agentscope.tool import Toolkit
from . import print_debug

class ChromeDevToolsMCPManager:
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
            # Go up one level from 'utils' to 'benchmark', then into 'mcp'
            mcp_root = os.path.join(current_dir, '..', 'mcp', 'chrome-devtools-mcp')
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
        Safely disconnects the MCP client and terminates the Chrome browser.
        """
        if self.client:
            try:
                # Always try to close - don't rely on is_connected attribute
                # which may not be set correctly on StdIOStatefulClient
                await self.client.close()
                print_debug("MCP client closed successfully")
            except Exception as e:
                print_debug(f"Error disconnecting MCP client: {e}")
                # Try to forcefully terminate the subprocess if close() failed
                try:
                    if hasattr(self.client, '_process') and self.client._process:
                        self.client._process.terminate()
                        print_debug("Forcefully terminated MCP subprocess")
                except Exception as e2:
                    print_debug(f"Error terminating MCP process: {e2}")
                # Also try closing the stack if it exists
                try:
                    if hasattr(self.client, 'stack') and self.client.stack:
                        await self.client.stack.aclose()
                        print_debug("Closed MCP stack")
                except Exception as e3:
                    print_debug(f"Error closing MCP stack: {e3}")
            finally:
                self.client = None
