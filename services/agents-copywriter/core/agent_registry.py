from typing import Dict, Optional
from models.queue_models import AgentType
import os


class AgentRegistry:
    """Registry for all agents in the system"""

    def __init__(self):
        self.agents = {
            AgentType.COPYWRITER: {
                "name": "copywriter_agent",
                "url": os.getenv("COPYWRITER_AGENT_URL", "http://copywriter-agent:8083"),
                "health_endpoint": "/health",
                "queues": ["copywriter", "communication"]
            },
            AgentType.METADATA_GENERATOR: {
                "name": "metadata_generator",
                "url": os.getenv("METADATA_GENERATOR_URL", "http://metadata-generator:8084"),
                "health_endpoint": "/health",
                "queues": ["metadata"]
            },
            AgentType.REWRITER: {
                "name": "rewriter_agent",
                "url": os.getenv("REWRITER_AGENT_URL", "http://rewriter-main:8085"),
                "health_endpoint": "/health",
                "queues": ["rewriting"]
            }
        }

    def get_agent_url(self, agent_type: AgentType) -> Optional[str]:
        """Get agent URL by type"""
        return self.agents.get(agent_type, {}).get("url")

    def get_agent_queues(self, agent_type: AgentType) -> list:
        """Get queues for an agent"""
        return self.agents.get(agent_type, {}).get("queues", [])

    def register_agent(self, agent_type: AgentType, config: dict):
        """Register a new agent"""
        self.agents[agent_type] = config

    def get_all_agents(self) -> Dict[AgentType, dict]:
        """Get all registered agents"""
        return self.agents


# Global registry instance
agent_registry = AgentRegistry()