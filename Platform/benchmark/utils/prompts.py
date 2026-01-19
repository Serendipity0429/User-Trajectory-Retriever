# Import from dedicated config file
from .model_config import has_builtin_thinking


def get_agent_prompt(prompt_key: str, model_name: str) -> str:
    """
    Build agent system prompt based on model capability.

    For thinking models: no think tool, no CoT instructions
    For other models: include think tool and CoT instructions
    """
    base_key = f"{prompt_key}_base"
    if base_key not in PROMPTS:
        # Fallback to direct key if no base version
        return PROMPTS.get(prompt_key, "")

    base_prompt = PROMPTS[base_key]

    if has_builtin_thinking(model_name):
        # Thinking models: no think tool, no explicit CoT
        return base_prompt.format(
            tools_section="",
            think_instruction=""
        )
    else:
        # Other models: include think tool and CoT instructions
        return base_prompt.format(
            tools_section="- `think(thought: str)`: Record your step-by-step reasoning.\n",
            think_instruction="2. You MUST use the `think` tool to explain your reasoning BEFORE using other tools. Please think step-by-step.\n"
        )


# --- Shared Rule Component ---
_RULES = """## Final Answer Format Rules
1. Your answer must be the EXACT MATCH to the expected answer. Please make the answer accurate and concise.
2. Provide answer in plain text. No markdown or any other formatting.
3. Don't include any punctuation, extra words or sentences.
4. Capitalization is ignored.

**Example:**
- Question: What is the capital of France?
- Correct: Paris
- Incorrect: The capital of France is Paris (contains extra words, not exact match)
- Incorrect: Paris is the capital of France (contains extra words, not exact match)
- Incorrect: Paris. (contains punctuation)
- Incorrect: **Paris** (contains markdown formatting)
"""

PROMPTS = {
    # =========================================================================
    # 1. SHARED COMPONENTS (used across all baselines for fair comparison)
    # =========================================================================

    # CoT prompting for models without built-in thinking
    # For thinking models, this is skipped entirely (they think natively)
    "shared_reasoning_instruction": """
Please think step-by-step to arrive at the answer. Make the reasoning as detailed as possible. Format your response as follows:
<think>
(step-by-step reasoning...)
</think>
Final Answer: (final answer only...) """,

    "shared_answer_request": "\nPlease provide the final answer.\nFinal Answer:",

    "shared_user_question": "Please answer the question: {question}",

    "shared_retry_request": "Your previous answer was incorrect. Please reflect on the conversation, re-examine the question, and try again.\n\nThe question is: {question}",

    "shared_retry_reasoning_prompt": """Your previous answer was incorrect. Please reflect on the conversation, re-examine the question, and try again.
The question is: {question}
""",

    # =========================================================================
    # 2. VANILLA BASELINE
    # =========================================================================

    "vanilla_system_prompt": f"""# Expert QA System

You are an expert answering engine capable of answering open-domain questions accurately and concisely.
Your goal is to provide the exact correct answer to the user's question.

{_RULES}""",

    # =========================================================================
    # 3. RAG BASELINE
    # =========================================================================

    "rag_system_prompt": f"""# RAG QA System

You are an expert Question Answering system capable of answering open-domain questions using retrieved information.
Your goal is to answer the user's question accurately using the provided search results.

{_RULES}""",

    "rag_query_gen_prompt": """Generate a search query to answer the following question.
Output ONLY the query.

Question: {question}
Search Query:""",

    # CoT version for non-thinking models
    "rag_query_gen_cot_prompt": """Generate a search query to answer the following question.
Format your response as follows:
<think>
<step-by-step thinking>
</think>
Search Query: <search query only>

Question: {question}""",

    "rag_query_reform_prompt": """You are a search query optimizer.
The previous search did not have yielded the correct answer.
Based on the conversation history, formulate a better search query.
Output ONLY the new query string.
""",

    # CoT version for non-thinking models
    "rag_query_reform_cot_prompt": """You are a search query optimizer.
The previous search did not have yielded the correct answer.
Based on the conversation history, formulate a better search query.
Format your response as follows:
<think>
<step-by-step thinking>
</think>
Search Query: <search query only>
""",

    "rag_context_wrapper": """Here are the search results you can use to answer the question. Each result is wrapped in <source i> ... </source i> tags, where i is the result number.
{formatted_results}""",

    "rag_context_debug_wrapper": """Context from search results (Search Query: {query}):
{results}

Question: {question}
""",

    "rag_debug_format": "*** SYSTEM PROMPT ***\n{system_prompt}\n\n*** USER INPUT ***\n{instruction}",

    # =========================================================================
    # 4. AGENT BASELINES (Shared & Specific)
    # =========================================================================

    # --- Vanilla Agent (ReAct) ---
    # Base prompt - think tool added dynamically based on model capability
    "vanilla_agent_system_prompt_base": f"""# ReAct Agent

You are a ReAct (Reasoning and Acting) Agent expert in open-domain QA.
Your goal is to answer the user's question by interacting with the environment.

{_RULES}

## Tools Available
{{tools_section}}
- `web_search_tool(query: str)`: Search the web. Returns snippets only.
- `visit_page(url: str)`: Visit a web page to read its full content.
- `answer_question(answer: str)`: Submit the final answer.

## Instructions
1. You must use `answer_question` to finish.
{{think_instruction}}
2. The search tool only provides snippets. You usually need to `visit_page` to verify information or get details.
3. Do not output text directly. Use the tools provided.
""",

    # --- Browser Agent (Autonomous) ---
    # Base prompt - think tool added dynamically based on model capability
    "browser_agent_system_prompt_base": f"""# Browser Agent

You are an autonomous Browser Agent expert in open-domain QA.
Your goal is to answer the user's question by browsing the web.

{_RULES}

## Tools Available
{{tools_section}}
- Browser tools provided by Chrome-Devtools-MCP.
- `answer_question(answer: str)`: Submit the final answer.

## Instructions
1. You must use `answer_question` to finish.
{{think_instruction}}
2. Do not output text directly. Use the tools provided.
""",

}
