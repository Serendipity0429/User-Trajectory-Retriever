#!/usr/bin/env python3
from abc import ABC, abstractmethod
import subprocess
import json
import os
import threading
import requests
from bs4 import BeautifulSoup
import re
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import print_debug

class WebSearch(ABC):
    @abstractmethod
    def search(self, query: str) -> list:
        pass

    @abstractmethod
    def format_results(self, results: list) -> str:
        """
        Formats the search results into a string suitable for LLM consumption.
        """
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
        self._lock = threading.RLock()
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
        print_debug(f"Started MCP server with PID: {self._process.pid}")

        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_stderr(self):
        """Continuously reads from the server's stderr stream."""
        if not self._process or not self._process.stderr:
            return
        for line in iter(self._process.stderr.readline, b''):
            pass
            # print_debug(f"[MCP-SERVER-STDERR] {line.decode('utf-8').strip()}")

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
            
            # print_debug(f"[PY-CLIENT-SEND] {body_str}")

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

            # print_debug(f"[PY-CLIENT-RECV] {line_str}")
            
            try:
                return json.loads(line_str)
            except json.JSONDecodeError:
                continue

    def list_tools(self):
        """Sends a tools/list request and returns the result."""
        with self._lock:
            self._send_request("tools/list")
            response = self._read_response()
        return response.get("result", {})

    def call_tool(self, name, arguments):
        """Sends a tools/call request and returns the result."""
        params = {
            "name": name,
            "arguments": arguments,
        }
        with self._lock:
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
                print_debug(f"Terminating MCP server with PID: {self._process.pid}")
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print_debug(f"Server {self._process.pid} did not terminate, killing.")
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
        
        # Dynamically determine the path relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        server_dir = os.path.join(current_dir, 'mcp', 'web-search-mcp')
        script_path = os.path.join(server_dir, 'dist', 'index.js')

        if not os.path.exists(script_path):
            print_debug(f"Could not find MCP script at {script_path}")
            print_debug('Please download the "web-search-mcp" from "https://github.com/mrkrsl/web-search-mcp" and place it in "Platform/benchmark/mcp/web-search-mcp".')
            print_debug('Make sure to build it or download the "dist" folder.')
            
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
                result['link'] = result['url'] # Alias for frontend compatibility
                
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

        fetch_full_content = getattr(self, 'fetch_full_content', True)
        limit = getattr(self, 'search_limit', 5)

        search_args = {
            "query": query,
            "limit": limit,
        }
        
        tool_name = "get-web-search-summaries"
        if fetch_full_content:
            tool_name = "full-web-search"
            search_args["includeContent"] = True # Only include this for full-web-search

        try:
            search_result = self._client.call_tool(tool_name, search_args)
        except Exception as e:
            print_debug(f"Error calling MCP tool: {e}")
            return [{"error": f"Error calling MCP tool: {str(e)}"}]

        if search_result and "content" in search_result and len(search_result['content']) > 0:
            text_content = search_result['content'][0]['text']
            return self._parse_mcp_text_response(text_content)
        else:
            return [{"error": "Did not receive a valid search result or content is empty."}]
    
    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def format_results(self, results: list) -> str:
        if not results:
            return "No results found."
        
        formatted = []
        for i, r in enumerate(results):
            title = r.get('title', 'No Title')
            snippet = r.get('snippet', '')
            content = r.get('content', '')
            
            # Prefer content if available and longer than snippet, otherwise use snippet
            text = content if content and len(content) > len(snippet) else snippet
            
            formatted.append(f"[{i+1}] {title}\n{text}")
            
        return "\n\n".join(formatted)

class WebCrawler:
    def __init__(self, timeout=6, max_content_length=500000):
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        ]

    def extract(self, url: str) -> str:
        try:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return self._parse_content(response.text)
        except Exception as e:
            print_debug(f"WebCrawler error for {url}: {e}")
            return ""

    def _parse_content(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'noscript', 'iframe', 'img', 'video', 'audio', 'canvas', 'svg', 'object', 'embed', 'applet', 'form', 'input', 'textarea', 'select', 'button', 'label', 'fieldset', 'legend', 'optgroup', 'option', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
            
        # Try to find main content
        main_content = ""
        # Priority selectors for main content
        content_selectors = [
            'article', 'main', '[role="main"]', '.content', '.post-content', 
            '.entry-content', '.article-content', '#content', '#main'
        ]
        
        for selector in content_selectors:
            found = soup.select_one(selector)
            if found:
                text = found.get_text(separator=' ', strip=True)
                if len(text) > 100:
                    main_content = text
                    break
        
        if not main_content:
            main_content = soup.get_text(separator=' ', strip=True)
            
        return self._clean_text(main_content)

    def _clean_text(self, text: str) -> str:
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()[:self.max_content_length]

    def batch_extract(self, items: list, max_workers: int = None) -> list:
        if not items:
            return items
            
        if max_workers is None:
            # Default to number of CPUs, but cap at len(items)
            import multiprocessing
            try:
                cpu_count = multiprocessing.cpu_count()
            except ImportError:
                cpu_count = 4 # Fallback
            max_workers = min(cpu_count, len(items))
        
        # Ensure at least 1 worker
        max_workers = max(1, max_workers)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {executor.submit(self.extract, item.get('url')): item for item in items if item.get('url')}
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    content = future.result()
                    if content:
                        item['content'] = content
                except Exception as e:
                    print_debug(f"Error fetching content for {item.get('url')}: {e}")
        return items

class SerperSearch(WebSearch):
    def __init__(self, api_key, fetch_full_content=True, search_limit=5):
        self.api_key = api_key
        self.fetch_full_content = fetch_full_content
        self.search_limit = search_limit
        self.crawler = WebCrawler()

    def search(self, query: str) -> list:
        if not self.api_key:
            return [{"error": "Serper API key not configured."}]
            
        import http.client
        import json

        all_results = []
        items_to_fetch = []
        page = 1
        MAX_PAGES = 10 # Safety limit

        try:
            while len(all_results) < self.search_limit and page <= MAX_PAGES:
                conn = http.client.HTTPSConnection("google.serper.dev")
                payload = json.dumps({
                    "q": query,
                    "page": page
                })
                headers = {
                    'X-API-KEY': self.api_key,
                    'Content-Type': 'application/json'
                }
                conn.request("POST", "/search", payload, headers)
                res = conn.getresponse()
                data = res.read()
                response_data = json.loads(data.decode("utf-8"))
                
                new_results_found = False
                if 'organic' in response_data:
                    for item in response_data['organic']:
                        # Stop if we have enough results
                        if len(all_results) >= self.search_limit:
                            break

                        snippet = item.get('snippet', '')
                        url = item.get('link')
                        
                        result_item = {
                            'title': item.get('title'),
                            'url': url,
                            'link': url, # Alias for frontend compatibility
                            'snippet': snippet,
                            'content': snippet # Default to snippet
                        }
                        
                        all_results.append(result_item)
                        if self.fetch_full_content and url:
                            items_to_fetch.append(result_item)
                            
                        new_results_found = True
                
                if not new_results_found:
                    break
                
                page += 1

            # Parallel fetch for all collected items
            if items_to_fetch:
                self.crawler.batch_extract(items_to_fetch)

            return all_results

        except Exception as e:
            print_debug(f"Error calling Serper API: {e}")
            if all_results:
                return all_results
            return [{"error": f"Error calling Serper API: {str(e)}"}]

    def format_results(self, results: list) -> str:
        if not results:
            return "No results found."
            
        formatted = []
        for i, r in enumerate(results):
            title = r.get('title', 'No Title')
            content = r.get('content', '')
            
            formatted.append(f"[{i+1}] {title}\n{content}")
            
        return "\n\n".join(formatted)

# For easy swapping of search implementations
def get_search_engine() -> WebSearch:
    from .models import SearchSettings
    settings = SearchSettings.load()
    limit = getattr(settings, 'search_limit', 5)
    
    if settings.search_provider == 'serper':
        api_key = os.getenv('SERPER_API_KEY') or settings.serper_api_key
        return SerperSearch(api_key=api_key, fetch_full_content=settings.fetch_full_content, search_limit=limit)
    else:
        mcp = MCPSearch()
        mcp.fetch_full_content = settings.fetch_full_content
        mcp.search_limit = limit
        return mcp
