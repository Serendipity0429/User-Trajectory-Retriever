#!/usr/bin/env python3
from abc import ABC, abstractmethod
import subprocess
import json
import os
import sys
import threading
import logging

logger = logging.getLogger(__name__)

class WebSearch(ABC):
    @abstractmethod
    def search(self, query: str) -> list:
        pass

class MCPClient:
    """
    A basic Python client to communicate with an MCP server over stdio.
    This client implements the necessary parts of the protocol (based on LSP)
    to send and receive JSON-RPC messages.
    Copied from test_search_mcp.py
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
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=self._cwd,
        )
        logger.info(f"Started MCP server with PID: {self._process.pid}")

        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_stderr(self):
        """Continuously reads from the server's stderr stream."""
        if not self._process or not self._process.stderr:
            return
        for line in iter(self._process.stderr.readline, b''):
            logger.debug(f"[MCP-SERVER-STDERR] {line.decode('utf-8').strip()}")

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
            
            logger.debug(f"[PY-CLIENT-SEND] {body_str}")

            self._process.stdin.write(full_message)
            self._process.stdin.flush()

        return request["id"]

    def _read_response(self):
        """Reads and decodes a single JSON-RPC response from stdout."""
        if not self._process or not self._process.stdout:
            raise ConnectionError("Server process is not running or stdout is closed.")

        while True:
            line = self._process.stdout.readline()
            if not line:
                return None
            
            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue

            logger.debug(f"[PY-CLIENT-RECV] {line_str}")
            
            try:
                return json.loads(line_str)
            except json.JSONDecodeError:
                # logger.info(f"Ignored non-JSON output from server: {line_str}")
                continue

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
                    pass
            if self._process.poll() is None:
                logger.info(f"Terminating MCP server with PID: {self._process.pid}")
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Server {self._process.pid} did not terminate, killing.")
                    self._process.kill()
            self._process = None

class MCPSearch(WebSearch):
    _instance = None
    _client = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MCPSearch, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        server_dir = os.path.join(project_root, 'Platform/benchmark/mcp/web-search-mcp')
        script_path = os.path.join(server_dir, 'dist/index.js')

        if not os.path.exists(script_path):
            logger.error(f"Could not find MCP script at {script_path}")
            # Here we should probably handle this error more gracefully
            # For now, just log and the search will fail.
            self._client = None
            self._initialized = True
            return

        command = ["node", script_path]
        self._client = MCPClient(command, cwd=server_dir)
        self._client.start()
        
        # We need to make sure to close the client when Django shuts down.
        # atexit might be a good option here.
        import atexit
        atexit.register(self.close)

        self._initialized = True

    def _parse_mcp_text_response(self, text: str) -> list:
        import re
        results = []
        
        # Split by the separator used in index.ts
        chunks = text.split('\n---\n\n')
        
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
                
            # Skip the header "Search completed for..." if it's in the first chunk
            header_match = re.match(r"Search completed for .*? results:\n\n(?:^\*\*Status:\*\*.*?\n\n)?", chunk, re.DOTALL | re.MULTILINE)
            if header_match:
                chunk = chunk[header_match.end():]
            
            if not chunk.strip():
                continue

            result = {}
            
            # Extract Title: **1. Title**
            title_match = re.search(r'^\*\*\d+\.\s+(.*?)\*\*$', chunk, re.MULTILINE)
            if title_match:
                result['title'] = title_match.group(1).strip()
            
            # Extract URL
            url_match = re.search(r'^URL:\s+(.*?)$', chunk, re.MULTILINE)
            if url_match:
                result['url'] = url_match.group(1).strip()
                
            # Extract Description
            desc_match = re.search(r'^Description:\s+(.*?)$', chunk, re.MULTILINE)
            if desc_match:
                result['snippet'] = desc_match.group(1).strip()
            else:
                result['snippet'] = ""
                
            # Extract Content
            content_match = re.search(r'^\*\*(?:Full Content|Content Preview):\*\*\n(.*?)$', chunk, re.DOTALL | re.MULTILINE)
            if content_match:
                result['content'] = content_match.group(1).strip()
            else:
                result['content'] = ""

            # Fallback: If description is missing or "No description available", use content as snippet
            if (not result.get('snippet') or result['snippet'] == "No description available") and result.get('content'):
                 # Take first 300 chars of content as snippet
                 result['snippet'] = result['content']

            if 'title' in result:
                results.append(result)
                
        return results

    def search(self, query: str) -> list:
        if not self._client:
            return [{"error": "MCP client not initialized."}]

        search_args = {
            "query": query,
            "limit": 5,
            "includeContent": True
        }

        try:
            search_result = self._client.call_tool("full-web-search", search_args)
            print(search_result)
        except Exception as e:
            logger.error(f"Error calling MCP tool: {e}")
            return [{"error": f"Error calling MCP tool: {str(e)}"}]

        if search_result and "content" in search_result and len(search_result['content']) > 0:
            text_content = search_result['content'][0]['text']
            return self._parse_mcp_text_response(text_content)
        else:
            return [{"error": "Did not receive a valid search result."}]
    
    def close(self):
        if self._client:
            self._client.close()
            self._client = None

# For easy swapping of search implementations
def get_search_engine() -> WebSearch:
    return MCPSearch()
