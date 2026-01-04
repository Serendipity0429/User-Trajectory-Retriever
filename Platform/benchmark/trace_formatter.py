import json
from .utils import print_debug

def parse_react_content(content):
    """
    Parses a ReAct-style text content into blocks of Thought, Action, Observation.
    """
    if not isinstance(content, str):
        return [{"type": "text", "content": content}]
        
    blocks = []
    current_type = "text"
    current_lines = []
    
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Thought:") or stripped.startswith("Reasoning:"):
            if current_lines:
                blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
            current_type = "thought"
            current_lines = [stripped.split(":", 1)[1].strip() if ":" in stripped else stripped]
        elif stripped.startswith("Action:") or stripped.startswith("Tool Call:"):
            if current_lines:
                blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
            current_type = "action"
            current_lines = [stripped.split(":", 1)[1].strip() if ":" in stripped else stripped]
        elif stripped.startswith("Observation:") or stripped.startswith("Execution Result:"):
            if current_lines:
                blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
            current_type = "observation"
            current_lines = [stripped.split(":", 1)[1].strip() if ":" in stripped else stripped]
        else:
            current_lines.append(line)
            
    if current_lines:
        blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
        
    # Filter out empty blocks
    return [b for b in blocks if b['content']]

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
                 else:
                     # Add placeholder thought if missing to ensure UI consistency
                     trace_data.append({
                         "role": m.role,
                         "name": m.name,
                         "step_type": "thought",
                         "content": "Thinking Process (Agent initiated tool call directly)",
                         "timestamp": getattr(m, 'timestamp', None)
                     })

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

                            trace_data.append({
                                "role": m.role,
                                "name": m.name,
                                "step_type": "action",
                                "content": json.dumps(item, indent=2),
                                "timestamp": getattr(m, 'timestamp', None)
                            })

                        elif isinstance(item, dict) and item.get('type') == 'tool_result':
                            # Flush texts
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
                 trace_data.append({
                    "role": m.role,
                    "name": m.name,
                    "step_type": "text",
                    "content": str(content),
                    "timestamp": getattr(m, 'timestamp', None)
                })
        
        return trace_data, real_answer_found
