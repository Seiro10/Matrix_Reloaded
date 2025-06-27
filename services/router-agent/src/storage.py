"""
Shared storage for HIL validations
Both main.py and agent.py can import from here
"""
from typing import Dict, Any

# Global storage for pending validations
pending_validations: Dict[str, Any] = {}

# Global storage for active workflows
active_workflows: Dict[str, Any] = {}