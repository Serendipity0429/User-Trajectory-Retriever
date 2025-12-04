#!/usr/bin/env python3
import subprocess
import json
import os
import sys
import threading

class MCPClient:
    """
    A basic Python client to communicate with an MCP server over stdio.
    This client implements the necessary parts of the protocol (based on LSP)
    to send and receive JSON-RPC messages.
    """
    def __init__(self, command, cwd):
        self._command = command
        self._cwd = cwd
        self._process = None
        self._next_id = 1
        self._lock = threading.Lock()
        self._stderr_thread = None

    def start(self):
        """Starts the MCP server as a subprocess."""
        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Isolate stderr
            bufsize=0,
            cwd=self._cwd,
        )
        print(f"Started MCP server with PID: {self._process.pid}")

        # Start a thread to drain and print stderr to prevent blocking
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_stderr(self):
        """Continuously reads from the server's stderr stream."""
        if not self._process or not self._process.stderr:
            return
        for line in iter(self._process.stderr.readline, b''):
            print(f"[MCP-SERVER-STDERR] {line.decode('utf-8').strip()}", file=sys.stderr)

    def _send_request(self, method, params=None):
        """Builds and sends a JSON-RPC request."""
        if not self._process or not self._process.stdin:
            raise ConnectionError("Server process is not running or stdin is closed.")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params:
            request["params"] = params

        with self._lock:
            self._next_id += 1
            body_str = json.dumps(request)
            full_message = (body_str + '\n').encode('utf-8')
            
            print(f"[PY-CLIENT-SEND] {body_str}", file=sys.stderr)

            self._process.stdin.write(full_message)
            self._process.stdin.flush()

        return request["id"]

    def _read_response(self):
        """Reads and decodes a single JSON-RPC response from stdout."""
        if not self._process or not self._process.stdout:
            raise ConnectionError("Server process is not running or stdout is closed.")

        line = self._process.stdout.readline()
        if not line:
            return None
        
        line_str = line.decode('utf-8').strip()
        print(f"[PY-CLIENT-RECV] {line_str}", file=sys.stderr)
        return json.loads(line_str)

    def list_tools(self):
        """Sends a tools/list request and returns the result."""
        self._send_request("tools/list")
        response = self._read_response()
        return response.get("result", {})

    def call_tool(self, name, arguments):
        """Sends a tools/call request and returns the result."""
        params = {
            "name": name,
            "arguments": arguments,
        }
        self._send_request("tools/call", params)
        response = self._read_response()
        return response.get("result", {})

    def close(self):
        """Closes the MCP server process."""
        if self._process:
            if self._process.stdin:
                try:
                    self._process.stdin.close()
                except (IOError, BrokenPipeError):
                    pass # Ignore errors on close
            if self._process.poll() is None:
                print(f"Terminating MCP server with PID: {self._process.pid}")
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"Server {self._process.pid} did not terminate, killing.", file=sys.stderr)
                    self._process.kill()
            self._process = None

def main():
    """
    Main function to run the test.
    It starts the web-search MCP server, calls the search tool,
    and prints the results.
    """
    # Get the project root directory (assuming the script is in the root)
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Define paths relative to the project root
    server_dir = os.path.join(project_root, 'tempFiles/web-search')
    script_path = os.path.join(server_dir, 'build/index.js')

    if not os.path.exists(script_path):
        print(f"Error: Could not find MCP script at {script_path}", file=sys.stderr)
        print("Please ensure you have run 'npm install' and 'npm run build' in the 'tempFiles/web-search' directory.", file=sys.stderr)
        sys.exit(1)

    command = ["node", script_path]
    # The working directory is important for node to find node_modules
    client = MCPClient(command, cwd=server_dir)

    try:
        client.start()

        # 1. List the available tools
        print("\n--> Listing available tools...")
        tools_response = client.list_tools()
        if tools_response and "tools" in tools_response:
            print(json.dumps(tools_response, indent=2))
        else:
            print("Could not get a valid tool list.")
            # return # Keep going to see if we get more error info

        # 2. Call the 'search' tool
        print("\n--> Performing a web search for 'python async programming'...")
        search_args = {
            "query": "In what episode does Goku give up against Cell?",
            # "limit": 10
        }
        search_result = client.call_tool("search", search_args)

        if search_result and "content" in search_result:
            print("\n<-- Received search results:")
            # The tool returns content as a stringified JSON array
            try:
                results_list = json.loads(search_result['content'][0]['text'])
                print(json.dumps(results_list, indent=2))
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                print(f"Error parsing search result content: {e}", file=sys.stderr)
                print("Raw content:", search_result.get('content'), file=sys.stderr)
        else:
            print("\n<-- Did not receive a valid search result.")

    except Exception as e:
        print(f"\nAn error occurred in the Python client: {e}", file=sys.stderr)
    finally:
        print("\n--> Shutting down client and server.")
        client.close()

if __name__ == "__main__":
    main()
