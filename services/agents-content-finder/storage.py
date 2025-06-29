"""
Shared storage for pending validations across modules
"""
from typing import Dict, Any

# Global storage for pending validations
pending_validations: Dict[str, Dict[str, Any]] = {}