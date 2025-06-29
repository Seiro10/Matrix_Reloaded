from typing import TypedDict, List, Dict, Optional

class WorkflowState(TypedDict):
    terms: List[str]
    keywords: List[str]
    filtered_keywords: List[str]
    deduplicated_keywords: List[str]
    keyword_data: Dict[str, Dict]
    validation_id: Optional[str]
    awaiting_keyword_selection: Optional[bool]
    selected_keyword: Optional[str]
    processing_stopped: Optional[bool]
    no_data_reason: Optional[str]