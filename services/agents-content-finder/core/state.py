from typing import TypedDict, List, Dict

class WorkflowState(TypedDict):
    terms: List[str]
    keywords: List[str]
    filtered_keywords: List[str]
    deduplicated_keywords: List[str]
    keyword_data: Dict[str, Dict]
