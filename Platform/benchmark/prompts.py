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
"""
}

