EXPECTED_SOURCES_MAP = {
    "random": True,
    "mapping": {
        "personal": "Personal Knowledge / Experience",
        "wikipedia": "Wikipedia / Encyclopedia",
        "news": "News / Media Outlet",
        "social_media": "Social Media (Twitter, Reddit, etc.)",
        "specialized_forum": "Specialized Forum / Q&A (StackOverflow, Quora, etc.)",
        "academic": "Academic Paper / Book",
        "official_source": "Official Source (Website, Government Site, Documentation)",
        "video": "Video / Documentary",
        "other": "Other",
    },
}

EFFORT_MAP = {
    "random": False,
    "mapping": {
        0: "0-5 minutes",
        1: "5-10 minutes",
        2: "10-15 minutes",
        3: "15-30 minutes",
        4: "30+ minutes",
    },
}

EFFORT_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        0: "The task is very simple, and you expect to find the answer almost immediately.",
        1: "The task is simple, and you expect to find the answer with a basic search.",
        2: "The task is of average difficulty and may require browsing a few pages.",
        3: "The task is difficult and may require in-depth research.",
        4: "The task is very difficult and may require significant effort and synthesis.",
        5: "The task is extremely difficult, and you expect it to take a long time.",
    },
}

FAMILIARITY_MAP = {
    "random": False,
    "mapping": {
        0: "0 - Not familiar at all",
        1: "1 - Slightly familiar",
        2: "2 - Moderately familiar",
        3: "3 - Familiar",
        4: "4 - Very familiar",
    },
}

DIFFICULTY_MAP = {
    "random": False,
    "mapping": {
        0: "0 - Very easy",
        1: "1 - Easy",
        2: "2 - Moderately difficult",
        3: "3 - Difficult",
        4: "4 - Very difficult",
    },
}

FAMILIARITY_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        0: "You have no prior knowledge or experience with this topic.",
        1: "You have heard of the topic, but know very little about it.",
        2: "You have some basic knowledge of the topic.",
        3: "You are comfortable with the topic and have a good understanding of it.",
        4: "You have a deep understanding of the topic and could explain it to others.",
    },
}

DIFFICULTY_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        0: "You can find the answer almost immediately.",
        1: "You can find the answer with a simple search.",
        2: "You may need to browse a few pages or perform several searches.",
        3: "You may need to conduct in-depth research and synthesis.",
        4: "This is a very challenging task that likely requires significant effort.",
    },
}

CONFIDENCE_MAP = {
    "random": False,
    "mapping": {
        -1: "Not Rated",
        1: "1 - Just a guess",
        2: "2 - Not very confident",
        3: "3 - Fairly confident",
        4: "4 - Very confident",
        5: "5 - Certain",
    },
}

ANSWER_FORMULATION_MAP = {
    "random": True,
    "mapping": {
        "direct_fact": "<strong>Direct Answer:</strong> The answer was stated clearly on a single page.",
        "synthesis_single_page": "<strong>Synthesis (Same Page):</strong> I had to combine multiple pieces of information from the same page.",
        "synthesis_multi_page": "<strong>Synthesis (Multiple Pages):</strong> I had to combine information from different webpages.",
        "calculation": "<strong>Calculation:</strong> I had to perform a calculation based on data I found.",
        "inference": "<strong>Inference:</strong> I had to make an inference or deduction that was not explicitly stated.",
        "contradiction_resolution": "<strong>Contradiction Resolution:</strong> I found conflicting info and had to determine which was correct.",
        "verification": "<strong>Verification:</strong> I found the answer but verified it on a second source to be sure.",
        "other": "<strong>Other</strong>",
    },
}

FAILURE_CATEGORY_MAP = {
    "random": True,
    "mapping": {
        "ineffective_search": "<strong>Ineffective Search Strategy</strong>: poor keywords, couldn't find info, etc.",
        "misunderstood_info": "<strong>Misunderstood Information</strong>: misinterpreted text, calculation error, etc.",
        "question_misinterpretation": "<strong>Question Misinterpretation:</strong> I misunderstood what the task was actually asking for.",
        "time_management": "<strong>Time Management:</strong> I spent too long on one unpromising path.",
        "unreliable_source": "<strong>Unreliable or Unclear Source</strong>: outdated, ambiguous, untrustworthy, etc.",
        "format_error": "<strong>Answer Formatting Error</strong>: wrong units, incorrect decimal places, etc.",
        "other": "<strong>Other</strong>:",
    },
}

CORRECTIVE_PLAN_MAP = {
    "random": True,
    "mapping": {
        "improve_search": "<strong>Improve Search Strategy</strong>: use different keywords, find new source types, etc.",
        "deeper_processing": "<strong>Deeper Processing</strong>: read more carefully, check logic, or verify source reliability.",
        "tool_change": "<strong>Tool Change:</strong> I will use a different search engine or tool.",
        "scope_adjustment": "<strong>Scope Adjustment:</strong> I will focus on a narrower/broader part of the problem first.",
        "correct_format": "<strong>Correct Answer Formatting</strong>: fix units, decimal places, etc.",
        "other": "<strong>Other</strong>:",
    },
}

AHA_MOMENT_MAP = {
    "random": True,
    "mapping": {
        "direct_statement": "Direct Statement / Paragraph",
        "key_definition": "Key Definition / Concept",
        "official_document": "Official Document / Report",
        "visual_or_data": "Visual Aid / Data Table (Image, Map, Chart, etc.)",
        "synthesis": "Synthesis (Combining Facts / Inference / Deduction)",
        "other": "Other",
    },
}

UNHELPFUL_PATHS_MAP = {
    "random": True,
    "mapping": {
        "no_major_roadblocks": "<strong>No Roadblocks:</strong> The search process was straightforward.",
        "irrelevant_or_overload": "<strong>Irrelevant / Information Overload:</strong> Search results were irrelevant, or the volume of information was overwhelming.",
        "low_quality_or_outdated": "<strong>Low Quality / Outdated Info:</strong> Encountered untrustworthy, difficult-to-use, or outdated sources.",
        "contradictory_info": "<strong>Contradictory Information:</strong> Found conflicting information on different websites.",
        "paywall": "<strong>Paywall:</strong> Access was blocked by a paywall or login requirement.",
        "language_barrier": "<strong>Language / Terminology Barrier:</strong> Content was too technical or in a language I didn't understand.",
        "circular_navigation": "<strong>Circular Navigation:</strong> I kept ending up on the same unhelpful pages.",
        "distractions": "<strong>Distractions / Ads:</strong> The page was difficult to read due to ads or popups.",
        "other": "<strong>Other:</strong>",
    },
}

STRATEGY_SHIFT_MAP = {
    "random": True,
    "mapping": {
        "no_change": "<strong>No Change:</strong> My initial plan was effective and did not need to change.",
        "narrowed_search": "<strong>Narrowed Search:</strong> I made my search queries more specific to narrow down the results.",
        "broadened_search": "<strong>Broadened Search:</strong> I made my search queries more general to get a broader overview.",
        "reformulation": "<strong>Reformulation:</strong> I completely changed the terms used (not just narrowed/broadened).",
        "source_or_platform_switch": "<strong>Changed Source / Platform:</strong> I switched to a different type of source or platform (e.g., News to Academic, Google to Wikipedia).",
        "re-evaluated_assumption": "<strong>Re-evaluated Assumption:</strong> I realized an initial assumption was wrong, which changed my approach.",
        "other": "<strong>Other:</strong>",
    },
}

AHA_MOMENT_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "direct_statement": "The answer was explicitly stated in a sentence or paragraph.",
        "key_definition": "Understanding a specific term or concept was the key.",
        "official_document": "An authoritative document (e.g., PDF, government site) provided the answer.",
        "visual_or_data": "The answer was found in a non-textual format like a table, chart, image, map, or diagram.",
        "synthesis": "The answer was derived by inferring a conclusion not explicitly stated.",
        "other": "A different type of information was critical.",
    },
}

UNHELPFUL_PATHS_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "no_major_roadblocks": "The search process was straightforward.",
        "irrelevant_or_overload": "Your search queries returned irrelevant results, or the volume of information was too large to filter effectively.",
        "low_quality_or_outdated": "You encountered websites that were untrustworthy, user-unfriendly, or contained outdated information.",
        "contradictory_info": "You found conflicting information on different websites.",
        "paywall": "You were blocked by a paywall or a login requirement.",
        "language_barrier": "The results were too technical or in a language you didn't understand.",
        "circular_navigation": "You found yourself repeatedly visiting the same unhelpful pages.",
        "distractions": "The page was difficult to read due to ads, popups, or clutter.",
        "other": "None of the above.",
    },
}

STRATEGY_SHIFT_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "no_change": "Your initial plan was effective and you did not need to change it.",
        "narrowed_search": "You made your search queries more specific to narrow down the results.",
        "broadened_search": "You made your search queries more general to get a broader overview of the topic.",
        "reformulation": "You completely changed the search terms used.",
        "source_or_platform_switch": "You switched to a different type of source (e.g., news to academic) or platform (e.g., Google to Wikipedia).",
        "re-evaluated_assumption": "You realized that one of your initial assumptions was wrong, which led you to change your search strategy.",
        "other": "None of the above.",
    },
}

CANCEL_CATEGORY_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "info_unavailable": "You have searched, but cannot find the required information on the public web.",
        "too_difficult": "The task requires a level of analysis, synthesis, or understanding that is beyond your current capabilities.",
        "no_idea": "You have exhausted your initial ideas and are unsure how to approach the problem differently.",
        "too_complex_or_long": "The task is consuming an excessive amount of time or the scope of research is much larger than anticipated.",
        "low_confidence": "You discovered potential answers but lacked sufficient confidence in their accuracy or reliability to proceed.",
        "technical_issue": "You are blocked by a non-information-related problem, such as a website that is down, a required login, or a paywall.",
        "other": "None of the above categories accurately describe the reason for cancellation.",
    },
}

MISSING_RESOURCES_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "expert_knowledge": "The task requires understanding of a specialized field that you do not possess.",
        "paid_access": "The information is likely behind a paywall or in a subscription-only database.",
        "better_tools": "A standard search engine is insufficient; a specialized tool (e.g., a scientific database, code interpreter) is needed.",
        "different_question": "The question is poorly phrased, ambiguous, or contains incorrect assumptions.",
        "info_not_online": "The information is likely to exist only in offline sources (e.g., books, private archives).",
        "time_limit": "You could likely solve it, but not within a reasonable timeframe.",
        "team_help": "The task requires collaboration or brainstorming with others.",
        "guidance": "You need a hint or direction from someone who knows the answer or the path to it.",
        "better_question": "The instructions for the task are unclear or incomplete.",
        "other": "A resource not listed here was needed.",
    },
}

FAILURE_CATEGORY_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "ineffective_search": "Select this if your search strategy was flawed. This includes using ineffective keywords (too broad/narrow), or being unable to locate the necessary information online.",
        "misunderstood_info": "Select this if you found the correct information but misinterpreted it. This includes misunderstanding the text, making a calculation error, or lacking the expertise to evaluate it correctly.",
        "question_misinterpretation": "Select this if you misunderstood what the task was asking you to do or find.",
        "time_management": "Select this if you spent too much time on a path that didn't yield results.",
        "unreliable_source": "Select this if the information you used was problematic. This includes sources that were outdated, ambiguous, contradictory, or not authoritative.",
        "format_error": "Select this if your answer was factually correct but did not follow the required format (e.g., wrong units, incorrect decimal places).",
        "other": "A reason for failure not listed here.",
    },
}

CORRECTIVE_ACTION_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "improve_search": "Select this if you plan to change how you search. This includes using different/better keywords or looking for new types of sources (e.g., news, academic papers).",
        "deeper_processing": "Select this if you plan to be more critical or thorough. This includes checking source authority, cross-referencing, re-reading text, or double-checking logic/calculations.",
        "tool_change": "Select this if you plan to use a different search engine, database, or tool.",
        "scope_adjustment": "Select this if you plan to narrow or broaden the scope of your search initially.",
        "correct_format": "Select this if you need to fix the format of your answer to meet the requirements.",
        "other": "A corrective action not listed here.",
    },
}

CANCEL_CATEGORY_MAP = {
    "random": True,
    "mapping": {
        "info_unavailable": "<strong>Information Unavailable:</strong> I believe the information is not publicly available online.",
        "ambiguous_question": "<strong>Ambiguous Question:</strong> The task is unclear, ambiguous, or appears to contain incorrect assumptions.",
        "too_complex_or_long": "<strong>Too Complex / Time-Consuming:</strong> The task scope was too large or taking too much time to complete.",
        "low_confidence": "<strong>Low Confidence:</strong> I found potential answers but none were reliable enough to submit.",
        "technical_issue": "<strong>Technical Barrier:</strong> I encountered a technical barrier (e.g., paywall, login, broken site).",
        "other": "<strong>Other:</strong>",
    },
}

MISSING_RESOURCES_MAP = {
    "random": True,
    "mapping": {
        "expert_knowledge": "<strong>Specialized Knowledge:</strong> The task requires deep, specialized domain knowledge.",
        "paid_access": "<strong>Paid Access:</strong> Access to a paid subscription, database, or service is needed.",
        "better_tools": "<strong>Better Tools:</strong> A more powerful or specialized search tool is required.",
        "team_help": "<strong>Collaboration:</strong> Help or collaboration from a team or community would be beneficial.",
        "other": "<strong>Other:</strong>",
    },
}
