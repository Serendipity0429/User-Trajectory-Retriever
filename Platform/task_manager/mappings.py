EXPECTED_SOURCES_MAP = {
    "random": True,
    "mapping": {
        "personal": "Personal Knowledge / Experience",
        "wikipedia": "Wikipedia / Encyclopedia",
        "news": "News / Media Outlet",
        "forum": "Forum / Social Media / Q&A Site",
        "academic": "Academic Paper / Book",
        "video": "Video / Documentary",
        "other": "Other",
    },
}

EFFORT_MAP = {
    "random": False,
    "mapping": {
        0: "0-3 minutes",
        1: "3-5 minutes",
        2: "5-10 minutes",
        3: "10-15 minutes",
        4: "15-30 minutes",
        5: "30+ minutes",
    },
}

EFFORT_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        0: "The task is very simple and I expect to find the answer almost immediately.",
        1: "The task is simple and I expect to find the answer with a simple search.",
        2: "The task is of average difficulty and may require browsing a few pages.",
        3: "The task is difficult and may require some in-depth research.",
        4: "The task is very difficult and may require significant effort and synthesis.",
        5: "The task is extremely difficult and I expect it to take a long time.",
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
        2: "You can need to browse a few pages or perform a few searches.",
        3: "You can need to do some in-depth research and synthesis.",
        4: "This is a very challenging task that may require significant effort.",
    },
}

CONFIDENCE_MAP = {
    "random": False,
    "mapping": {
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
        "other": "<strong>Other</strong>",
    },
}

FAILURE_CATEGORY_MAP = {
    "random": True,
    "mapping": {
        "ineffective_search": "<strong>Ineffective Search Strategy</strong>: poor keywords, couldn't find info, etc.",
        "misunderstood_info": "<strong>Misunderstood Information</strong>: misinterpreted text, calculation error, etc.",
        "unreliable_source": "<strong>Unreliable or Unclear Source</strong>: outdated, ambiguous, untrustworthy, etc.",
        "format_error": "<strong>Answer Formatting Error</strong>: wrong units, incorrect decimal places, etc.",
        "other": "<strong>Other</strong>:",
    },
}

CORRECTIVE_PLAN_MAP = {
    "random": True,
    "mapping": {
        "improve_search": "<strong>Improve Search Strategy</strong>: use different keywords, find new source types, etc.",
        "improve_evaluation": "<strong>Improve Source Evaluation</strong>: check reliability, validate with other sources, etc.",
        "improve_analysis": "<strong>Improve Information Analysis</strong>: re-read carefully, check logic, etc.",
        "correct_format": "<strong>Correct Answer Formatting</strong>: fix units, decimal places, etc.",
        "other": "<strong>Other</strong>:",
    },
}

AHA_MOMENT_MAP = {
    "random": True,
    "mapping": {
        "direct_statement": "Direct Statement / Paragraph",
        "data_table": "Data Table / Chart",
        "official_document": "Official Document / Report",
        "key_definition": "Key Definition / Concept",
        "synthesis": "Synthesizing Multiple Sources",
        "other": "Other",
    },
}

UNHELPFUL_PATHS_MAP = {
    "random": True,
    "mapping": {
        "no_major_roadblocks": "<strong>No Roadblocks:</strong> The search process was straightforward.",
        "irrelevant_results": "<strong>Irrelevant Results:</strong> Search results were not relevant to the task.",
        "outdated_info": "<strong>Outdated Information:</strong> I found information that was no longer accurate.",
        "low_quality": "<strong>Low-Quality Sources:</strong> I encountered untrustworthy or difficult-to-use websites.",
        "paywall": "<strong>Paywall:</strong> I was blocked by a paywall or a login requirement.",
        "contradictory_info": "<strong>Contradictory Information:</strong> I found conflicting information on different websites.",
        "other": "<strong>Other:</strong>",
    },
}

STRATEGY_SHIFT_MAP = {
    "random": True,
    "mapping": {
        "no_change": "<strong>No Change:</strong> My initial plan was effective and did not need to change.",
        "narrowed_search": "<strong>Narrowed Search:</strong> I made my search queries more specific to narrow down the results.",
        "broadened_search": "<strong>Broadened Search:</strong> I made my search queries more general to get a broader overview.",
        "changed_source_type": "<strong>Changed Source Type:</strong> I switched from one type of source to another (e.g., news to academic papers).",
        "re-evaluated_assumption": "<strong>Re-evaluated Assumption:</strong> I realized an initial assumption was wrong, which changed my approach.",
        "other": "<strong>Other:</strong>",
    },
}

AHA_MOMENT_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "data_table": "The answer was found in a structured table or chart.",
        "direct_statement": "The answer was explicitly stated in a sentence or paragraph.",
        "official_document": "An authoritative document (e.g., PDF, government site) provided the answer.",
        "key_definition": "Understanding a specific term or concept was the key.",
        "synthesis": "The answer was derived by combining information from different sources or sections.",
        "other": "A different type of information was critical.",
    },
}

UNHELPFUL_PATHS_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "no_major_roadblocks": "The search process was straightforward.",
        "irrelevant_results": "Your search queries returned results that were not relevant to the task.",
        "outdated_info": "You found information that was no longer accurate.",
        "low_quality": "You encountered websites that were untrustworthy or difficult to use.",
        "paywall": "You were blocked by a paywall or a login requirement.",
        "contradictory_info": "You found conflicting information on different websites.",
        "other": "None of the above.",
    },
}

STRATEGY_SHIFT_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "no_change": "Your initial plan was effective and you did not need to change it.",
        "narrowed_search": "You made your search queries more specific to narrow down the results.",
        "broadened_search": "You made your search queries more general to get a broader overview of the topic.",
        "changed_source_type": "You switched from looking at one type of source (e.g., news articles) to another (e.g., academic papers).",
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
        "too_long": "The task is consuming an excessive amount of time relative to its expected difficulty or importance.",
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
        "unreliable_source": "Select this if the information you used was problematic. This includes sources that were outdated, ambiguous, contradictory, or not authoritative.",
        "format_error": "Select this if your answer was factually correct but did not follow the required format (e.g., wrong units, incorrect decimal places).",
        "other": "A reason for failure not listed here.",
    },
}

CORRECTIVE_ACTION_EXPLANATION_MAP = {
    "random": False,
    "mapping": {
        "improve_search": "Select this if you plan to change how you search. This includes using different/better keywords or looking for new types of sources (e.g., news, academic papers).",
        "improve_evaluation": "Select this if you plan to be more critical of your sources. This includes checking the authority and recency of a source, or cross-referencing with other sources.",
        "improve_analysis": "Select this if you plan to analyze the information you find more carefully. This includes re-reading the text, double-checking your logic, or re-doing calculations.",
        "correct_format": "Select this if you need to fix the format of your answer to meet the requirements.",
        "other": "A corrective action not listed here.",
    },
}

CANCEL_CATEGORY_MAP = {
    "random": True,
    "mapping": {
        "info_unavailable": "<strong>Information Unavailable:</strong> I believe the information is not publicly available online.",
        "ambiguous_question": "<strong>Ambiguous Question:</strong> The task is unclear, ambiguous, or appears to contain incorrect assumptions.",
        "scope_too_large": "<strong>Excessive Scope:</strong> The amount of research or synthesis required is much larger than anticipated.",
        "too_long": "<strong>Too Time-Consuming:</strong> The task is taking too much time to complete.",
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
