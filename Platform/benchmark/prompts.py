PROMPTS = {
    "adhoc_answer": """Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: Paris

Incorrect Answers:
- \"The capital of France is Paris.\" (contains extra words)
- \"Paris is the capital of France.\" (contains extra words)
- \"Paris.\" (contains a period)

Now, answer the following question:
Question: {question}
Answer:""",
    "adhoc_reasoning": """Your task is to answer the following question.
First, explain your reasoning step-by-step. 
Then, on a new line, provide the final answer starting with 'Final Answer:'.

Follow these rules for the final answer strictly:
1. It must be an exact match to the correct answer.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

Question: {question}
""",
    "multi_turn_initial": """Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Question: {question}
Answer:""",
    "multi_turn_reasoning_initial": """Your task is to answer the following question.
First, explain your reasoning step-by-step.
Then, on a new line, provide the final answer starting with 'Final Answer:'.

Follow these rules for the final answer strictly:
1. It must be an exact match to the correct answer.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

Question: {question}
""",
    "multi_turn_followup": """Your task is to answer the question again. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Answer:""",
    "multi_turn_reasoning_followup": """Your task is to answer the question again.
First, explain your reasoning step-by-step.
Then, on a new line, provide the final answer starting with 'Final Answer:'.

Follow these rules for the final answer strictly:
1. It must be an exact match to the correct answer.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.
""",
    "rag_prompt_template": """Your task is to answer the following question based on the provided search results. Follow these rules strictly:
1. Your answer must be an exact match to the correct answer found in the search results.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: Paris

Incorrect Answers:
- "The capital of France is Paris." (contains extra words)
- "Paris is the capital of France." (contains extra words)
- "Paris." (contains a period)

Now, answer the following question based on the provided search results:
Question: {question}

Search Results:
{search_results}

Answer:""",
    "rag_system_context": "Context from web search (Query: {query}):\n{results}\n\n",
    "rag_reformulation": "Based on the history, provide a better search query to find the correct answer. Output ONLY the query.",
    "rag_adhoc_reasoning": """Your task is to answer the following question based on the provided search results.
First, explain your reasoning step-by-step. 
Then, on a new line, provide the final answer starting with 'Final Answer:'.

Follow these rules for the final answer strictly:
1. It must be an exact match to the correct answer found in the search results.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

Question: {question}

Search Results:
{search_results}
""",
    "vanilla_agent_react_system": """You are an intelligent research agent tasked with answering user questions accurately.
You have access to the following tools:
1. `web_search_tool(query: str)`: Search the internet for information.
2. `answer_question(answer: str)`: Submit the final answer.

**Instructions:**
1.  **Analyze the Request:** Understand the user's question.
2.  **Information Retrieval:** Use `web_search_tool` to gather necessary information. You can use it multiple times if needed.
3.  **Reasoning:** Think step-by-step about the information you have. Explain your logic.
4.  **Refinement:** If the user provides feedback (e.g., "Incorrect"), analyze WHY it might be wrong. Did you miss a detail? Was the source outdated? Search again with a refined query.
5.  **Final Answer:** When you are confident, use `answer_question` to submit the answer. The answer should be concise and directly address the question.

**Format:**
Always output your thought process as "Thought: [Your reasoning]" before taking any action.

**WARNING:**
You MUST use the `answer_question` tool to submit your final answer.
Do NOT output the answer directly as text.
If you find the answer, your next action MUST be `answer_question`.

**CRITICAL INSTRUCTION:**
Your final answer MUST strictly adhere to the following rules:
1. Your answer must be an exact match to the correct answer found in the search results.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: (call answer_question tool with the answer) Paris

Incorrect Answers:
- "The capital of France is Paris." (contains extra words)
- "Paris is the capital of France." (contains extra words)
- "Paris." (contains a period)
""",
    "browser_agent_system": """You are an intelligent browser automation agent.
You have access to a set of tools to interact with the browser. 
Your goal is to complete the user's task using these tools.

**CRITICAL INSTRUCTION:**
You MUST use the provided browser tools to gather information. 
Do NOT rely on your internal knowledge. You must VERIFY all information by browsing the web.
Even if you think you know the answer, you must prove it by visiting a webpage. 
Your final answer MUST strictly adhere to the following rules:
1. Your answer must be an exact match to the correct answer found in the search results.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: (call answer_question tool with the answer) Paris

Incorrect Answers:
- "The capital of France is Paris." (contains extra words)
- "Paris is the capital of France." (contains extra words)
- "Paris." (contains a period)

**Tool Categories and Usage:**
- **Input Automation:** `click`, `drag`, `fill`, `fill_form`, `handle_dialog`, `hover`, `press_key`, `upload_file`
- **Navigation Automation:** `close_page`, `list_pages`, `navigate_page`, `new_page`, `select_page`, `wait_for`
- **Emulation:** `emulate`, `resize_page`
- **Performance:** `performance_analyze_insight`, `performance_start_trace`, `performance_stop_trace`
- **Network:** `get_network_request`, `list_network_requests`
- **Debugging:** `evaluate_script`, `get_console_message`, `list_console_messages`, `take_screenshot`, `take_snapshot`

**General Instructions:**
1.  **Explore & Inspect:** Use navigation, debugging, and snapshot tools (e.g., `navigate_page`, `take_snapshot`) to understand the page and gather information.
2.  **Interact:** Use input automation tools (e.g., `click`, `fill`) to manipulate the page as needed to complete the task.
3.  **Answer:** Once you have completed the task and verified the information, you MUST use the `answer_question` tool to submit your final answer.

**Tool Usage Guidelines:**
- Always output your thought process "Thought: ..." before using a tool.
- Check tool documentation for specific capabilities and arguments.

**WARNING:**
- You MUST use `answer_question(answer="...")` to finish.
- Do NOT return the answer as plain text.
""",
}

