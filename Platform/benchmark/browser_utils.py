import subprocess
import json
import os
import threading
import atexit
import time
from .utils import print_debug

class MCPBrowserClient:
    """
    A Python client to communicate with the chrome-devtools-mcp server over stdio.
    This client implements the necessary parts of the protocol (based on LSP)
    to send and receive JSON-RPC messages for browser control.
    """
    def __init__(self, command, cwd):
        self._command = command
        self._cwd = cwd
        self._process = None
        self._next_id = 1
        self._lock = threading.RLock()
        self._stderr_thread = None
        self._stdout_thread = None
        self._response_queue = {}
        self._notification_callback = None # For handling notifications

    def start(self):
        """Starts the MCP server as a subprocess."""
        print_debug(f"Starting MCP browser server with command: {' '.join(self._command)} in cwd: {self._cwd}")
        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0, # Unbuffered
            cwd=self._cwd,
            text=True # Decode stdin/stdout/stderr as text
        )
        print_debug(f"Started MCP browser server with PID: {self._process.pid}")

        # Start threads to read stdout and stderr
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

        # Register cleanup on exit
        atexit.register(self.close)
        
        # Wait a bit for the server to spin up
        time.sleep(2) # Adjust as needed

    def _read_stderr(self):
        """Continuously reads from the server's stderr stream."""
        if not self._process or not self._process.stderr:
            return
        for line in iter(self._process.stderr.readline, ''):
            if line:
                print_debug(f"[MCP-BROWSER-SERVER-STDERR] {line.strip()}")

    def _read_stdout(self):
        """Continuously reads from the server's stdout stream and processes messages."""
        if not self._process or not self._process.stdout:
            return
        while True:
            line = self._process.stdout.readline()
            if not line:
                break # EOF, process exited
            
            line_str = line.strip()
            if not line_str:
                continue

            print_debug(f"[MCP-BROWSER-SERVER-STDOUT] {line_str}")
            
            try:
                message = json.loads(line_str)
                with self._lock:
                    if 'id' in message:
                        # This is a response to a request
                        self._response_queue[message['id']] = message
                    elif 'method' in message:
                        # This is a notification/event from the server
                        if self._notification_callback:
                            self._notification_callback(message)
            except json.JSONDecodeError:
                print_debug(f"[MCP-BROWSER-SERVER-PARSE-ERROR] {line_str}")
                continue
            except Exception as e:
                print_debug(f"[MCP-BROWSER-SERVER-PROCESSING-ERROR] {e} for message: {line_str}")

    def _send_request(self, method, params=None):
        """Builds and sends a JSON-RPC request."""
        if not self._process or not self._process.stdin:
            raise ConnectionError("Server process is not running or stdin is closed.")

        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }
            if params:
                request["params"] = params

            body_str = json.dumps(request)
            # MCP servers typically expect messages delimited by newlines
            full_message = (body_str + '\n')
            
            print_debug(f"[PY-BROWSER-CLIENT-SEND] {body_str}")
            self._process.stdin.write(full_message)
            self._process.stdin.flush()
        return request_id

    def _wait_for_response(self, request_id, timeout=10):
        """Waits for a response to a specific request ID."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if request_id in self._response_queue:
                    return self._response_queue.pop(request_id)
            time.sleep(0.05) # Poll every 50ms
        raise TimeoutError(f"Timed out waiting for response to request {request_id}")

    def call_mcp_tool(self, name: str, arguments: dict, timeout=30):
        """
        Calls a specific tool on the MCP server and returns its result.
        """
        params = {
            "name": name,
            "arguments": arguments,
        }
        request_id = self._send_request("tools/call", params)
        response = self._wait_for_response(request_id, timeout)
        
        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            raise Exception(f"MCP Tool Error: {response['error']}")
        else:
            raise Exception(f"Unexpected MCP response: {response}")

    def close(self):
        """Closes the MCP server process."""
        if self._process:
            if self._process.stdin:
                try:
                    self._process.stdin.close()
                except (IOError, BrokenPipeError):
                    pass
            if self._process.poll() is None:
                print_debug(f"Terminating MCP browser server with PID: {self._process.pid}")
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print_debug(f"Server {self._process.pid} did not terminate, killing.")
                    self._process.kill()
            self._process = None

# Singleton instance management for the browser client
class BrowserClientManager:
    _client = None
    _client_lock = threading.Lock()

    @classmethod
    def get_client(cls):
        with cls._client_lock:
            if cls._client is None:
                # Dynamically determine the path
                current_dir = os.path.dirname(os.path.abspath(__file__))
                server_dir = os.path.join(current_dir, 'mcp', 'chrome-devtools-mcp')
                script_path = os.path.join(server_dir, 'dist', 'index.js') # Assuming main entry is index.js

                if not os.path.exists(script_path):
                    print_debug(f"MCP browser script not found at {script_path}")
                    raise FileNotFoundError(f"MCP browser script not found at {script_path}. Please ensure 'chrome-devtools-mcp' is cloned and built.")

                # The chrome-devtools-mcp typically needs to be run with --chrome-path and --user-data-dir
                # For simplicity, we might start without them and let it use default Chrome installation
                # and create temp profile. Or add configuration later.
                command = ["node", script_path]
                
                # We need to ensure we pass the correct port if the server doesn't autodetect.
                # The chrome-devtools-mcp defaults to port 9222 for Chrome, or can use --port.
                # For now, let's assume default works or it's configured in its own config.
                
                cls._client = MCPBrowserClient(command, cwd=server_dir)
                cls._client.start()
            return cls._client

    @classmethod
    def close_client(cls):
        with cls._client_lock:
            if cls._client:
                cls._client.close()
                cls._client = None
                print_debug("MCP browser client closed.")

# Register atexit to ensure client is closed when application exits
atexit.register(BrowserClientManager.close_client)

# Example usage (for testing purposes, not part of actual pipeline)
async def test_browser_client():
    try:
        client = BrowserClientManager.get_client()
        
        # Example tool call: You would need to know the actual tools exposed by chrome-devtools-mcp
        # This is a placeholder; actual tool names will be discovered or read from docs.
        # e.g., 'browser/navigate', 'dom/snapshot', 'input/type', 'input/click'
        
        # Test navigate tool (assuming it exists and takes a 'url' argument)
        print_debug("Navigating to example.com...")
        navigate_result = client.call_mcp_tool("browser/navigate", {"url": "https://example.com"})
        print_debug(f"Navigate Result: {navigate_result}")

        # Test taking a DOM snapshot
        print_debug("Taking DOM snapshot...")
        snapshot_result = client.call_mcp_tool("dom/snapshot", {})
        print_debug(f"DOM Snapshot: {snapshot_result['snapshot']['title']}")

    except Exception as e:
        print_debug(f"Test failed: {e}")
    finally:
        BrowserClientManager.close_client()
        
# To run the test:
# if __name__ == "__main__":
#    import asyncio
#    asyncio.run(test_browser_client())
