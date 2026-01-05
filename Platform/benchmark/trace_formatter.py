import json
from .utils import print_debug

def parse_think_tags(content):
    """
    Splits content into blocks of Thought and Text based on <think> tags.
    Case-insensitive and handles multiple blocks.
    """
    if not isinstance(content, str):
        return [{"type": "text", "content": content}]
    
    import re
    blocks = []
    
    # Pattern to find <think>...</think> blocks, case-insensitive
    pattern = r"(?si)<think>(.*?)</think>"
    
    last_idx = 0
    for match in re.finditer(pattern, content):
        # Text before the think tag
        before_text = content[last_idx:match.start()].strip()
        if before_text:
            blocks.append({"type": "text", "content": before_text})
        
        # Thinking content
        think_content = match.group(1).strip()
        if think_content:
            blocks.append({"type": "thought", "content": think_content})
        
        last_idx = match.end()
    
    # Remaining text after the last think tag
    after_text = content[last_idx:].strip()
    if after_text:
        # Check if the remaining text IS a think tag itself (incomplete)
        if "<think" in after_text.lower() and "</think" not in after_text.lower():
             # Handle trailing open think tag
             parts = re.split(r"(?i)<think>", after_text, maxsplit=1)
             if parts[0].strip():
                 blocks.append({"type": "text", "content": parts[0].strip()})
             if len(parts) > 1:
                 blocks.append({"type": "thought", "content": parts[1].strip()})
        else:
            blocks.append({"type": "text", "content": after_text})
        
    return blocks

def parse_react_content(content):
    """
    Parses a ReAct-style text content into blocks of Thought, Action, Observation.
    Also handles <think> tags.
    """
    if not isinstance(content, str):
        return [{"type": "text", "content": content}]
    
    # 1. First, split by <think> tags if they exist
    lower_content = content.lower()
    if "<think>" in lower_content or "<think" in lower_content:
        initial_blocks = parse_think_tags(content)
    else:
        initial_blocks = [{"type": "text", "content": content}]
        
    # 2. For each 'text' block from initial split, further split by ReAct headers
    final_blocks = []
    
    for block in initial_blocks:
        if block['type'] != 'text':
            final_blocks.append(block)
            continue
            
        # Split this text block by headers
        text_content = block['content']
        current_type = "text"
        current_lines = []
        
        def flush_current():
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    final_blocks.append({"type": current_type, "content": text})
                current_lines.clear()

        lines = text_content.split('\n')
        for line in lines:
            stripped = line.strip()
            # Detect headers
            if stripped.startswith("Thought:") or stripped.startswith("Reasoning:"):
                flush_current()
                current_type = "thought"
                # Keep the header text if it contains content after the colon
                parts = stripped.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    current_lines.append(parts[1].strip())
            elif stripped.startswith("Action:") or stripped.startswith("Tool Call:") or stripped.startswith("Search Query:"):
                flush_current()
                current_type = "action"
                current_lines.append(line) # Keep header for Action/Query
            elif stripped.startswith("Observation:") or stripped.startswith("Execution Result:") or stripped.startswith("Search Results:"):
                flush_current()
                current_type = "observation"
                current_lines.append(line) # Keep header for Observation/Results
            elif stripped.startswith("Final Answer:") or stripped.startswith("Answer:"):
                flush_current()
                current_type = "text" # Final answer is standard text
                current_lines.append(line)
            else:
                current_lines.append(line)
                
        flush_current()
            
    # Filter out empty blocks
    return [b for b in final_blocks if b['content']]

class TraceFormatter:
    """
    Helper class to format agent execution traces into a standardized JSON structure.
    """
    @staticmethod
    def serialize(trace_msgs):
        trace_data = []
        real_answer_found = None
        should_stop = False
        
        for m in trace_msgs:
            if should_stop:
                break
                
            # Check for native tool calls
            m_dict = m.to_dict() if hasattr(m, 'to_dict') else m.__dict__
            
            # Helper to extract text from content list/dict
            def extract_text(c):
                if isinstance(c, str): return c
                if isinstance(c, list):
                    try:
                        texts = []
                        for item in c:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                texts.append(item.get('text', ''))
                            elif isinstance(item, str):
                                texts.append(item)
                        return "".join(texts)
                    except: return json.dumps(c, indent=2)
                if isinstance(c, dict):
                    if c.get('type') == 'text': return c.get('text', '')
                    return json.dumps(c, indent=2)
                return str(c)

            # 1. Handle Tool Calls (Action)
            if m_dict.get('tool_calls') or m_dict.get('function_call'):
                 calls = m_dict.get('tool_calls') or m_dict.get('function_call')
                             
                 # Try to extract answer from tool call
                 if isinstance(calls, list):
                     for call in calls:
                         if call.get('name') == 'answer_question' or call.get('function', {}).get('name') == 'answer_question':
                             # Extract answer
                             args = call.get('input') or call.get('function', {}).get('arguments')
                             if isinstance(args, str):
                                 try: args = json.loads(args)
                                 except: pass
                             if isinstance(args, dict) and 'answer' in args:
                                 real_answer_found = args['answer']
            
                         # SPECIAL HANDLING: "think" tool
                         if call.get('name') == 'think' or call.get('function', {}).get('name') == 'think':
                             # Extract thought
                             args = call.get('input') or call.get('function', {}).get('arguments')
                             if isinstance(args, str):
                                 try: args = json.loads(args)
                                 except: pass
                             if isinstance(args, dict) and 'thought' in args:
                                 # We treat this tool call as a PURE thought step, NOT an action
                                 trace_data.append({
                                     "role": m.role,
                                     "name": m.name,
                                     "step_type": "thought",
                                     "content": args['thought'],
                                     "timestamp": getattr(m, 'timestamp', None)
                                 })
                                 continue # Skip adding it as an action
            
                 content_str = json.dumps(calls, indent=2)
                             
                 # Robust check for content existence
                 has_content = False
                 if m.content:
                     if isinstance(m.content, str) and m.content.strip():
                         has_content = True
                     elif isinstance(m.content, list) and len(m.content) > 0:
                         has_content = True
                     elif isinstance(m.content, dict):
                         has_content = True
            
                 if has_content:
                     trace_data.append({
                         "role": m.role,
                         "name": m.name,
                         "step_type": "thought",
                         "content": extract_text(m.content),
                         "timestamp": getattr(m, 'timestamp', None)
                     })
                             
                 # Only add action if it wasn't just a think tool (which we continued/skipped above)
                 trace_data.append({
                     "role": m.role,
                     "name": m.name,
                     "step_type": "action",
                     "content": content_str,
                     "timestamp": getattr(m, 'timestamp', None)
                 })
                 continue
            
            # 2. Handle Structured Content (e.g. Tool Results/Observations from agentscope)
            content = m.content
            if isinstance(content, list):
                try:
                    # Clean up nested JSON in tool results and SPLIT content
                    import copy
                    cleaned_content = copy.deepcopy(content)
                                
                    current_texts = []
                                
                    for item in cleaned_content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            current_texts.append(item.get('text', ''))
                                    
                        elif isinstance(item, dict) and item.get('type') == 'tool_use':
                            # Flush texts as thought
                            if current_texts:
                                trace_data.append({
                                    "role": m.role,
                                    "name": m.name,
                                    "step_type": "thought",
                                    "content": "\n".join(current_texts),
                                    "timestamp": getattr(m, 'timestamp', None)
                                })
                                current_texts = []
                                        
                            # Add action
                            if item.get('name') == 'answer_question':
                                 args = item.get('input')
                                 if isinstance(args, dict) and 'answer' in args:
                                     real_answer_found = args['answer']
                                        
                            # Handle think tool in structured content
                            if item.get('name') == 'think':
                                args = item.get('input')
                                if isinstance(args, dict) and 'thought' in args:
                                     trace_data.append({
                                         "role": m.role,
                                         "name": m.name,
                                         "step_type": "thought",
                                         "content": args['thought'],
                                         "timestamp": getattr(m, 'timestamp', None)
                                     })
                                     continue # Skip action for think tool
            
                            trace_data.append({
                                "role": m.role,
                                "name": m.name,
                                "step_type": "action",
                                "content": json.dumps(item, indent=2),
                                "timestamp": getattr(m, 'timestamp', None)
                            })
                                    
                        # Handle think tool observation (skip it or treat as hidden)
                        elif isinstance(item, dict) and item.get('type') == 'tool_result' and item.get('name') == 'think':
                             continue # Hide the observation of thinking
            
                        elif isinstance(item, dict) and item.get('type') == 'tool_result':                            # Flush texts
                            if current_texts:
                                trace_data.append({
                                    "role": m.role,
                                    "name": m.name,
                                    "step_type": "text",
                                    "content": "\n".join(current_texts),
                                    "timestamp": getattr(m, 'timestamp', None)
                                })
                                current_texts = []

                            # Process output JSON if needed
                            output = item.get('output')
                            if isinstance(output, str) and (output.strip().startswith('[') or output.strip().startswith('{')):
                                try: item['output'] = json.loads(output)
                                except: pass
                            
                            output_content = json.dumps(item, indent=2)
                            if item.get('name') == 'web_search_tool':
                                # Ensure we dump the list if possible to help frontend detection
                                if isinstance(item.get('output'), list):
                                    output_content = json.dumps(item.get('output'), indent=2)

                            if item.get('name') == 'answer_question':
                                should_stop = True
                            
                            trace_data.append({
                                "role": m.role,
                                "name": m.name,
                                "step_type": "observation",
                                "content": output_content,
                                "timestamp": getattr(m, 'timestamp', None)
                            })
                        else:
                            # Fallback for unknown items in list
                            if isinstance(item, str):
                                current_texts.append(item)
                            else:
                                current_texts.append(json.dumps(item))

                    # Flush remaining texts
                    if current_texts:
                        trace_data.append({
                            "role": m.role,
                            "name": m.name,
                            "step_type": "thought" if m.role == "assistant" else "text",
                            "content": "\n".join(current_texts),
                            "timestamp": getattr(m, 'timestamp', None)
                        })

                    continue
                except Exception as e:
                    print_debug(f"Error parsing list content: {e}")
                    pass
                
                content = extract_text(content)
            elif isinstance(content, dict):
                content = extract_text(content)
            
            # 3. Handle Text Content (Thoughts/Standard messages)
            if isinstance(content, str):
                role = getattr(m, 'role', 'assistant')
                
                # ONLY parse assistant messages for thinking tags or ReAct headers
                if role == 'assistant':
                    # Fallback: Check for JSON answer in text (robustness)
                    import re
                    json_match = re.search(r'\{\s*"answer"\s*:\s*"(.*?)"\s*\}', content)
                    if json_match:
                         real_answer_found = json_match.group(1)
                         # Treat this block as an action to trigger final answer bubble
                         trace_data.append({
                             "role": m.role,
                             "name": m.name,
                             "step_type": "action",
                             "content": f'{{"name": "answer_question", "input": {{"answer": "{real_answer_found}"}}}}',
                             "timestamp": getattr(m, 'timestamp', None)
                         })
                         # Simulate observation
                         trace_data.append({
                             "role": m.role,
                             "name": m.name,
                             "step_type": "observation",
                             "content": "Answer submitted successfully.",
                             "timestamp": getattr(m, 'timestamp', None)
                         })
                         should_stop = True
                         continue

                    blocks = parse_react_content(content)
                    for b in blocks:
                        trace_data.append({
                            "role": m.role,
                            "name": m.name,
                            "step_type": b['type'],
                            "content": b['content'],
                            "timestamp": getattr(m, 'timestamp', None)
                        })
                else:
                    # System or User message: treat as plain text (do NOT parse tags)
                    trace_data.append({
                        "role": m.role,
                        "name": m.name,
                        "step_type": "text",
                        "content": content,
                        "timestamp": getattr(m, 'timestamp', None)
                    })
            else:
                 trace_data.append({
                    "role": m.role,
                    "name": m.name,
                    "step_type": "text",
                    "content": str(content),
                    "timestamp": getattr(m, 'timestamp', None)
                })
        
        return trace_data, real_answer_found
