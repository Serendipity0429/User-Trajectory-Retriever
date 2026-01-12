import os
import re
from agentscope.mcp import StdIOStatefulClient
from agentscope.tool import Toolkit
from . import print_debug

# Default profile directory for persistent browser sessions
DEFAULT_CHROME_PROFILE_DIR = os.path.expanduser("~/.cache/chrome-devtools-mcp/agent-profile")


class ChromeDevToolsMCPManager:
    """
    Manages the connection to the Chrome DevTools MCP server.
    Decouples transport logic from the agent factory.
    """
    def __init__(self, use_isolated: bool = False, user_data_dir: str = None, proxy_server: str = None):
        """
        Initialize the MCP manager.

        Args:
            use_isolated: If True, use a temporary profile (may trigger more CAPTCHAs).
                         If False, use a persistent profile for better anti-bot evasion.
            user_data_dir: Custom user data directory. If None, uses default persistent profile.
            proxy_server: Optional proxy server URL (e.g., "http://proxy:8080" or "socks5://proxy:1080").
                         Using a residential proxy can help bypass IP-based bot detection (e.g., Google).
        """
        self.client = None
        self.use_isolated = use_isolated
        self.user_data_dir = user_data_dir or DEFAULT_CHROME_PROFILE_DIR
        self.proxy_server = proxy_server

    async def connect(self, toolkit: Toolkit):
        """
        Connects to the MCP server and registers tools with the provided toolkit.
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level from 'utils' to 'benchmark', then into 'mcp'
            mcp_root = os.path.join(current_dir, '..', 'mcp', 'chrome-devtools-mcp')
            mcp_script = os.path.join(mcp_root, 'build', 'src', 'index.js')

            # Build MCP args with anti-bot detection measures
            # See: https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/430
            mcp_args = [
                mcp_script,
                # Disable Puppeteer's default automation flags that trigger bot detection
                "--ignore-default-chrome-arg=--enable-automation",
                "--ignore-default-chrome-arg=--disable-component-extensions-with-background-pages",
                # Critical: This flag sets navigator.webdriver to false (key anti-detection measure)
                "--chrome-arg=--disable-blink-features=AutomationControlled",
            ]

            # Use persistent profile for better anti-bot evasion (preserves cookies, history)
            if self.use_isolated:
                mcp_args.append("--isolated")
            else:
                # Ensure profile directory exists
                os.makedirs(self.user_data_dir, exist_ok=True)
                mcp_args.append(f"--user-data-dir={self.user_data_dir}")
                print_debug(f"Using persistent Chrome profile: {self.user_data_dir}")

            # Add proxy server if configured (helps bypass IP-based bot detection like Google's)
            if self.proxy_server:
                mcp_args.append(f"--proxy-server={self.proxy_server}")
                print_debug(f"Using proxy server: {self.proxy_server}")
            
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

            # Clean up pages from previous sessions (persistent profile may have old tabs)
            await self._cleanup_pages()

            return self.client
                
        except Exception as e:
            print_debug(f"Failed to fetch/register MCP tools: {e}")
            return None

    async def _cleanup_pages(self):
        """
        Close all pages from previous sessions and leave only a blank page.
        This ensures a clean state when using persistent profiles.
        """
        if not self.client:
            return

        try:
            # Get tool functions
            list_pages_fn = await self.client.get_callable_function('list_pages')
            close_page_fn = await self.client.get_callable_function('close_page')
            navigate_fn = await self.client.get_callable_function('navigate_page')
            select_page_fn = await self.client.get_callable_function('select_page')

            # List all current pages
            pages_result = await list_pages_fn()
            pages_str = str(pages_result)

            # Parse page IDs from the result (format: "1: url [selected]" or "2: url")
            page_ids = re.findall(r'^(\d+):', pages_str, re.MULTILINE)

            if not page_ids:
                print_debug("No pages found")
                return

            print_debug(f"Found {len(page_ids)} page(s), cleaning up...")

            # Keep only the first page, close all others
            if len(page_ids) > 1:
                # Select the first page
                await select_page_fn(pageId=int(page_ids[0]))

                # Close all other pages
                for page_id in page_ids[1:]:
                    try:
                        await close_page_fn(pageId=int(page_id))
                        print_debug(f"Closed page {page_id}")
                    except Exception as e:
                        print_debug(f"Failed to close page {page_id}: {e}")

            # Navigate the remaining page to blank
            await navigate_fn(url="about:blank")
            print_debug("Cleanup complete: single blank page ready")

        except Exception as e:
            print_debug(f"Error during page cleanup: {e}")
            # Don't fail the connection if cleanup fails

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
