"""
Extract search queries from LLM benchmark data.
Standardized output format: task > entities > trials > queries
"""
import json
import os
import glob
import re
from urllib.parse import urlparse, parse_qs, unquote_plus


DATA_DIR = os.path.join(os.path.dirname(__file__), "../data/")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "extracted_queries/")


# Regex pattern for search engine URLs - handles regional variants
SEARCH_ENGINE_REGEX = re.compile(
    r'https?://(?:[\w-]+\.)?('
    r'google\.[\w.]+/search|'
    r'bing\.com/search|'
    r'duckduckgo\.com/|'
    r'search\.yahoo\.[\w.]+/search|'
    r'yandex\.[\w.]+/search|'
    r'baidu\.com/s|'
    r'youtube\.com/results|'
    r'last\.fm/search|'
    r'musicbrainz\.org/search|'
    r'allmusic\.com/search/|'
    r'amazon\.[\w.]+/s|'
    r'ebay\.[\w.]+/sch|'
    r'reddit\.com/search|'
    r'twitter\.com/search|'
    r'x\.com/search|'
    r'github\.com/search|'
    r'stackoverflow\.com/search|'
    r'scholar\.google\.[\w.]+/scholar|'
    r'wolframalpha\.com/input|'
    r'books\.google\.[\w.]+/books'
    r')', re.IGNORECASE
)


def _get_query_param_for_domain(domain_match):
    """Get query parameter name based on domain match."""
    domain_lower = domain_match.lower()

    if 'google' in domain_lower:
        return 'q'
    elif 'bing' in domain_lower:
        return 'q'
    elif 'duckduckgo' in domain_lower:
        return 'q'
    elif 'yahoo' in domain_lower:
        return 'p'
    elif 'yandex' in domain_lower:
        return 'text'
    elif 'baidu' in domain_lower:
        return 'wd'
    elif 'youtube' in domain_lower:
        return 'search_query'
    elif 'last.fm' in domain_lower:
        return 'q'
    elif 'musicbrainz' in domain_lower:
        return 'query'
    elif 'allmusic' in domain_lower:
        return None  # Path-based
    elif 'amazon' in domain_lower:
        return 'k'
    elif 'ebay' in domain_lower:
        return '_nkw'
    elif 'reddit' in domain_lower:
        return 'q'
    elif 'twitter' in domain_lower:
        return 'q'
    elif 'x.com' in domain_lower:
        return 'q'
    elif 'github' in domain_lower:
        return 'q'
    elif 'stackoverflow' in domain_lower:
        return 'q'
    elif 'scholar' in domain_lower:
        return 'q'
    elif 'wolframalpha' in domain_lower:
        return 'i'
    elif 'books' in domain_lower:
        return 'q'

    return None


def _extract_source_from_domain(domain):
    """Extract search engine name from domain."""
    domain_lower = domain.lower()
    if 'google' in domain_lower:
        return 'google'
    elif 'bing' in domain_lower:
        return 'bing'
    elif 'baidu' in domain_lower:
        return 'baidu'
    elif 'yahoo' in domain_lower:
        return 'yahoo'
    elif 'yandex' in domain_lower:
        return 'yandex'
    elif 'duckduckgo' in domain_lower:
        return 'duckduckgo'
    elif 'youtube' in domain_lower:
        return 'youtube'
    elif 'last.fm' in domain_lower:
        return 'lastfm'
    elif 'musicbrainz' in domain_lower:
        return 'musicbrainz'
    elif 'allmusic' in domain_lower:
        return 'allmusic'
    elif 'amazon' in domain_lower:
        return 'amazon'
    elif 'ebay' in domain_lower:
        return 'ebay'
    elif 'reddit' in domain_lower:
        return 'reddit'
    elif 'twitter' in domain_lower or 'x.com' in domain_lower:
        return 'twitter'
    elif 'github' in domain_lower:
        return 'github'
    elif 'stackoverflow' in domain_lower:
        return 'stackoverflow'
    elif 'scholar' in domain_lower:
        return 'google_scholar'
    elif 'wolframalpha' in domain_lower:
        return 'wolframalpha'
    return 'unknown'


def extract_query_from_url(url, timestamp=None):
    """
    Extract search query and metadata from a URL.

    Returns dict with keys: query, source, domain, url, timestamp (if provided)
    Returns None if no query found.
    """
    if not url:
        return None

    # Skip Google CAPTCHA/sorry pages
    if '/sorry/' in url.lower() or '/recaptcha/' in url.lower():
        return None

    match = SEARCH_ENGINE_REGEX.search(url)
    if not match:
        return None

    domain_match = match.group(1).lower()
    query_param = _get_query_param_for_domain(domain_match)

    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    source = _extract_source_from_domain(domain)

    query_text = None
    if query_param is None:
        # Path-based extraction
        path_parts = parsed_url.path.split('/')
        if len(path_parts) >= 3:
            query_text = unquote_plus(path_parts[-1])
    else:
        query_params = parse_qs(parsed_url.query)
        q_val = query_params.get(query_param)
        if q_val:
            query_text = q_val[0]

    if not query_text:
        return None

    result = {
        'query': query_text,
        'source': source,
        'domain': domain,
        'url': url
    }

    if timestamp:
        result['timestamp'] = timestamp

    return result


def extract_rag_queries(data):
    """Extract queries from RAG pipeline data."""
    results = {}

    for session in data.get("sessions", []):
        question = session.get("question")
        session_id = f"session_{session.get('session_id')}"

        if question not in results:
            results[question] = {"question": question, "trajectories": {}}

        results[question]["trajectories"][session_id] = {}

        for trial in session.get("trials", []):
            trial_number = trial.get("trial_number")
            queries = []

            for message in trial.get("messages", []):
                if message.get("role") == "assistant" and isinstance(message.get("content"), str):
                    content = message["content"]
                    if content.startswith("Search Query:"):
                        query_text = content.replace("Search Query:", "").strip()
                        # RAG pipeline doesn't have URLs, so create minimal metadata
                        queries.append({
                            'query': query_text,
                            'source': 'rag_internal',
                            'domain': None,
                            'url': None
                        })

            # Deduplicate based on query text while preserving order
            seen = set()
            deduped_queries = []
            for q in queries:
                if q['query'] not in seen:
                    seen.add(q['query'])
                    deduped_queries.append(q)

            results[question]["trajectories"][session_id][trial_number] = deduped_queries

    return results


def extract_vanilla_queries(data):
    """Extract queries from vanilla agent pipeline data."""
    results = {}

    for session in data.get("sessions", []):
        question = session.get("question")
        session_id = f"session_{session.get('session_id')}"

        if question not in results:
            results[question] = {"question": question, "trajectories": {}}

        results[question]["trajectories"][session_id] = {}

        for trial in session.get("trials", []):
            trial_number = trial.get("trial_number")
            queries = []

            for message in trial.get("messages", []):
                if message.get("role") == "assistant" and isinstance(message.get("content"), list):
                    for content_item in message["content"]:
                        if content_item.get("type") == "tool_use" and content_item.get("name") == "web_search_tool":
                            query_text = content_item.get("input", {}).get("query")
                            if query_text:
                                # Vanilla agent uses web_search_tool, no direct URL
                                queries.append({
                                    'query': query_text,
                                    'source': 'agent_tool',
                                    'domain': None,
                                    'url': None
                                })

            # Deduplicate based on query text while preserving order
            seen = set()
            deduped_queries = []
            for q in queries:
                if q['query'] not in seen:
                    seen.add(q['query'])
                    deduped_queries.append(q)

            results[question]["trajectories"][session_id][trial_number] = deduped_queries

    return results


def extract_browser_queries(data):
    """Extract queries from browser agent pipeline data."""
    results = {}

    for session in data.get("sessions", []):
        question = session.get("question")
        session_id = f"session_{session.get('session_id')}"

        if question not in results:
            results[question] = {"question": question, "trajectories": {}}

        results[question]["trajectories"][session_id] = {}

        for trial in session.get("trials", []):
            trial_number = trial.get("trial_number")
            queries = []

            for message in trial.get("messages", []):
                if message.get("role") == "assistant" and isinstance(message.get("content"), list):
                    for content_item in message["content"]:
                        if content_item.get("type") == "tool_use":
                            url = content_item.get("input", {}).get("url")
                            query_obj = extract_query_from_url(url)
                            if query_obj:
                                queries.append(query_obj)

            # Deduplicate based on query text while preserving order
            seen = set()
            deduped_queries = []
            for q in queries:
                if q['query'] not in seen:
                    seen.add(q['query'])
                    deduped_queries.append(q)

            results[question]["trajectories"][session_id][trial_number] = deduped_queries

    return results


def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    files = glob.glob(os.path.join(DATA_DIR, "*.json"))

    for file_path in files:
        filename = os.path.basename(file_path)
        if filename == "vanilla_llm.json":
            continue

        print(f"Processing {filename}...")

        with open(file_path, 'r') as f:
            data = json.load(f)

        if filename == "rag.json":
            extracted = extract_rag_queries(data)
        elif filename == "vanilla_agent.json":
            extracted = extract_vanilla_queries(data)
        elif filename == "browser_agent.json":
            extracted = extract_browser_queries(data)
        else:
            print(f"Skipping unknown file type: {filename}")
            continue

        output_path = os.path.join(OUTPUT_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(extracted, f, indent=2, ensure_ascii=False, sort_keys=True)

        # Print stats
        total_queries = sum(
            len(queries)
            for task_data in extracted.values()
            for trajectory_trials in task_data["trajectories"].values()
            for queries in trajectory_trials.values()
        )
        print(f"Extracted {total_queries} queries from {len(extracted)} tasks")
        print(f"Saved to {output_path}\n")

if __name__ == "__main__":
    main()
