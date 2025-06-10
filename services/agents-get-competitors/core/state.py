from typing import TypedDict, List, Dict, Any


class State(TypedDict):
    input_json: List[Dict[str, Any]]
    urls_to_process: List[Dict[str, Any]]
    processed: List[Dict[str, Any]]