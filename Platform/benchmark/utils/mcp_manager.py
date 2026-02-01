import os
import re
import signal
import subprocess
from agentscope.mcp import StdIOStatefulClient
from agentscope.tool import Toolkit
from . import print_debug

DEFAULT_CHROME_PROFILE_DIR = os.path.expanduser("~/.cache/chrome-devtools-mcp/agent-profile")


def _kill_process_tree(pid, timeout=2):
    """Kill a process and all its children using SIGTERM then SIGKILL."""
    try:
        import psutil
        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            for p in children + [proc]:
                try:
                    p.terminate()
                except psutil.NoSuchProcess:
                    pass
            gone, alive = psutil.wait_procs(children + [proc], timeout=timeout)
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
        except psutil.NoSuchProcess:
            pass
    except ImportError:
        # Fallback without psutil - use process group kill
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


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
        self._node_pid = None  # Track the node process PID for cleanup

    async def connect(self, toolkit: Toolkit):
        """
        Connects to the MCP server and registers tools with the provided toolkit.
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level from 'utils' to 'benchmark', then into 'mcp'
            mcp_root = os.path.join(current_dir, '..', 'mcp', 'chrome-devtools-mcp')
            # Use installed npm package
            mcp_script = os.path.join(mcp_root, 'node_modules', 'chrome-devtools-mcp', 'build', 'src', 'index.js')

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

            # Try to capture the node process PID for cleanup
            # The MCP library stores the process in client.client which is the stdio_client context
            self._node_pid = self._extract_process_pid()

            await toolkit.register_mcp_client(self.client)

            print_debug(f"Registered MCP tools from {self.client.name} (node PID: {self._node_pid})")

            # Clean up pages from previous sessions (persistent profile may have old tabs)
            await self._cleanup_pages()

            return self.client
                
        except Exception as e:
            print_debug(f"Failed to fetch/register MCP tools: {e}")
            return None

    def _extract_process_pid(self):
        """Try to extract node process PID from MCP client internals."""
        if not self.client:
            return None
        try:
            # Try various paths to find the process PID
            if hasattr(self.client, 'client') and hasattr(self.client.client, '_process'):
                proc = self.client.client._process
                if hasattr(proc, 'pid'):
                    return proc.pid
            return None
        except Exception:
            return None

    def _find_chrome_processes_by_profile(self):
        """Find Chrome processes using our profile directory."""
        try:
            import psutil
            pids = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'chrom' in proc.info['name'].lower():
                        cmdline_str = ' '.join(proc.info.get('cmdline') or [])
                        if self.user_data_dir in cmdline_str:
                            pids.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return pids
        except ImportError:
            # Fallback using pgrep
            try:
                result = subprocess.run(
                    ['pgrep', '-f', self.user_data_dir],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return [int(p) for p in result.stdout.strip().split('\n') if p]
            except Exception:
                pass
            return []

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
        Disconnect MCP client. Handles cancel scope errors from async task mismatch
        by falling back to forceful process termination.
        """
        if not self.client:
            return

        node_pid = self._node_pid

        # Try normal async close (may warn about cancel scope but won't raise)
        try:
            if self.client.is_connected:
                await self.client.close()
                print_debug("MCP client closed")
        except RuntimeError as e:
            if "not connected" not in str(e).lower():
                print_debug(f"MCP close error: {e}")
        except Exception as e:
            print_debug(f"MCP close error: {e}")

        # Force cleanup - handles incomplete async cleanup due to cancel scope issues
        await self._ensure_processes_terminated(node_pid)

        self.client = None
        self._node_pid = None

    async def _ensure_processes_terminated(self, node_pid):
        """Force terminate any remaining node/Chrome processes."""
        # Kill node process if still running
        if node_pid:
            try:
                os.kill(node_pid, 0)
                print_debug(f"Forcing node process {node_pid} termination")
                _kill_process_tree(node_pid)
            except ProcessLookupError:
                pass

        # Kill orphan Chrome processes using our profile
        chrome_pids = self._find_chrome_processes_by_profile()
        for pid in chrome_pids:
            print_debug(f"Killing orphan Chrome process {pid}")
            _kill_process_tree(pid)
