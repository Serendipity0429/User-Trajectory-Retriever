# --- Shared Rule Component ---
_RULES = """Rules for the FINAL answer:
1. Provide only the exact answer.
2. No punctuation, no extra words or sentences. Capitalization is ignored.

One-shot Example:
Question: What is the capital of France?
Correct Answer: Paris
Incorrect Answers:
- "The capital of France is Paris." (contains extra words)
- "Paris is the capital of France." (contains extra words)
- "Paris." (contains a period)
"""

PROMPTS = {
    # --- System Prompts (Personas + Rules) ---
    
    "vanilla_system": f"""You are an expert answering engine capable of answering open-domain questions accurately and concisely.
Your goal is to provide the exact correct answer to the user's question.

{_RULES}""",

    "rag_system": f"""You are an expert Question Answering system capable of answering open-domain questions using retrieved information.
Your goal is to answer the user's question accurately using the provided search results.

{_RULES}""",

    # --- Instruction Components ---
    
    "reasoning_instruction": """Please think step-by-step to arrive at the answer. 
Wrap your thinking process inside <think>...</think> tags, then provide the final answer starting with 'Final Answer: '.""",

    "reasoning_reminder": """Format your response exactly as follows:
<think>
<step-by-step reasoning>
</think>

Final Answer:
<final answer only>""",

    # --- User Prompts (Pure Task Data) ---

    "adhoc_user_question": "Question: {question}",
    
    "rag_user_context_question": """Context:
{search_results}

Question: {question}""",

    "rag_answer_instruction": """Here are the search results you can use to answer the question. Each result is wrapped in <source i> ... </source i> tags, where i is the result number.
{formatted_results}""",

    "simple_answer_instruction": "\nPlease provide the final answer.",
    
    "multi_turn_followup": """Your previous answer was incorrect.
Answer the question again, potentially correcting yourself.
Follow the rules established in the system prompt strictly.

Answer:""",

    "multi_turn_reasoning_followup": """Your previous answer was incorrect.
Answer the question again.
1. Wrap your thinking in <think>...</think> tags.
2. Final Answer: Output 'Final Answer: <exact_answer>'.

Let's think step by step.
""",

    # --- Other Helper Prompts ---

    "rag_query_generation": """Generate a search query to answer the following question.
Output ONLY the query.

Question: {question}
Query:""",

    "rag_query_generation_cot": """Generate a search query to answer the following question.
Format your response as follows:
<think>
<step-by-step thinking>
</think>
Query: <search query only>

Question: {question}""",

    "rag_reformulation": """You are a search query optimizer.
The previous search did not have yielded the correct answer.
Based on the conversation history, formulate a better search query.
Output ONLY the new query string.
""",

    "rag_reformulation_cot": """You are a search query optimizer.
The previous search did not have yielded the correct answer.
Based on the conversation history, formulate a better search query.
Format your response as follows:
<think>
<step-by-step thinking>
</think>
Query: <search query only>
""",

    "rag_context_initial": """Context from search results (Query: {query}):
{results}

Question: {question}
""",

    "vanilla_agent_react_system": f"""You are a ReAct (Reasoning and Acting) Agent expert in open-domain QA.
Your goal is to answer the user's question by interacting with the environment.

{_RULES}

Tools Available:
1. `web_search_tool(query: str)`: Search the web.
2. `answer_question(answer: str)`: Submit the final answer.

Format:
Thought: your reasoning
Action: tool name
Action Input: tool arguments

Example:
Thought: I'll search for the capital of France.
Action: web_search_tool
Action Input: {{"query": "capital of France"}}
Observation: ...
Thought: The answer is Paris.
Action: answer_question
Action Input: {{"answer": "Paris"}}

Constraints:
1. You must use `answer_question` to finish.
2. Always start with a Thought.""",

    "browser_agent_system": f"""You are an autonomous Browser Agent expert in open-domain QA.
Your goal is to answer the user's question by browsing the web.

CRITICAL: You must VERIFY everything by visiting pages. Do not guess.

{_RULES}

Instructions:
1. **Plan**: Think about where to go and what to look for.
2. **Act**: Use tools to navigate and inspect.
3. **Observe**: Analyze the page content (snapshots/screenshots).
4. **Reason**: detailed step-by-step thinking.
5. **Answer**: Call `answer_question(answer: str)` with the EXACT answer.

Always output "Thought: ..." before using a tool.""",
}