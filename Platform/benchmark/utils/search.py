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
from core.utils import print_debug

def remove_null_bytes(data):
    """
    Recursively removes null bytes and replacement characters from strings.
    """
    if isinstance(data, str):
        return data.replace('\x00', '').replace('\ufffd', '')
    if isinstance(data, list):
        return [remove_null_bytes(item) for item in data]
    if isinstance(data, dict):
        return {k: remove_null_bytes(v) for k, v in data.items()}
    return data

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
            pass  # Consume stderr to prevent buffer blocking

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
            return remove_null_bytes(self._parse_mcp_text_response(text_content))
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
            
            formatted.append(f"<source {i+1}> {title}\n{text}</source {i+1}>")
            
        return "".join(formatted)

class WebCrawler:
    """
    Modern web crawler with comprehensive binary detection, retry logic,
    and robust content extraction.
    """

    # Comprehensive list of binary file extensions to skip
    BINARY_EXTENSIONS = frozenset([
        # Documents
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',
        # Images
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.svg', '.tiff', '.tif',
        '.raw', '.cr2', '.nef', '.heic', '.heif', '.avif',
        # Audio
        '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus', '.mid', '.midi',
        # Video
        '.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv', '.flv', '.m4v', '.mpeg', '.mpg', '.3gp',
        # Archives
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso', '.dmg', '.cab', '.lz', '.zst',
        # Executables & binaries
        '.exe', '.dll', '.so', '.dylib', '.bin', '.app', '.msi', '.deb', '.rpm', '.apk', '.ipa',
        # Fonts
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        # Data & databases
        '.db', '.sqlite', '.mdb', '.accdb', '.dat', '.sav',
        # Other binary
        '.swf', '.class', '.jar', '.pyc', '.pyo', '.o', '.a', '.lib', '.obj',
        '.torrent', '.img', '.vhd', '.vmdk', '.qcow2',
    ])

    # Magic number signatures for binary file detection
    # Format: (signature_bytes, offset, description)
    BINARY_SIGNATURES = [
        (b'%PDF', 0, 'PDF'),
        (b'PK\x03\x04', 0, 'ZIP/Office'),
        (b'PK\x05\x06', 0, 'ZIP empty'),
        (b'\x89PNG\r\n\x1a\n', 0, 'PNG'),
        (b'\xff\xd8\xff', 0, 'JPEG'),
        (b'GIF87a', 0, 'GIF87'),
        (b'GIF89a', 0, 'GIF89'),
        (b'RIFF', 0, 'RIFF (WEBP/WAV/AVI)'),
        (b'BM', 0, 'BMP'),
        (b'\x1f\x8b', 0, 'GZIP'),
        (b'BZ', 0, 'BZIP2'),
        (b'Rar!\x1a\x07', 0, 'RAR'),
        (b"7z\xbc\xaf'\x1c", 0, '7ZIP'),
        (b'\x7fELF', 0, 'ELF binary'),
        (b'\xfe\xed\xfa\xce', 0, 'Mach-O 32'),
        (b'\xfe\xed\xfa\xcf', 0, 'Mach-O 64'),
        (b'\xcf\xfa\xed\xfe', 0, 'Mach-O 32 rev'),
        (b'\xca\xfe\xba\xbe', 0, 'Java class/Mach-O fat'),
        (b'MZ', 0, 'DOS/PE executable'),
        (b'ID3', 0, 'MP3 ID3'),
        (b'\xff\xfb', 0, 'MP3 sync'),
        (b'\xff\xfa', 0, 'MP3 sync'),
        (b'OggS', 0, 'OGG'),
        (b'fLaC', 0, 'FLAC'),
        (b'wOFF', 0, 'WOFF'),
        (b'wOF2', 0, 'WOFF2'),
        (b'\x00\x00\x01\x00', 0, 'ICO'),
        (b'\x00\x00\x00\x1c\x66\x74\x79\x70', 0, 'MP4/MOV ftyp'),
        (b'\x00\x00\x00\x20\x66\x74\x79\x70', 0, 'MP4/MOV ftyp'),
        (b'SQLite format 3', 0, 'SQLite'),
    ]

    # Modern Chrome user agents (updated regularly)
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    ]

    # Content types that are safe to parse as text
    TEXT_CONTENT_TYPES = frozenset([
        'text/html', 'application/xhtml+xml', 'application/xml', 'text/xml',
        'text/plain', 'application/json', 'text/css', 'application/javascript',
        'text/javascript', 'application/ld+json', 'text/markdown',
    ])

    # Elements to remove during content extraction
    REMOVE_ELEMENTS = [
        'script', 'style', 'noscript', 'iframe', 'img', 'video', 'audio',
        'canvas', 'svg', 'object', 'embed', 'applet', 'form', 'input',
        'textarea', 'select', 'button', 'nav', 'header', 'footer', 'aside',
        'ad', 'advertisement', 'banner', 'popup', 'modal', 'cookie-notice',
    ]

    # CSS selectors for main content (priority order)
    CONTENT_SELECTORS = [
        'article', 'main', '[role="main"]', '[role="article"]',
        '.post-content', '.entry-content', '.article-content', '.article-body',
        '.content-body', '.story-body', '.post-body', '.blog-post',
        '#article-content', '#post-content', '#main-content', '#content', '#main',
        '.content', '.post', '.entry',
    ]

    def __init__(self, timeout: int = 15, max_content_length: int = 500000, max_retries: int = 2, use_browser: bool = True):
        """
        Initialize the WebCrawler.

        Args:
            timeout: Request timeout in seconds
            max_content_length: Maximum content length to extract (bytes)
            max_retries: Number of retry attempts for failed requests
            use_browser: Use headless browser as final fallback for bot-protected sites
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.max_retries = max_retries
        self.use_browser = use_browser
        self._session = None
        self._playwright = None
        self._browser = None

    def _get_session(self) -> requests.Session:
        """Get or create a reusable session with retry adapter."""
        if self._session is None:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            self._session = requests.Session()
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["GET", "HEAD"],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def _validate_url(self, url: str) -> bool:
        """Validate URL scheme and format."""
        if not url:
            return False
        url_lower = url.lower()
        if not (url_lower.startswith('http://') or url_lower.startswith('https://')):
            print_debug(f"Invalid URL scheme (must be http/https): {url}")
            return False
        return True

    def _is_binary_extension(self, url: str) -> bool:
        """Check if URL ends with a known binary file extension."""
        # Extract path, ignoring query params
        path = url.split('?')[0].split('#')[0].lower()
        return any(path.endswith(ext) for ext in self.BINARY_EXTENSIONS)

    def _is_binary_content(self, data: bytes) -> bool:
        """Check if content starts with known binary signatures."""
        if not data:
            return False
        for signature, offset, _ in self.BINARY_SIGNATURES:
            end_pos = offset + len(signature)
            if len(data) >= end_pos and data[offset:end_pos] == signature:
                return True
        return False

    def _is_text_content_type(self, content_type: str) -> bool:
        """Check if Content-Type header indicates text content."""
        if not content_type:
            return True  # Assume text if not specified
        ct_lower = content_type.lower().split(';')[0].strip()
        return any(t in ct_lower for t in self.TEXT_CONTENT_TYPES)

    def _get_headers(self) -> dict:
        """Generate realistic browser headers."""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-CH-UA': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"macOS"',
            'Cache-Control': 'max-age=0',
        }

    def extract(self, url: str) -> str:
        """
        Extract text content from a web page.

        Args:
            url: The URL to fetch and extract content from

        Returns:
            Extracted text content, or empty string if extraction fails
        """
        # Validate URL
        if not self._validate_url(url):
            return ""

        # Check extension-based filtering
        if self._is_binary_extension(url):
            print_debug(f"Skipping binary file extension: {url}")
            return ""

        # Try requests first, then curl fallback, then browser fallback
        content = self._extract_with_requests(url)
        if content:
            return content

        print_debug(f"Requests failed for {url}, trying curl fallback...")
        content = self._extract_with_curl(url)
        if content:
            return content

        # Final fallback: headless browser for bot-protected sites
        if self.use_browser:
            print_debug(f"Curl failed for {url}, trying browser fallback...")
            return self._extract_with_browser(url)

        return ""

    def _extract_with_requests(self, url: str) -> str:
        """Extract content using requests library."""
        try:
            session = self._get_session()
            headers = self._get_headers()

            with session.get(
                url,
                headers=headers,
                timeout=(5, self.timeout),  # (connect, read) timeouts
                stream=True,
                allow_redirects=True,
            ) as response:
                # Check for blocked/error status
                if response.status_code in [401, 403, 429, 451]:
                    print_debug(f"Request blocked: {url} ({response.status_code})")
                    return ""

                response.raise_for_status()

                # Validate content type
                content_type = response.headers.get('Content-Type', '')
                if not self._is_text_content_type(content_type):
                    print_debug(f"Non-text content type: {url} ({content_type})")
                    return ""

                # Read initial chunk for binary detection
                initial_chunk = b""
                for chunk in response.iter_content(chunk_size=8192):
                    initial_chunk += chunk
                    if len(initial_chunk) >= 8192:
                        break

                if self._is_binary_content(initial_chunk):
                    print_debug(f"Binary content detected: {url}")
                    return ""

                # Read remaining content
                full_content = initial_chunk
                for chunk in response.iter_content(chunk_size=16384):
                    full_content += chunk
                    if len(full_content) > self.max_content_length:
                        print_debug(f"Content truncated at {self.max_content_length} bytes: {url}")
                        break

                # Decode content
                encoding = response.encoding or response.apparent_encoding or 'utf-8'
                try:
                    text = full_content.decode(encoding, errors='replace')
                except (LookupError, TypeError):
                    text = full_content.decode('utf-8', errors='replace')

                # Check for high garbage ratio (likely binary or encoding issues)
                if text:
                    garbage_ratio = text.count('\ufffd') / len(text)
                    if garbage_ratio > 0.03:
                        print_debug(f"High garbage ratio ({garbage_ratio:.1%}): {url}")
                        return ""

                return self._extract_text(text)

        except requests.exceptions.Timeout:
            print_debug(f"Request timeout: {url}")
            return ""
        except requests.exceptions.TooManyRedirects:
            print_debug(f"Too many redirects: {url}")
            return ""
        except requests.exceptions.RequestException as e:
            print_debug(f"Request error for {url}: {e}")
            return ""
        except Exception as e:
            print_debug(f"Unexpected error for {url}: {e}")
            return ""

    def _extract_with_curl(self, url: str) -> str:
        """Extract content using curl as fallback."""
        try:
            command = [
                'curl',
                '-L',                           # Follow redirects
                '--max-redirs', '10',           # Limit redirects
                '-s', '-S',                     # Silent but show errors
                '--compressed',                 # Handle compression
                '--max-time', str(self.timeout),
                '--connect-timeout', '5',
                '-A', random.choice(self.USER_AGENTS),
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '-H', 'Accept-Language: en-US,en;q=0.9',
                url
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout + 5,
            )

            if result.returncode != 0:
                print_debug(f"Curl failed for {url}: {result.stderr[:200] if result.stderr else 'Unknown error'}")
                return ""

            if not result.stdout:
                return ""

            return self._extract_text(result.stdout)

        except subprocess.TimeoutExpired:
            print_debug(f"Curl timeout: {url}")
            return ""
        except Exception as e:
            print_debug(f"Curl error for {url}: {e}")
            return ""

    def _extract_with_browser(self, url: str) -> str:
        """Extract content using headless browser for bot-protected sites."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print_debug("Playwright not installed, skipping browser fallback")
            return ""

        try:
            # Lazy initialization of playwright
            if self._playwright is None:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )

            context = self._browser.new_context(
                user_agent=random.choice(self.USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True,
            )
            page = context.new_page()

            try:
                # Navigate with timeout
                page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)

                # Wait for potential Cloudflare challenge to resolve
                page.wait_for_timeout(2000)

                # Check if still on challenge page
                title = page.title()
                if 'Just a moment' in title or 'Cloudflare' in title:
                    print_debug(f"Waiting for Cloudflare challenge: {url}")
                    page.wait_for_timeout(5000)

                # Get page content
                html = page.content()

                # Also try to get rendered text directly
                try:
                    text = page.evaluate('() => document.body.innerText')
                    if text and len(text) > 200:
                        return self._clean_text(text)
                except Exception:
                    pass

                return self._extract_text(html)

            finally:
                context.close()

        except Exception as e:
            print_debug(f"Browser error for {url}: {e}")
            return ""

    def cleanup(self):
        """Clean up browser resources."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def __del__(self):
        """Destructor to clean up resources."""
        self.cleanup()

    def _extract_text(self, html: str) -> str:
        """Extract and clean text content from HTML."""
        if not html or len(html) < 50:
            return ""

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove unwanted elements
            for selector in self.REMOVE_ELEMENTS:
                for element in soup.select(selector) if '.' in selector or '#' in selector else soup.find_all(selector):
                    element.decompose()

            # Also remove elements by class/id patterns (use word boundaries to avoid false matches)
            # e.g., "ad" should not match "header", "loading", "download"
            ad_pattern = re.compile(r'\b(ads?|advert|advertisement|banner|popup|modal|cookie-?notice|consent-?banner|newsletter|subscribe)\b', re.I)
            for element in soup.find_all(class_=ad_pattern):
                element.decompose()
            for element in soup.find_all(id=ad_pattern):
                element.decompose()

            # Try to find main content using priority selectors
            main_content = ""
            for selector in self.CONTENT_SELECTORS:
                try:
                    found = soup.select_one(selector)
                    if found:
                        text = found.get_text(separator=' ', strip=True)
                        if len(text) > 200:  # Minimum viable content
                            main_content = text
                            break
                except Exception:
                    continue

            # Fallback to body content
            if not main_content:
                body = soup.find('body')
                if body:
                    main_content = body.get_text(separator=' ', strip=True)
                else:
                    main_content = soup.get_text(separator=' ', strip=True)

            return self._clean_text(main_content)

        except Exception as e:
            print_debug(f"Error extracting text: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""

        # Remove null bytes and replacement characters
        text = text.replace('\x00', '').replace('\ufffd', '')

        # Remove ASCII control characters except newlines/tabs
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # Normalize whitespace (collapse multiple spaces/newlines)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)

        # Truncate to max length
        if len(text) > self.max_content_length:
            text = text[:self.max_content_length]
            # Try to break at a sentence boundary
            last_period = text.rfind('. ')
            if last_period > self.max_content_length * 0.8:
                text = text[:last_period + 1]

        return text.strip()

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

            return remove_null_bytes(all_results)

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
            
            formatted.append(f"<source {i+1}> {title}\n{content}</source {i+1}>")
            
        return "".join(formatted)

# For easy swapping of search implementations
def get_search_engine(fetch_full_content=None) -> WebSearch:
    from ..models import BenchmarkSettings
    settings = BenchmarkSettings.load()
    limit = getattr(settings, 'search_limit', 5)
    
    should_fetch = fetch_full_content if fetch_full_content is not None else settings.fetch_full_content
    
    if settings.search_provider == 'serper':
        api_key = os.getenv('SERPER_API_KEY') or settings.serper_api_key
        return SerperSearch(api_key=api_key, fetch_full_content=should_fetch, search_limit=limit)
    else:
        mcp = MCPSearch()
        mcp.fetch_full_content = should_fetch
        mcp.search_limit = limit
        return mcp
